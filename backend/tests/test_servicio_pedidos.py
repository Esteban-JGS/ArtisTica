"""Servicio de pedidos contra una base migrada. Cada prueba termina en rollback."""

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import event, select
from sqlalchemy.exc import IntegrityError

from src.core.config import settings
from src.core.exceptions import (
    ActorNoAutorizado,
    FueraDePlazo,
    HechosInconsistentes,
    ObraNoDisponible,
    ReglaDeNegocioViolada,
    ResourceNotFound,
)
from src.domain.pedidos import HechosPasarela
from src.domain.politicas import PoliticasPedido
from src.models import (
    Cobro,
    Consulta,
    Disputa,
    Entregable,
    EstadoCobro,
    EstadoConsulta,
    EstadoDisputa,
    EstadoMedia,
    EstadoObra,
    EstadoPedido,
    MediaAsset,
    Obra,
    Pedido,
    PlanArtista,
    Profile,
    RolPerfil,
    TipoCobro,
    TipoPedido,
)
from src.services import pedidos as servicio

POLITICAS = PoliticasPedido.desde_config(settings)
T0 = datetime(2026, 10, 1, 12, 0, tzinfo=UTC)
PASARELA = "falsa"


# Fabricas


async def _perfil(session, plan=PlanArtista.TALLER, rol=RolPerfil.PUBLICO) -> Profile:
    perfil = Profile(
        id=uuid.uuid4(),
        handle=f"p{uuid.uuid4().hex[:12]}",
        nombre="Prueba",
        rol=rol,
        plan=plan,
    )
    session.add(perfil)
    await session.flush()
    return perfil


async def _consulta(session, cliente, artista) -> Consulta:
    consulta = Consulta(
        cliente_id=cliente.id, artista_id=artista.id, estado=EstadoConsulta.ABIERTA
    )
    session.add(consulta)
    await session.flush()
    return consulta


async def _obra(session, artista, precio=Decimal("15000.00")) -> Obra:
    obra = Obra(
        artista_id=artista.id,
        titulo="Colibri en acuarela",
        estado=EstadoObra.DISPONIBLE,
        precio=precio,
    )
    session.add(obra)
    await session.flush()
    return obra


async def _media(session, artista, *, subido=True, **kw) -> MediaAsset:
    media = MediaAsset(
        propietario_id=artista.id,
        tipo="imagen",
        storage_path=f"previas/{uuid.uuid4()}.jpg",
        estado=EstadoMedia.PROCESADO,
        subido_en=T0 if subido else None,
        **kw,
    )
    session.add(media)
    await session.flush()
    return media


async def _cobros(session, pedido) -> dict[TipoCobro, Cobro]:
    filas = await session.execute(
        select(Cobro)
        .where(Cobro.pedido_id == pedido.id)
        .execution_options(populate_existing=True)
    )
    return {c.tipo: c for c in filas.scalars()}


async def _recargar(session, modelo, id_):
    return await session.get(modelo, id_, populate_existing=True)


async def _encargo_cotizado(session, artista=None, cliente=None, **kw) -> Pedido:
    artista = artista or await _perfil(session)
    cliente = cliente or await _perfil(session)
    consulta = await _consulta(session, cliente, artista)
    datos = {"monto_total": Decimal("10000.01"), "anticipo_porcentaje": Decimal("33")}
    datos.update(kw)
    return await servicio.crear_pedido_desde_cotizacion(
        session,
        consulta_id=consulta.id,
        tipo=TipoPedido.ENCARGO,
        descripcion="Retrato de mascota",
        pasarela=PASARELA,
        ahora=T0,
        politicas=POLITICAS,
        **datos,
    )


async def _encargo_pagado(session, captura: datetime) -> Pedido:
    """Encargo recorrido hasta saldo_pagado, con el saldo capturado en `captura`."""
    pedido = await _encargo_cotizado(session)
    await servicio.registrar_anticipo_capturado(
        session, pedido_id=pedido.id, referencia_pasarela=f"a{pedido.id}", ahora=T0
    )
    await servicio.iniciar_trabajo(session, pedido_id=pedido.id)
    media = await _media(session, await _recargar(session, Profile, pedido.artista_id))
    await servicio.entregar_vista_previa(
        session,
        pedido_id=pedido.id,
        media_asset_id=media.id,
        bucket_publico=settings.BUCKET_MEDIOS,
    )
    await servicio.registrar_saldo_autorizado(
        session,
        pedido_id=pedido.id,
        referencia_pasarela=f"s{pedido.id}",
        autorizado_hasta=captura + timedelta(days=5),
        ahora=captura - timedelta(hours=1),
    )
    return await servicio.registrar_saldo_capturado(
        session, pedido_id=pedido.id, ahora=captura, politicas=POLITICAS
    )


# 7. Camino completo de un encargo


async def test_07_camino_completo_de_un_encargo(async_session):
    s = async_session
    artista, cliente = await _perfil(s), await _perfil(s)
    pedido = await _encargo_cotizado(s, artista, cliente)
    consulta = await _recargar(s, Consulta, pedido.consulta_id)
    assert pedido.estado is EstadoPedido.COTIZADO
    assert consulta.estado is EstadoConsulta.COTIZADA
    cobros = await _cobros(s, pedido)
    assert cobros[TipoCobro.ANTICIPO].monto == Decimal("3300.00")
    assert cobros[TipoCobro.SALDO].monto == Decimal("6700.01")

    # Contraoferta sobre el mismo pedido
    await servicio.actualizar_cotizacion(
        s,
        pedido_id=pedido.id,
        descripcion="Retrato de dos mascotas",
        monto_total=Decimal("12000.00"),
        anticipo_porcentaje=None,
        ahora=T0,
        politicas=POLITICAS,
    )
    cobros = await _cobros(s, pedido)
    assert cobros[TipoCobro.ANTICIPO].monto == Decimal("6000.00")
    assert cobros[TipoCobro.SALDO].monto == Decimal("6000.00")

    await servicio.registrar_anticipo_capturado(
        s, pedido_id=pedido.id, referencia_pasarela="ant-7", ahora=T0
    )
    assert (await _recargar(s, Consulta, consulta.id)).estado is (
        EstadoConsulta.CONVERTIDA
    )
    await servicio.iniciar_trabajo(s, pedido_id=pedido.id)
    media = await _media(s, artista)
    await servicio.entregar_vista_previa(
        s,
        pedido_id=pedido.id,
        media_asset_id=media.id,
        nota="Primera version",
        bucket_publico=settings.BUCKET_MEDIOS,
    )
    # D24: entregar no cambia el estado; lo cambia el saldo autorizado
    assert (await _recargar(s, Pedido, pedido.id)).estado is EstadoPedido.EN_PROCESO
    await servicio.registrar_saldo_autorizado(
        s,
        pedido_id=pedido.id,
        referencia_pasarela="sal-7",
        autorizado_hasta=T0 + timedelta(days=6),
        ahora=T0 + timedelta(days=1),
    )
    assert (await _recargar(s, Pedido, pedido.id)).estado is (
        EstadoPedido.VISTA_PREVIA_ENTREGADA
    )
    assert (await _cobros(s, pedido))[TipoCobro.SALDO].estado is (
        EstadoCobro.AUTORIZADO
    )
    captura = T0 + timedelta(days=2)
    await servicio.registrar_saldo_capturado(
        s, pedido_id=pedido.id, ahora=captura, politicas=POLITICAS
    )
    pedido = await _recargar(s, Pedido, pedido.id)
    assert pedido.estado is EstadoPedido.SALDO_PAGADO
    assert pedido.disputable_hasta == captura + timedelta(days=7)

    # En el borde exacto la ventana sigue abierta
    assert await servicio.completar_vencidos(s, ahora=pedido.disputable_hasta) == 0
    vencida = pedido.disputable_hasta + timedelta(seconds=1)
    assert await servicio.completar_vencidos(s, ahora=vencida) == 1

    pedido = await _recargar(s, Pedido, pedido.id)
    consulta = await _recargar(s, Consulta, consulta.id)
    cobros = await _cobros(s, pedido)
    assert pedido.estado is EstadoPedido.COMPLETADO
    assert consulta.estado is EstadoConsulta.CONVERTIDA
    assert {c.estado for c in cobros.values()} == {EstadoCobro.CAPTURADO}
    assert sum(c.monto for c in cobros.values()) == pedido.monto_total


# 8. Obra disponible y el indice parcial


async def test_08_una_obra_no_admite_dos_pedidos_vivos(async_session):
    s = async_session
    artista = await _perfil(s)
    obra = await _obra(s, artista)
    primero = await servicio.crear_pedido_obra_disponible(
        s,
        obra_id=obra.id,
        cliente_id=(await _perfil(s)).id,
        pasarela=PASARELA,
        politicas=POLITICAS,
    )
    consulta = await _recargar(s, Consulta, primero.consulta_id)
    assert consulta.estado is EstadoConsulta.CONVERTIDA
    assert primero.anticipo_porcentaje is None
    cobros = await _cobros(s, primero)
    assert list(cobros) == [TipoCobro.TOTAL]
    assert cobros[TipoCobro.TOTAL].monto == obra.precio

    otro_cliente = await _perfil(s)
    with pytest.raises(ObraNoDisponible):
        await servicio.crear_pedido_obra_disponible(
            s,
            obra_id=obra.id,
            cliente_id=otro_cliente.id,
            pasarela=PASARELA,
            politicas=POLITICAS,
        )

    # La transaccion sigue viva: el savepoint aislo el choque
    await servicio.rechazar_pedido(s, pedido_id=primero.id)
    assert (await _recargar(s, Consulta, consulta.id)).estado is (
        EstadoConsulta.DESCARTADA
    )
    segundo = await servicio.crear_pedido_obra_disponible(
        s,
        obra_id=obra.id,
        cliente_id=otro_cliente.id,
        pasarela=PASARELA,
        politicas=POLITICAS,
    )
    assert segundo.estado is EstadoPedido.COTIZADO
    assert (await _recargar(s, Obra, obra.id)).estado is EstadoObra.DISPONIBLE


async def test_08_obra_pasa_a_vendida_solo_al_despachar(async_session):
    s = async_session
    artista, cliente = await _perfil(s), await _perfil(s)
    obra = await _obra(s, artista)
    pedido = await servicio.crear_pedido_obra_disponible(
        s,
        obra_id=obra.id,
        cliente_id=cliente.id,
        pasarela=PASARELA,
        politicas=POLITICAS,
    )
    await servicio.confirmar_obra(
        s,
        pedido_id=pedido.id,
        referencia_pasarela="tot-8",
        autorizado_hasta=T0 + timedelta(days=7),
        ahora=T0,
    )
    assert (await _recargar(s, Obra, obra.id)).estado is EstadoObra.DISPONIBLE
    await servicio.registrar_despacho(
        s, pedido_id=pedido.id, guia_envio="CR123", ahora=T0, politicas=POLITICAS
    )
    pedido = await _recargar(s, Pedido, pedido.id)
    assert (await _recargar(s, Obra, obra.id)).estado is EstadoObra.VENDIDA
    assert pedido.estado is EstadoPedido.SALDO_PAGADO
    assert pedido.disputable_hasta == T0 + timedelta(days=7)
    assert (await _cobros(s, pedido))[TipoCobro.TOTAL].estado is (EstadoCobro.CAPTURADO)

    with pytest.raises(ActorNoAutorizado):
        await servicio.crear_pedido_obra_disponible(
            s,
            obra_id=(await _obra(s, artista)).id,
            cliente_id=artista.id,
            pasarela=PASARELA,
            politicas=POLITICAS,
        )


# 9. Atomicidad


async def test_09_si_el_cobro_falla_el_pedido_no_cambia(async_session):
    s = async_session
    ocupado = await _encargo_cotizado(s)
    await servicio.registrar_anticipo_capturado(
        s, pedido_id=ocupado.id, referencia_pasarela="ref-duplicada", ahora=T0
    )
    pedido = await _encargo_cotizado(s)
    # El rollback del savepoint expira los objetos: se guarda el id antes
    pedido_id = pedido.id

    with pytest.raises(IntegrityError):
        async with s.begin_nested():
            await servicio.registrar_anticipo_capturado(
                s, pedido_id=pedido_id, referencia_pasarela="ref-duplicada", ahora=T0
            )

    pedido = await _recargar(s, Pedido, pedido_id)
    anticipo = (await _cobros(s, pedido))[TipoCobro.ANTICIPO]
    consulta = await _recargar(s, Consulta, pedido.consulta_id)
    assert pedido.estado is EstadoPedido.COTIZADO
    assert anticipo.estado is EstadoCobro.PENDIENTE
    assert anticipo.referencia_pasarela is None
    assert consulta.estado is EstadoConsulta.COTIZADA


# 10. Disputa y su ventana


async def test_10_disputa_solo_dentro_de_la_ventana(async_session):
    s = async_session
    pedido = await _encargo_pagado(s, captura=T0)
    limite = pedido.disputable_hasta

    with pytest.raises(FueraDePlazo):
        await servicio.abrir_disputa(
            s,
            pedido_id=pedido.id,
            actor_id=pedido.cliente_id,
            motivo="No se parece",
            ahora=limite + timedelta(seconds=1),
        )
    with pytest.raises(ActorNoAutorizado):
        await servicio.abrir_disputa(
            s,
            pedido_id=pedido.id,
            actor_id=(await _perfil(s)).id,
            motivo="Metiche",
            ahora=limite,
        )
    assert await s.scalar(select(Disputa).where(Disputa.pedido_id == pedido.id)) is (
        None
    )

    disputa = await servicio.abrir_disputa(
        s,
        pedido_id=pedido.id,
        actor_id=pedido.cliente_id,
        motivo="No se parece",
        ahora=limite,
    )
    fila = await s.scalar(select(Disputa).where(Disputa.pedido_id == pedido.id))
    assert fila is not None
    assert fila.id == disputa.id
    assert fila.estado is EstadoDisputa.ABIERTA
    assert (await _recargar(s, Pedido, pedido.id)).estado is EstadoPedido.EN_DISPUTA


async def test_10_moderacion_resuelve_y_puede_devolver_el_anticipo(async_session):
    s = async_session
    pedido = await _encargo_pagado(s, captura=T0)
    await servicio.abrir_disputa(
        s,
        pedido_id=pedido.id,
        actor_id=pedido.cliente_id,
        motivo="Incumplio",
        ahora=T0,
    )
    admin = await _perfil(s, rol=RolPerfil.ADMIN)
    cobros = await _cobros(s, pedido)
    anticipo, saldo = cobros[TipoCobro.ANTICIPO], cobros[TipoCobro.SALDO]
    hechos = HechosPasarela(
        reembolsos={anticipo.id: anticipo.monto, saldo.id: Decimal("1000.00")}
    )

    with pytest.raises(ActorNoAutorizado):
        await servicio.resolver_disputa(
            s,
            pedido_id=pedido.id,
            destino=EstadoPedido.CANCELADO,
            resolucion="x",
            admin_id=pedido.cliente_id,
            hechos=hechos,
            ahora=T0,
        )

    disputa = await servicio.resolver_disputa(
        s,
        pedido_id=pedido.id,
        destino=EstadoPedido.CANCELADO,
        resolucion="El artista no entrego lo acordado",
        admin_id=admin.id,
        hechos=hechos,
        ahora=T0 + timedelta(days=1),
    )
    assert disputa.estado is EstadoDisputa.RESUELTA
    assert disputa.resuelta_por_id == admin.id
    cobros = await _cobros(s, pedido)
    assert cobros[TipoCobro.ANTICIPO].estado is EstadoCobro.REEMBOLSADO
    assert cobros[TipoCobro.ANTICIPO].monto_reembolsado == anticipo.monto
    assert cobros[TipoCobro.SALDO].monto_reembolsado == Decimal("1000.00")
    assert (await _recargar(s, Pedido, pedido.id)).estado is EstadoPedido.CANCELADO


# 11. Vencimientos


async def test_11_completar_vencidos_solo_toca_ventanas_vencidas(async_session):
    s = async_session
    viejo = await _encargo_pagado(s, captura=T0)
    reciente = await _encargo_pagado(s, captura=T0 + timedelta(days=5))
    en_disputa = await _encargo_pagado(s, captura=T0)
    await servicio.abrir_disputa(
        s,
        pedido_id=en_disputa.id,
        actor_id=en_disputa.artista_id,
        motivo="Impago",
        ahora=T0,
    )

    corte = T0 + timedelta(days=7, seconds=1)
    assert await servicio.completar_vencidos(s, ahora=corte) == 1

    estados = {
        p.id: (await _recargar(s, Pedido, p.id)).estado
        for p in (viejo, reciente, en_disputa)
    }
    assert estados == {
        viejo.id: EstadoPedido.COMPLETADO,
        reciente.id: EstadoPedido.SALDO_PAGADO,
        en_disputa.id: EstadoPedido.EN_DISPUTA,
    }
    assert await servicio.completar_vencidos(s, ahora=corte) == 0


# 12. Tarifa congelada


async def test_12_la_tarifa_queda_congelada(async_session):
    s = async_session
    artista = await _perfil(s, plan=PlanArtista.TALLER)
    pedido = await _encargo_cotizado(s, artista=artista)
    assert pedido.tarifa_porcentaje == POLITICAS.tarifa_taller_porcentaje

    artista.plan = PlanArtista.ESTUDIO
    await s.flush()

    pedido = await _recargar(s, Pedido, pedido.id)
    assert pedido.tarifa_porcentaje == POLITICAS.tarifa_taller_porcentaje
    nuevo = await _encargo_cotizado(s, artista=artista)
    assert nuevo.tarifa_porcentaje == POLITICAS.tarifa_estudio_porcentaje


# Complementarias: cancelacion con hechos de la pasarela


async def test_cliente_cancela_encargo_y_conserva_el_anticipo(async_session):
    s = async_session
    pedido = await _encargo_cotizado(s)
    await servicio.registrar_anticipo_capturado(
        s, pedido_id=pedido.id, referencia_pasarela="ant-c", ahora=T0
    )
    plan = await servicio.planear_cancelacion(
        s,
        pedido_id=pedido.id,
        actor_id=pedido.cliente_id,
        ahora=T0,
        politicas=POLITICAS,
    )
    assert plan.reembolsos == {}
    assert plan.liberaciones == set()

    with pytest.raises(HechosInconsistentes):
        await servicio.cancelar_pedido(
            s,
            pedido_id=pedido.id,
            actor_id=pedido.cliente_id,
            hechos=HechosPasarela(reembolsos={uuid.uuid4(): Decimal("1")}),
            ahora=T0,
            politicas=POLITICAS,
        )

    await servicio.cancelar_pedido(
        s,
        pedido_id=pedido.id,
        actor_id=pedido.cliente_id,
        hechos=HechosPasarela(),
        ahora=T0,
        politicas=POLITICAS,
    )
    cobros = await _cobros(s, pedido)
    assert cobros[TipoCobro.ANTICIPO].estado is EstadoCobro.CAPTURADO
    assert cobros[TipoCobro.SALDO].estado is EstadoCobro.CANCELADO
    assert (await _recargar(s, Pedido, pedido.id)).estado is EstadoPedido.CANCELADO


async def test_cliente_cancela_evento_con_reembolso_parcial(async_session):
    s = async_session
    artista, cliente = await _perfil(s), await _perfil(s)
    consulta = await _consulta(s, cliente, artista)
    fecha = T0 + timedelta(days=20)
    pedido = await servicio.crear_pedido_desde_cotizacion(
        s,
        consulta_id=consulta.id,
        tipo=TipoPedido.EVENTO,
        descripcion="Mural en vivo",
        monto_total=Decimal("40000.00"),
        anticipo_porcentaje=Decimal("30"),
        fecha_evento=fecha,
        lugar_evento="San Jose",
        pasarela=PASARELA,
        ahora=T0,
        politicas=POLITICAS,
    )
    await servicio.registrar_anticipo_capturado(
        s, pedido_id=pedido.id, referencia_pasarela="ev-a", ahora=T0
    )
    await servicio.registrar_saldo_capturado(
        s,
        pedido_id=pedido.id,
        ahora=T0,
        politicas=POLITICAS,
        referencia_pasarela="ev-s",
    )
    pedido = await _recargar(s, Pedido, pedido.id)
    assert pedido.disputable_hasta == fecha + timedelta(days=7)

    plan = await servicio.planear_cancelacion(
        s, pedido_id=pedido.id, actor_id=cliente.id, ahora=T0, politicas=POLITICAS
    )
    cobros = await _cobros(s, pedido)
    esperado = {
        cobros[TipoCobro.ANTICIPO].id: Decimal("6000.00"),
        cobros[TipoCobro.SALDO].id: Decimal("14000.00"),
    }
    assert plan.reembolsos == esperado
    await servicio.cancelar_pedido(
        s,
        pedido_id=pedido.id,
        actor_id=cliente.id,
        hechos=HechosPasarela(reembolsos=esperado),
        ahora=T0,
        politicas=POLITICAS,
    )
    cobros = await _cobros(s, pedido)
    assert {c.estado for c in cobros.values()} == {EstadoCobro.REEMBOLSADO}
    assert sum(c.monto_reembolsado for c in cobros.values()) == Decimal("20000.00")


# Lote 8b: vista previa en dos pasos (D24) y orden de bloqueos


async def _encargo_en_proceso(session) -> tuple[Pedido, Profile]:
    pedido = await _encargo_cotizado(session)
    await servicio.registrar_anticipo_capturado(
        session, pedido_id=pedido.id, referencia_pasarela=f"a{pedido.id}", ahora=T0
    )
    await servicio.iniciar_trabajo(session, pedido_id=pedido.id)
    return pedido, await _recargar(session, Profile, pedido.artista_id)


async def test_8b_02_entregar_vista_previa_exige_un_medio_valido(async_session):
    s = async_session
    pedido, artista = await _encargo_en_proceso(s)

    async def _entregar(media_id):
        return await servicio.entregar_vista_previa(
            s,
            pedido_id=pedido.id,
            media_asset_id=media_id,
            bucket_publico=settings.BUCKET_MEDIOS,
        )

    ajeno = await _media(s, await _perfil(s))
    with pytest.raises(ResourceNotFound):
        await _entregar(ajeno.id)
    with pytest.raises(ResourceNotFound):
        await _entregar(uuid.uuid4())
    with pytest.raises(ReglaDeNegocioViolada):
        await _entregar((await _media(s, artista, subido=False)).id)
    with pytest.raises(ReglaDeNegocioViolada):
        await _entregar((await _media(s, artista, deleted_at=T0)).id)
    obra = await _obra(s, artista)
    with pytest.raises(ReglaDeNegocioViolada):
        await _entregar((await _media(s, artista, obra_id=obra.id)).id)

    usado = await _media(s, artista)
    await _entregar(usado.id)
    with pytest.raises(ReglaDeNegocioViolada):
        await _entregar(usado.id)
    # Una por revision: otra vista previa con otro medio sigue en proceso
    await _entregar((await _media(s, artista)).id)
    assert (await _recargar(s, Pedido, pedido.id)).estado is EstadoPedido.EN_PROCESO
    previas = await s.scalars(
        select(Entregable).where(Entregable.pedido_id == pedido.id)
    )
    assert len(list(previas)) == 2


async def test_8b_02_saldo_autorizado_sin_vista_previa(async_session):
    s = async_session
    pedido, _ = await _encargo_en_proceso(s)
    with pytest.raises(ReglaDeNegocioViolada):
        await servicio.registrar_saldo_autorizado(
            s,
            pedido_id=pedido.id,
            referencia_pasarela="sin-previa",
            autorizado_hasta=T0 + timedelta(days=5),
            ahora=T0,
        )
    saldo = (await _cobros(s, pedido))[TipoCobro.SALDO]
    assert saldo.estado is EstadoCobro.PENDIENTE
    assert saldo.referencia_pasarela is None


async def test_8b_03_cotizar_bloquea_el_perfil_antes_que_la_consulta(
    async_session, test_db
):
    s = async_session
    artista, cliente = await _perfil(s), await _perfil(s)
    consulta = await _consulta(s, cliente, artista)
    bloqueos: list[str] = []

    def _anotar(_conn, _cursor, sentencia, *_args) -> None:
        if "FOR UPDATE" in sentencia:
            bloqueos.append(sentencia)

    event.listen(test_db.sync_engine, "before_cursor_execute", _anotar)
    try:
        await servicio.crear_pedido_desde_cotizacion(
            s,
            consulta_id=consulta.id,
            tipo=TipoPedido.ENCARGO,
            descripcion="Retrato",
            monto_total=Decimal("10000.00"),
            pasarela=PASARELA,
            ahora=T0,
            politicas=POLITICAS,
        )
    finally:
        event.remove(test_db.sync_engine, "before_cursor_execute", _anotar)

    assert len(bloqueos) >= 2
    assert "FROM profiles" in bloqueos[0]
    assert "FROM consultas" in bloqueos[1]
