"""Endpoints de pedidos y cobros.

Todos piden token. La API pasa el reloj, las politicas, la url de retorno y el
nombre de la pasarela, y confirma la transaccion despues del servicio.

Un pago rechazado responde 200 con `resultado` igual a `rechazado`: es un
resultado normal, no un error del servidor. Con `requiere_accion`, la app abre
`url_autenticacion` y al volver llama a `POST /cobros/{cobro_id}/verificar`.
"""

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Response, status

from src.api.deps import AlmacenamientoDeMedios, Pasarela, Sesion, Usuario
from src.api.paginacion import Pagina, Paginacion
from src.core.config import settings
from src.domain.enums import EstadoPedido
from src.domain.pedidos import Rol
from src.domain.politicas import PoliticasPedido
from src.schemas.medios import SolicitudSubida, SubidaRespuesta
from src.schemas.pedidos import (
    DatosCotizacion,
    DescargaRespuesta,
    Despacho,
    NuevaCotizacion,
    NuevaDisputa,
    NuevaVistaPrevia,
    NuevoFinal,
    Pago,
    PedidoRespuesta,
    ResultadoPagoRespuesta,
)
from src.services import contratacion
from src.services import pedidos as servicio
from src.services.contratacion import Resultado

router = APIRouter(tags=["pedidos"])

CREADO = status.HTTP_201_CREATED


def _ahora() -> datetime:
    return datetime.now(UTC)


def _politicas() -> PoliticasPedido:
    return PoliticasPedido.desde_config(settings)


def _nombre_pasarela() -> str:
    return settings.PASARELA.strip().lower()


# Cotizacion


@router.post("/consultas/{consulta_id}/cotizacion", status_code=CREADO)
async def cotizar(
    consulta_id: uuid.UUID,
    datos: NuevaCotizacion,
    usuario: Usuario,
    session: Sesion,
    almacenamiento: AlmacenamientoDeMedios,
) -> PedidoRespuesta:
    detalle = await contratacion.cotizar(
        session,
        usuario,
        consulta_id,
        tipo=datos.tipo,
        descripcion=datos.descripcion,
        monto_total=datos.monto_total,
        anticipo_porcentaje=datos.anticipo_porcentaje,
        fecha_evento=datos.fecha_evento,
        lugar_evento=datos.lugar_evento,
        fecha_entrega_estimada=datos.fecha_entrega_estimada,
        ahora=_ahora(),
        politicas=_politicas(),
        nombre_pasarela=_nombre_pasarela(),
    )
    await session.commit()
    return PedidoRespuesta.desde(detalle, almacenamiento)


@router.put("/pedidos/{pedido_id}/cotizacion")
async def actualizar_cotizacion(
    pedido_id: uuid.UUID,
    datos: DatosCotizacion,
    usuario: Usuario,
    session: Sesion,
    almacenamiento: AlmacenamientoDeMedios,
) -> PedidoRespuesta:
    """Contraoferta: reemplaza la cotizacion vigente del mismo pedido."""
    detalle = await contratacion.actualizar_cotizacion(
        session,
        usuario,
        pedido_id,
        descripcion=datos.descripcion,
        monto_total=datos.monto_total,
        anticipo_porcentaje=datos.anticipo_porcentaje,
        fecha_evento=datos.fecha_evento,
        lugar_evento=datos.lugar_evento,
        fecha_entrega_estimada=datos.fecha_entrega_estimada,
        ahora=_ahora(),
        politicas=_politicas(),
    )
    await session.commit()
    return PedidoRespuesta.desde(detalle, almacenamiento)


@router.post("/pedidos/{pedido_id}/rechazar")
async def rechazar(
    pedido_id: uuid.UUID,
    usuario: Usuario,
    session: Sesion,
    pasarela: Pasarela,
    almacenamiento: AlmacenamientoDeMedios,
) -> PedidoRespuesta:
    detalle = await contratacion.rechazar(
        session, pasarela, usuario, pedido_id, ahora=_ahora(), politicas=_politicas()
    )
    await session.commit()
    return PedidoRespuesta.desde(detalle, almacenamiento)


# Encargo y evento


@router.post("/pedidos/{pedido_id}/anticipo")
async def pagar_anticipo(
    pedido_id: uuid.UUID,
    datos: Pago,
    usuario: Usuario,
    session: Sesion,
    pasarela: Pasarela,
    almacenamiento: AlmacenamientoDeMedios,
) -> ResultadoPagoRespuesta:
    resultado = await contratacion.pagar_anticipo(
        session,
        pasarela,
        usuario,
        pedido_id,
        datos.metodo_pago_id,
        ahora=_ahora(),
        politicas=_politicas(),
        url_retorno=settings.URL_RETORNO_PAGO,
    )
    await session.commit()
    return ResultadoPagoRespuesta.desde(resultado, almacenamiento)


@router.post("/pedidos/{pedido_id}/iniciar")
async def iniciar_trabajo(
    pedido_id: uuid.UUID,
    usuario: Usuario,
    session: Sesion,
    almacenamiento: AlmacenamientoDeMedios,
) -> PedidoRespuesta:
    detalle = await contratacion.iniciar_trabajo(session, usuario, pedido_id)
    await session.commit()
    return PedidoRespuesta.desde(detalle, almacenamiento)


@router.post("/pedidos/{pedido_id}/vistas-previas", status_code=CREADO)
async def entregar_vista_previa(
    pedido_id: uuid.UUID,
    datos: NuevaVistaPrevia,
    usuario: Usuario,
    session: Sesion,
    almacenamiento: AlmacenamientoDeMedios,
) -> PedidoRespuesta:
    """El pedido sigue en proceso hasta que el cliente autoriza el saldo (D24)."""
    detalle = await contratacion.entregar_vista_previa(
        session,
        usuario,
        pedido_id,
        datos.medio_id,
        datos.nota,
        bucket_publico=settings.BUCKET_MEDIOS,
    )
    await session.commit()
    return PedidoRespuesta.desde(detalle, almacenamiento)


@router.post("/pedidos/{pedido_id}/saldo")
async def pagar_saldo(
    pedido_id: uuid.UUID,
    datos: Pago,
    usuario: Usuario,
    session: Sesion,
    pasarela: Pasarela,
    almacenamiento: AlmacenamientoDeMedios,
) -> ResultadoPagoRespuesta:
    """Encargo: autoriza el saldo al ver la vista previa. Evento: lo cobra."""
    resultado = await contratacion.pagar_saldo(
        session,
        pasarela,
        usuario,
        pedido_id,
        datos.metodo_pago_id,
        ahora=_ahora(),
        politicas=_politicas(),
        url_retorno=settings.URL_RETORNO_PAGO,
    )
    await session.commit()
    return ResultadoPagoRespuesta.desde(resultado, almacenamiento)


@router.post("/pedidos/{pedido_id}/aprobar")
async def aprobar(
    pedido_id: uuid.UUID,
    usuario: Usuario,
    session: Sesion,
    pasarela: Pasarela,
    almacenamiento: AlmacenamientoDeMedios,
) -> PedidoRespuesta:
    detalle = await contratacion.aprobar(
        session, pasarela, usuario, pedido_id, ahora=_ahora(), politicas=_politicas()
    )
    await session.commit()
    return PedidoRespuesta.desde(detalle, almacenamiento)


# Archivo final del encargo, en el bucket privado


@router.post("/pedidos/{pedido_id}/entregables/subida", status_code=CREADO)
async def solicitar_subida_final(
    pedido_id: uuid.UUID,
    datos: SolicitudSubida,
    usuario: Usuario,
    session: Sesion,
    almacenamiento: AlmacenamientoDeMedios,
) -> SubidaRespuesta:
    """Se confirma como cualquier medio, con POST /medios/{medio_id}/confirmar."""
    medio, subida = await contratacion.solicitar_subida_final(
        session,
        almacenamiento,
        usuario,
        pedido_id,
        datos.content_type,
        datos.tamano_bytes,
        bucket_privado=settings.BUCKET_ENTREGABLES,
        maximo_pendientes=settings.MEDIOS_PENDIENTES_MAXIMOS,
    )
    await session.commit()
    return SubidaRespuesta.desde(medio, subida)


@router.post("/pedidos/{pedido_id}/entregables/final", status_code=CREADO)
async def entregar_final(
    pedido_id: uuid.UUID,
    datos: NuevoFinal,
    usuario: Usuario,
    session: Sesion,
    almacenamiento: AlmacenamientoDeMedios,
) -> PedidoRespuesta:
    detalle = await contratacion.entregar_final(
        session,
        usuario,
        pedido_id,
        datos.medio_id,
        datos.nota,
        bucket_privado=settings.BUCKET_ENTREGABLES,
    )
    await session.commit()
    return PedidoRespuesta.desde(detalle, almacenamiento)


@router.get("/pedidos/{pedido_id}/entregables/{entregable_id}/descarga")
async def descargar_entregable(
    pedido_id: uuid.UUID,
    entregable_id: uuid.UUID,
    usuario: Usuario,
    session: Sesion,
    almacenamiento: AlmacenamientoDeMedios,
    response: Response,
) -> DescargaRespuesta:
    """URL firmada de corta duracion. Solo el cliente o el artista del pedido."""
    descarga = await contratacion.descargar_entregable(
        session,
        almacenamiento,
        usuario,
        pedido_id,
        entregable_id,
        segundos=settings.DESCARGA_FIRMADA_SEGUNDOS,
    )
    # Ningun intermediario guarda la URL firmada
    response.headers["Cache-Control"] = "no-store"
    return DescargaRespuesta.desde(descarga)


# Obra disponible


@router.post("/obras/{obra_id}/la-quiero", status_code=CREADO)
async def la_quiero(
    obra_id: uuid.UUID,
    datos: Pago,
    usuario: Usuario,
    session: Sesion,
    pasarela: Pasarela,
    almacenamiento: AlmacenamientoDeMedios,
    response: Response,
) -> ResultadoPagoRespuesta:
    """201 si se creo el pedido; 200 si la pasarela rechazo y no quedo nada."""
    resultado = await contratacion.la_quiero(
        session,
        pasarela,
        usuario,
        obra_id,
        datos.metodo_pago_id,
        ahora=_ahora(),
        politicas=_politicas(),
        url_retorno=settings.URL_RETORNO_PAGO,
        nombre_pasarela=_nombre_pasarela(),
    )
    if resultado.resultado is Resultado.RECHAZADO:
        # Sin pedido ni consulta: la obra sigue libre para otro cliente
        await session.rollback()
        response.status_code = status.HTTP_200_OK
    else:
        await session.commit()
    return ResultadoPagoRespuesta.desde(resultado, almacenamiento)


@router.post("/pedidos/{pedido_id}/despacho")
async def despachar(
    pedido_id: uuid.UUID,
    datos: Despacho,
    usuario: Usuario,
    session: Sesion,
    pasarela: Pasarela,
    almacenamiento: AlmacenamientoDeMedios,
) -> PedidoRespuesta:
    detalle = await contratacion.despachar(
        session,
        pasarela,
        usuario,
        pedido_id,
        datos.guia_envio,
        ahora=_ahora(),
        politicas=_politicas(),
    )
    await session.commit()
    return PedidoRespuesta.desde(detalle, almacenamiento)


# Cierre


@router.post("/pedidos/{pedido_id}/cancelar")
async def cancelar(
    pedido_id: uuid.UUID,
    usuario: Usuario,
    session: Sesion,
    pasarela: Pasarela,
    almacenamiento: AlmacenamientoDeMedios,
) -> PedidoRespuesta:
    detalle = await contratacion.cancelar(
        session, pasarela, usuario, pedido_id, ahora=_ahora(), politicas=_politicas()
    )
    await session.commit()
    return PedidoRespuesta.desde(detalle, almacenamiento)


@router.post("/pedidos/{pedido_id}/disputa", status_code=CREADO)
async def abrir_disputa(
    pedido_id: uuid.UUID,
    datos: NuevaDisputa,
    usuario: Usuario,
    session: Sesion,
    almacenamiento: AlmacenamientoDeMedios,
) -> PedidoRespuesta:
    detalle = await contratacion.abrir_disputa(
        session, usuario, pedido_id, datos.motivo, ahora=_ahora()
    )
    await session.commit()
    return PedidoRespuesta.desde(detalle, almacenamiento)


# Cobros


@router.post("/cobros/{cobro_id}/verificar")
async def verificar_cobro(
    cobro_id: uuid.UUID,
    usuario: Usuario,
    session: Sesion,
    pasarela: Pasarela,
    almacenamiento: AlmacenamientoDeMedios,
) -> ResultadoPagoRespuesta:
    """POST porque puede registrar el pago que la pasarela ya confirmo."""
    resultado = await contratacion.verificar_cobro(
        session, pasarela, usuario, cobro_id, _ahora(), _politicas()
    )
    await session.commit()
    return ResultadoPagoRespuesta.desde(resultado, almacenamiento)


# Lectura


@router.get("/pedidos")
async def listar(
    usuario: Usuario,
    session: Sesion,
    paginacion: Paginacion,
    almacenamiento: AlmacenamientoDeMedios,
    como: Rol | None = None,
    estado: EstadoPedido | None = None,
    consulta_id: uuid.UUID | None = None,
) -> Pagina[PedidoRespuesta]:
    """Del mas nuevo al mas viejo."""
    detalles, siguiente = await servicio.listar(
        session, usuario, como, estado, consulta_id, paginacion
    )
    return Pagina(
        items=[PedidoRespuesta.desde(d, almacenamiento) for d in detalles],
        siguiente_cursor=siguiente,
    )


@router.get("/pedidos/{pedido_id}")
async def detalle(
    pedido_id: uuid.UUID,
    usuario: Usuario,
    session: Sesion,
    almacenamiento: AlmacenamientoDeMedios,
) -> PedidoRespuesta:
    return PedidoRespuesta.desde(
        await servicio.detalle(session, usuario, pedido_id), almacenamiento
    )
