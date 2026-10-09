"""Dominio de pedidos, sin base de datos."""

import uuid
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from src.core.config import Settings
from src.core.exceptions import (
    ActorNoAutorizado,
    CotizacionInvalida,
    FueraDePlazo,
    HechosInconsistentes,
    InvalidStateTransition,
    ReglaDeNegocioViolada,
)
from src.domain import pedidos as d
from src.domain.pedidos import Accion, HechosPasarela, Rol
from src.domain.politicas import PoliticasPedido
from src.models import (
    EstadoCobro,
    EstadoPedido,
    PlanArtista,
    TipoCobro,
    TipoPedido,
)

E = EstadoPedido
T = TipoPedido
AHORA = datetime(2026, 10, 1, 12, 0, tzinfo=UTC)

POLITICAS = PoliticasPedido(
    anticipo_porcentaje_minimo=Decimal("30"),
    anticipo_porcentaje_maximo=Decimal("50"),
    anticipo_porcentaje_defecto=Decimal("50"),
    ventana_disputa=timedelta(days=7),
    cancelacion_evento_total=timedelta(days=30),
    cancelacion_evento_parcial=timedelta(days=7),
    cancelacion_evento_porcentaje_parcial=Decimal("50"),
    monto_minimo_pedido=Decimal("2500.00"),
    tarifa_taller_porcentaje=Decimal("8"),
    tarifa_estudio_porcentaje=Decimal("5"),
    vigencia_autorizacion_supuesta=timedelta(days=5),
    plazo_reautorizacion_saldo=timedelta(days=7),
    abandono_3ds=timedelta(minutes=30),
)


@dataclass
class CobroFalso:
    tipo: TipoCobro
    estado: EstadoCobro
    monto: Decimal
    monto_reembolsado: Decimal = Decimal("0")
    id: uuid.UUID = field(default_factory=uuid.uuid4)


# 1. Transiciones

# Copia independiente de la tabla del prompt, para no probar el dominio contra si mismo
TODOS = (T.ENCARGO, T.EVENTO, T.OBRA_DISPONIBLE)
TABLA_ESPERADA = [
    (TODOS, E.COTIZADO, E.RECHAZADO),
    ((T.ENCARGO, T.EVENTO), E.COTIZADO, E.ANTICIPO_PAGADO),
    ((T.ENCARGO,), E.ANTICIPO_PAGADO, E.EN_PROCESO),
    ((T.ENCARGO,), E.EN_PROCESO, E.VISTA_PREVIA_ENTREGADA),
    ((T.ENCARGO,), E.VISTA_PREVIA_ENTREGADA, E.SALDO_PAGADO),
    ((T.EVENTO,), E.ANTICIPO_PAGADO, E.SALDO_PAGADO),
    ((T.OBRA_DISPONIBLE,), E.COTIZADO, E.EN_PROCESO),
    ((T.OBRA_DISPONIBLE,), E.EN_PROCESO, E.SALDO_PAGADO),
    (TODOS, E.SALDO_PAGADO, E.COMPLETADO),
    ((T.ENCARGO,), E.VISTA_PREVIA_ENTREGADA, E.EN_DISPUTA),
    (TODOS, E.SALDO_PAGADO, E.EN_DISPUTA),
    ((T.ENCARGO,), E.ANTICIPO_PAGADO, E.CANCELADO),
    ((T.ENCARGO,), E.EN_PROCESO, E.CANCELADO),
    ((T.ENCARGO,), E.VISTA_PREVIA_ENTREGADA, E.CANCELADO),
    ((T.EVENTO,), E.ANTICIPO_PAGADO, E.CANCELADO),
    ((T.EVENTO,), E.SALDO_PAGADO, E.CANCELADO),
    ((T.OBRA_DISPONIBLE,), E.EN_PROCESO, E.CANCELADO),
    (TODOS, E.EN_DISPUTA, E.COMPLETADO),
    (TODOS, E.EN_DISPUTA, E.CANCELADO),
]
PERMITIDAS = sorted(
    {(t, desde, hacia) for tipos, desde, hacia in TABLA_ESPERADA for t in tipos}
)


def test_01_tabla_de_transiciones_es_exactamente_la_del_negocio():
    assert set(PERMITIDAS) == d.TRANSICIONES_PEDIDO


@pytest.mark.parametrize(("tipo", "desde", "hacia"), PERMITIDAS)
def test_01_cada_transicion_de_la_tabla_se_acepta(tipo, desde, hacia):
    d.validar_transicion(tipo, desde, hacia)


PROHIBIDAS = [
    (T.ENCARGO, E.COTIZADO, E.SALDO_PAGADO),
    (T.OBRA_DISPONIBLE, E.COTIZADO, E.ANTICIPO_PAGADO),
    (T.EVENTO, E.ANTICIPO_PAGADO, E.VISTA_PREVIA_ENTREGADA),
    (T.OBRA_DISPONIBLE, E.EN_PROCESO, E.EN_DISPUTA),
    (T.EVENTO, E.COTIZADO, E.CANCELADO),
    *[(T.EVENTO, desde, E.EN_PROCESO) for desde in EstadoPedido],
    *[
        (tipo, desde, hacia)
        for tipo in TipoPedido
        for desde in (E.COMPLETADO, E.RECHAZADO, E.CANCELADO)
        for hacia in EstadoPedido
    ],
]


@pytest.mark.parametrize(("tipo", "desde", "hacia"), PROHIBIDAS)
def test_01_transiciones_prohibidas_levantan_error(tipo, desde, hacia):
    with pytest.raises(InvalidStateTransition):
        d.validar_transicion(tipo, desde, hacia)


def test_01_estados_terminales_no_tienen_salida():
    salidas = {desde for _, desde, _ in d.TRANSICIONES_PEDIDO}
    assert salidas.isdisjoint(d.ESTADOS_TERMINALES)
    assert {E.COMPLETADO, E.RECHAZADO, E.CANCELADO} == d.ESTADOS_TERMINALES


# 2. Dinero


@pytest.mark.parametrize(
    ("total", "porcentaje", "anticipo"),
    [
        ("10000.01", "33", "3300.00"),
        ("10000.03", "33.33", "3333.01"),
        ("2500.01", "30", "750.00"),
        ("9999.99", "45.55", "4555.00"),
        ("12345.67", "50", "6172.84"),
    ],
)
def test_02_anticipo_mas_saldo_da_el_total_exacto(total, porcentaje, anticipo):
    total, porcentaje = Decimal(total), Decimal(porcentaje)
    a, s = d.dividir_monto(total, porcentaje)
    assert a == Decimal(anticipo)
    assert a + s == total
    assert a.as_tuple().exponent == -2
    assert s.as_tuple().exponent == -2


def test_02_cotizacion_reparte_en_dos_cobros_que_suman_el_total():
    cot = d.cotizar(T.ENCARGO, Decimal("10000.01"), Decimal("33"), POLITICAS)
    montos = dict(cot.cobros)
    assert montos == {
        TipoCobro.ANTICIPO: Decimal("3300.00"),
        TipoCobro.SALDO: Decimal("6700.01"),
    }
    assert sum(montos.values()) == Decimal("10000.01")


def test_02_monto_minimo_y_tipos_de_dinero():
    with pytest.raises(CotizacionInvalida):
        d.cotizar(T.ENCARGO, Decimal("2499.99"), None, POLITICAS)
    with pytest.raises(CotizacionInvalida):
        d.cotizar(T.ENCARGO, Decimal("3000.001"), None, POLITICAS)
    with pytest.raises(TypeError):
        d.cotizar(T.ENCARGO, 3000.0, None, POLITICAS)
    cot = d.cotizar(T.OBRA_DISPONIBLE, Decimal("2500.00"), None, POLITICAS)
    assert cot.cobros == ((TipoCobro.TOTAL, Decimal("2500.00")),)


# 3. Porcentaje de anticipo


@pytest.mark.parametrize("porcentaje", ["29.99", "50.01", "0", "100"])
def test_03_anticipo_fuera_de_rango_se_rechaza(porcentaje):
    with pytest.raises(CotizacionInvalida):
        d.cotizar(T.EVENTO, Decimal("5000"), Decimal(porcentaje), POLITICAS)


@pytest.mark.parametrize("porcentaje", ["30", "42.5", "50"])
def test_03_anticipo_en_los_bordes_del_rango_se_acepta(porcentaje):
    cot = d.cotizar(T.ENCARGO, Decimal("5000"), Decimal(porcentaje), POLITICAS)
    assert cot.anticipo_porcentaje == Decimal(porcentaje)


def test_03_sin_porcentaje_se_usa_el_defecto():
    politicas = replace(POLITICAS, anticipo_porcentaje_defecto=Decimal("40"))
    cot = d.cotizar(T.ENCARGO, Decimal("5000"), None, politicas)
    assert cot.anticipo_porcentaje == Decimal("40")
    assert dict(cot.cobros)[TipoCobro.ANTICIPO] == Decimal("2000.00")


def test_03_obra_disponible_no_lleva_anticipo():
    assert d.resolver_porcentaje_anticipo(T.OBRA_DISPONIBLE, None, POLITICAS) is None
    with pytest.raises(CotizacionInvalida):
        d.cotizar(T.OBRA_DISPONIBLE, Decimal("5000"), Decimal("30"), POLITICAS)


# 4. Bordes de la cancelacion de eventos


@pytest.mark.parametrize(
    ("anticipacion", "porcentaje"),
    [
        (timedelta(days=30, seconds=1), Decimal("100")),
        (timedelta(days=30), Decimal("50")),
        (timedelta(days=7), Decimal("50")),
        (timedelta(days=6, hours=23), Decimal("0")),
    ],
    ids=["30d_y_1s_total", "30d_parcial", "7d_parcial", "6d23h_cero"],
)
def test_04_bordes_de_cancelacion_de_evento(anticipacion, porcentaje):
    fecha = AHORA + anticipacion
    assert d.porcentaje_reembolso_evento(fecha, AHORA, POLITICAS) == porcentaje

    anticipo = CobroFalso(TipoCobro.ANTICIPO, EstadoCobro.CAPTURADO, Decimal("3000"))
    saldo = CobroFalso(TipoCobro.SALDO, EstadoCobro.PENDIENTE, Decimal("3000"))
    plan = d.planear_cancelacion(
        T.EVENTO,
        E.ANTICIPO_PAGADO,
        Rol.CLIENTE,
        [anticipo, saldo],
        fecha,
        AHORA,
        POLITICAS,
    )
    esperado = d.porcentaje_de(Decimal("3000"), porcentaje)
    assert plan.reembolsos == ({anticipo.id: esperado} if esperado else {})
    assert plan.de(saldo.id).accion is Accion.CANCELAR


def test_04_evento_no_se_cancela_despues_de_su_fecha():
    anticipo = CobroFalso(TipoCobro.ANTICIPO, EstadoCobro.CAPTURADO, Decimal("3000"))
    with pytest.raises(FueraDePlazo):
        d.planear_cancelacion(
            T.EVENTO, E.SALDO_PAGADO, Rol.ARTISTA, [anticipo], AHORA, AHORA, POLITICAS
        )


# 5. Plan de cancelacion


def _encargo_con_anticipo(estado_saldo=EstadoCobro.PENDIENTE):
    return (
        CobroFalso(TipoCobro.ANTICIPO, EstadoCobro.CAPTURADO, Decimal("1500.00")),
        CobroFalso(TipoCobro.SALDO, estado_saldo, Decimal("1500.01")),
    )


def test_05_cliente_cancela_encargo_y_el_anticipo_se_conserva():
    anticipo, saldo = _encargo_con_anticipo(EstadoCobro.AUTORIZADO)
    plan = d.planear_cancelacion(
        T.ENCARGO,
        E.VISTA_PREVIA_ENTREGADA,
        Rol.CLIENTE,
        [anticipo, saldo],
        None,
        AHORA,
        POLITICAS,
    )
    assert plan.de(anticipo.id).accion is Accion.CONSERVAR
    assert plan.de(saldo.id).accion is Accion.LIBERAR_AUTORIZACION
    assert plan.reembolsos == {}


def test_05_artista_cancela_y_todo_se_devuelve():
    anticipo, saldo = _encargo_con_anticipo(EstadoCobro.PENDIENTE)
    plan = d.planear_cancelacion(
        T.ENCARGO,
        E.EN_PROCESO,
        Rol.ARTISTA,
        [anticipo, saldo],
        None,
        AHORA,
        POLITICAS,
    )
    assert plan.reembolsos == {anticipo.id: Decimal("1500.00")}
    assert plan.de(saldo.id).accion is Accion.CANCELAR


def test_05_artista_cancela_evento_pagado_y_devuelve_ambos_cobros():
    cobros = [
        CobroFalso(TipoCobro.ANTICIPO, EstadoCobro.CAPTURADO, Decimal("1500")),
        CobroFalso(TipoCobro.SALDO, EstadoCobro.CAPTURADO, Decimal("1500")),
    ]
    fecha = AHORA + timedelta(days=2)
    plan = d.planear_cancelacion(
        T.EVENTO, E.SALDO_PAGADO, Rol.ARTISTA, cobros, fecha, AHORA, POLITICAS
    )
    assert sum(plan.reembolsos.values()) == Decimal("3000")


def test_05_los_hechos_deben_seguir_el_plan():
    anticipo, saldo = _encargo_con_anticipo()
    plan = d.planear_cancelacion(
        T.ENCARGO,
        E.EN_PROCESO,
        Rol.ARTISTA,
        [anticipo, saldo],
        None,
        AHORA,
        POLITICAS,
    )
    d.verificar_hechos(plan, HechosPasarela(reembolsos={anticipo.id: Decimal("1500")}))
    with pytest.raises(HechosInconsistentes):
        d.verificar_hechos(plan, HechosPasarela(reembolsos={anticipo.id: Decimal("1")}))
    with pytest.raises(HechosInconsistentes):
        d.verificar_hechos(plan, HechosPasarela())


def test_05_cancelar_desde_cotizado_no_es_cancelacion():
    with pytest.raises(InvalidStateTransition):
        d.planear_cancelacion(
            T.ENCARGO, E.COTIZADO, Rol.CLIENTE, [], None, AHORA, POLITICAS
        )


# 6. Politicas configurables y ventana de disputa


def test_06_la_ventana_de_disputa_es_configurable():
    tres_dias = replace(POLITICAS, ventana_disputa=timedelta(days=3))
    normal = d.calcular_disputable_hasta(T.ENCARGO, AHORA, None, POLITICAS)
    corta = d.calcular_disputable_hasta(T.ENCARGO, AHORA, None, tres_dias)
    assert normal == AHORA + timedelta(days=7)
    assert corta == AHORA + timedelta(days=3)


def test_06_la_ventana_del_evento_corre_desde_su_fecha():
    fecha = AHORA + timedelta(days=20)
    hasta = d.calcular_disputable_hasta(T.EVENTO, AHORA, fecha, POLITICAS)
    assert hasta == fecha + timedelta(days=7)


def test_06_desde_config_toma_los_valores_de_la_configuracion():
    config = Settings(
        DATABASE_URL="postgresql+psycopg://u:p@h:5432/d",
        ALEMBIC_DATABASE_URL="postgresql+psycopg://u:p@h:5432/d",
        SUPABASE_URL="https://x.supabase.co",
        DIAS_VENTANA_DISPUTA=3,
        ANTICIPO_PORCENTAJE_DEFECTO=Decimal("35"),
    )
    politicas = PoliticasPedido.desde_config(config)
    assert politicas.ventana_disputa == timedelta(days=3)
    assert politicas.anticipo_porcentaje_defecto == Decimal("35")
    assert politicas.monto_minimo_pedido == Decimal("2500.00")


def test_06_politicas_incoherentes_se_rechazan():
    with pytest.raises(ValueError, match="El anticipo debe cumplir"):
        replace(POLITICAS, anticipo_porcentaje_defecto=Decimal("60"))
    with pytest.raises(ValueError, match="El plazo parcial no puede superar al total"):
        replace(POLITICAS, cancelacion_evento_parcial=timedelta(days=40))


# Complementarias: tarifa, actores, disputa y resolucion


def test_tarifa_segun_plan():
    assert d.tarifa_para_plan(PlanArtista.TALLER, POLITICAS) == Decimal("8")
    assert d.tarifa_para_plan(PlanArtista.ESTUDIO, POLITICAS) == Decimal("5")


def test_solo_cliente_o_artista_actuan_sobre_el_pedido():
    cliente, artista = uuid.uuid4(), uuid.uuid4()
    assert d.rol_en_pedido(cliente, cliente, artista) is Rol.CLIENTE
    assert d.rol_en_pedido(artista, cliente, artista) is Rol.ARTISTA
    with pytest.raises(ActorNoAutorizado):
        d.rol_en_pedido(uuid.uuid4(), cliente, artista)


def test_apertura_de_disputa_respeta_la_ventana():
    hasta = AHORA + timedelta(days=7)
    d.validar_apertura_disputa(T.ENCARGO, E.SALDO_PAGADO, hasta, hasta)
    d.validar_apertura_disputa(T.ENCARGO, E.VISTA_PREVIA_ENTREGADA, None, AHORA)
    with pytest.raises(FueraDePlazo):
        d.validar_apertura_disputa(
            T.ENCARGO, E.SALDO_PAGADO, hasta, hasta + timedelta(seconds=1)
        )
    with pytest.raises(InvalidStateTransition):
        d.validar_apertura_disputa(T.ENCARGO, E.EN_PROCESO, None, AHORA)


def test_resolucion_puede_devolver_el_anticipo():
    anticipo, saldo = _encargo_con_anticipo(EstadoCobro.AUTORIZADO)
    plan = d.planear_resolucion(
        T.ENCARGO,
        E.EN_DISPUTA,
        E.CANCELADO,
        [anticipo, saldo],
        {anticipo.id: Decimal("750.00")},
    )
    assert plan.reembolsos == {anticipo.id: Decimal("750.00")}
    assert plan.liberaciones == {saldo.id}

    completa = d.planear_resolucion(
        T.ENCARGO, E.EN_DISPUTA, E.COMPLETADO, [anticipo, saldo], {}
    )
    assert completa.capturas == {saldo.id}
    assert completa.de(anticipo.id).accion is Accion.CONSERVAR


def test_resolucion_rechaza_reembolsos_imposibles():
    anticipo, saldo = _encargo_con_anticipo(EstadoCobro.AUTORIZADO)
    for orden in (
        {anticipo.id: Decimal("1500.01")},
        {saldo.id: Decimal("10")},
        {uuid.uuid4(): Decimal("10")},
    ):
        with pytest.raises(ReglaDeNegocioViolada):
            d.planear_resolucion(
                T.ENCARGO, E.EN_DISPUTA, E.CANCELADO, [anticipo, saldo], orden
            )


def test_transiciones_de_cobro():
    d.validar_transicion_cobro(EstadoCobro.AUTORIZADO, EstadoCobro.CAPTURADO)
    with pytest.raises(InvalidStateTransition):
        d.validar_transicion_cobro(EstadoCobro.PENDIENTE, EstadoCobro.REEMBOLSADO)
    with pytest.raises(InvalidStateTransition):
        d.validar_transicion_cobro(EstadoCobro.REEMBOLSADO, EstadoCobro.CAPTURADO)


# Lote 9. Vencimientos

LIMITE = AHORA + timedelta(days=7)


def test_9_cobro_vencido_solo_vuelve_a_pendiente():
    d.validar_transicion_cobro(EstadoCobro.VENCIDO, EstadoCobro.PENDIENTE)
    for hacia in (EstadoCobro.AUTORIZADO, EstadoCobro.CAPTURADO, EstadoCobro.CANCELADO):
        with pytest.raises(InvalidStateTransition):
            d.validar_transicion_cobro(EstadoCobro.VENCIDO, hacia)


def test_9_limite_de_reautorizacion_desde_el_vencimiento():
    assert d.limite_reautorizacion(AHORA, POLITICAS) == LIMITE


@pytest.mark.parametrize("estado_saldo", [EstadoCobro.VENCIDO, EstadoCobro.PENDIENTE])
def test_9_reautorizacion_admitida_hasta_el_limite(estado_saldo):
    antes = LIMITE - timedelta(microseconds=1)
    d.validar_reautorizacion(
        E.VISTA_PREVIA_ENTREGADA, estado_saldo, AHORA, antes, POLITICAS
    )
    with pytest.raises(FueraDePlazo):
        d.validar_reautorizacion(
            E.VISTA_PREVIA_ENTREGADA, estado_saldo, AHORA, LIMITE, POLITICAS
        )


@pytest.mark.parametrize(
    ("estado_pedido", "estado_saldo", "autorizado_hasta"),
    [
        (E.VISTA_PREVIA_ENTREGADA, EstadoCobro.AUTORIZADO, AHORA),
        (E.VISTA_PREVIA_ENTREGADA, EstadoCobro.CAPTURADO, AHORA),
        (E.VISTA_PREVIA_ENTREGADA, EstadoCobro.CANCELADO, AHORA),
        (E.VISTA_PREVIA_ENTREGADA, EstadoCobro.PENDIENTE, None),
        (E.EN_PROCESO, EstadoCobro.VENCIDO, AHORA),
        (E.SALDO_PAGADO, EstadoCobro.VENCIDO, AHORA),
    ],
)
def test_9_reautorizacion_rechaza_otros_casos(
    estado_pedido, estado_saldo, autorizado_hasta
):
    with pytest.raises(InvalidStateTransition):
        d.validar_reautorizacion(
            estado_pedido, estado_saldo, autorizado_hasta, AHORA, POLITICAS
        )


def test_9_saldo_de_evento_solo_antes_de_su_fecha():
    d.validar_saldo_evento_a_tiempo(AHORA + timedelta(microseconds=1), AHORA)
    for fecha in (AHORA, AHORA - timedelta(days=1), None):
        with pytest.raises(FueraDePlazo):
            d.validar_saldo_evento_a_tiempo(fecha, AHORA)


@pytest.mark.parametrize("estado_saldo", [EstadoCobro.VENCIDO, EstadoCobro.PENDIENTE])
def test_9_vencimiento_de_encargo_conserva_el_anticipo(estado_saldo):
    anticipo, saldo = _encargo_con_anticipo(estado_saldo)
    plan = d.planear_vencimiento(T.ENCARGO, E.VISTA_PREVIA_ENTREGADA, [anticipo, saldo])
    assert plan.de(anticipo.id).accion is Accion.CONSERVAR
    if estado_saldo is EstadoCobro.VENCIDO:
        assert plan.de(saldo.id) is None
    else:
        assert plan.de(saldo.id).accion is Accion.CANCELAR
    assert plan.reembolsos == {}
    assert plan.liberaciones == frozenset()


def test_9_vencimiento_de_evento_conserva_el_anticipo_y_anula_el_saldo():
    anticipo, saldo = _encargo_con_anticipo(EstadoCobro.PENDIENTE)
    plan = d.planear_vencimiento(T.EVENTO, E.ANTICIPO_PAGADO, [anticipo, saldo])
    assert plan.de(anticipo.id).accion is Accion.CONSERVAR
    assert plan.de(saldo.id).accion is Accion.CANCELAR
    assert plan.reembolsos == {}


def test_9_vencimiento_de_obra_con_el_total_vencido_no_mueve_dinero():
    total = CobroFalso(TipoCobro.TOTAL, EstadoCobro.VENCIDO, Decimal("15000.00"))
    plan = d.planear_vencimiento(T.OBRA_DISPONIBLE, E.EN_PROCESO, [total])
    assert plan.acciones == ()


@pytest.mark.parametrize(
    ("tipo", "estado"),
    [
        (T.ENCARGO, E.EN_PROCESO),
        (T.ENCARGO, E.ANTICIPO_PAGADO),
        (T.ENCARGO, E.COTIZADO),
        (T.EVENTO, E.SALDO_PAGADO),
        (T.OBRA_DISPONIBLE, E.COTIZADO),
        (T.ENCARGO, E.CANCELADO),
    ],
)
def test_9_vencimiento_rechaza_estados_no_admitidos(tipo, estado):
    anticipo, saldo = _encargo_con_anticipo(EstadoCobro.VENCIDO)
    with pytest.raises(InvalidStateTransition):
        d.planear_vencimiento(tipo, estado, [anticipo, saldo])


def test_9_politicas_de_vencimiento_desde_config_y_positivas():
    config = Settings(
        DATABASE_URL="postgresql+psycopg://u:p@h:5432/d",
        ALEMBIC_DATABASE_URL="postgresql+psycopg://u:p@h:5432/d",
        SUPABASE_URL="https://x.supabase.co",
        DIAS_REAUTORIZACION_SALDO=3,
        MINUTOS_ABANDONO_3DS=45,
    )
    politicas = PoliticasPedido.desde_config(config)
    assert politicas.plazo_reautorizacion_saldo == timedelta(days=3)
    assert politicas.abandono_3ds == timedelta(minutes=45)
    for campo in ("plazo_reautorizacion_saldo", "abandono_3ds"):
        with pytest.raises(ValueError, match="positivo"):
            replace(POLITICAS, **{campo: timedelta(0)})
