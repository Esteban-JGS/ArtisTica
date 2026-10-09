"""Esquemas de pedidos y cobros. Las validaciones de forma dan 422.

Ninguna respuesta lleva la referencia de la pasarela. La url de autenticacion
del 3DS solo viaja en la respuesta al cliente que paga.
"""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal, Self

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, StringConstraints

from src.domain.enums import EstadoCobro, EstadoPedido, TipoCobro, TipoPedido
from src.domain.pedidos import Rol
from src.models import Cobro
from src.schemas.catalogo import Monto
from src.schemas.medios import ImagenPublica
from src.schemas.social import PerfilResumido
from src.services.contratacion import Resultado, ResultadoPago
from src.services.pedidos import PedidoDetalle, VistaPrevia
from src.storage import Almacenamiento

Texto2000 = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)
]
Lugar = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)
]
Nota = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)
]
Guia = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)
]
# El rango de negocio lo valida el dominio con la configuracion (409)
Porcentaje = Annotated[Decimal, Field(gt=0, lt=100, decimal_places=2)]
MetodoPagoId = Annotated[
    str, StringConstraints(min_length=1, max_length=200, pattern=r"^\S+$")
]


# Entrada


class DatosCotizacion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    descripcion: Texto2000
    monto_total: Monto
    # Sin valor rige el anticipo por defecto
    anticipo_porcentaje: Porcentaje | None = None
    # Obligatoria y futura en un evento; prohibida en un encargo
    fecha_evento: AwareDatetime | None = None
    lugar_evento: Lugar | None = None
    fecha_entrega_estimada: AwareDatetime | None = None


class NuevaCotizacion(DatosCotizacion):
    # La obra disponible no se cotiza: se pide con La quiero
    tipo: Literal[TipoPedido.ENCARGO, TipoPedido.EVENTO]


class Pago(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # El medio de pago que la app tokenizo contra la pasarela (D23)
    metodo_pago_id: MetodoPagoId


class NuevaVistaPrevia(BaseModel):
    model_config = ConfigDict(extra="forbid")

    medio_id: uuid.UUID
    nota: Nota | None = None


class Despacho(BaseModel):
    model_config = ConfigDict(extra="forbid")

    guia_envio: Guia


class NuevaDisputa(BaseModel):
    model_config = ConfigDict(extra="forbid")

    motivo: Texto2000


# Salida


class CobroRespuesta(BaseModel):
    id: uuid.UUID
    tipo: TipoCobro
    estado: EstadoCobro
    monto: Decimal
    monto_reembolsado: Decimal
    autorizado_hasta: datetime | None
    capturado_en: datetime | None
    # Un intento espera que el cliente se autentique en el banco
    esperando_autenticacion: bool

    @classmethod
    def desde(cls, cobro: Cobro) -> Self:
        return cls(
            id=cobro.id,
            tipo=cobro.tipo,
            estado=cobro.estado,
            monto=cobro.monto,
            monto_reembolsado=cobro.monto_reembolsado,
            autorizado_hasta=cobro.autorizado_hasta,
            capturado_en=cobro.capturado_en,
            esperando_autenticacion=cobro.estado is EstadoCobro.PENDIENTE
            and cobro.referencia_pasarela is not None,
        )


class VistaPreviaRespuesta(BaseModel):
    id: uuid.UUID
    nota: str | None
    created_at: datetime
    imagen: ImagenPublica

    @classmethod
    def desde(cls, vista: VistaPrevia, almacenamiento: Almacenamiento) -> Self:
        return cls(
            id=vista.entregable.id,
            nota=vista.entregable.nota,
            created_at=vista.entregable.created_at,
            imagen=ImagenPublica.desde(vista.medio, almacenamiento),
        )


class PedidoRespuesta(BaseModel):
    id: uuid.UUID
    consulta_id: uuid.UUID
    tipo: TipoPedido
    estado: EstadoPedido
    soy: Rol
    cliente: PerfilResumido
    artista: PerfilResumido
    descripcion: str
    monto_total: Decimal
    moneda: str
    tarifa_porcentaje: Decimal
    anticipo_porcentaje: Decimal | None
    obra_id: uuid.UUID | None
    fecha_evento: datetime | None
    lugar_evento: str | None
    fecha_entrega_estimada: datetime | None
    guia_envio: str | None
    # Hasta cuando se puede abrir una disputa, desde saldo_pagado
    disputable_hasta: datetime | None
    created_at: datetime
    updated_at: datetime
    cobros: list[CobroRespuesta]
    vistas_previas: list[VistaPreviaRespuesta]

    @classmethod
    def desde(cls, detalle: PedidoDetalle, almacenamiento: Almacenamiento) -> Self:
        pedido = detalle.pedido
        return cls(
            id=pedido.id,
            consulta_id=pedido.consulta_id,
            tipo=pedido.tipo,
            estado=pedido.estado,
            soy=detalle.soy,
            cliente=PerfilResumido.desde(detalle.cliente),
            artista=PerfilResumido.desde(detalle.artista),
            descripcion=pedido.descripcion,
            monto_total=pedido.monto_total,
            moneda=pedido.moneda,
            tarifa_porcentaje=pedido.tarifa_porcentaje,
            anticipo_porcentaje=pedido.anticipo_porcentaje,
            obra_id=pedido.obra_id,
            fecha_evento=pedido.fecha_evento,
            lugar_evento=pedido.lugar_evento,
            fecha_entrega_estimada=pedido.fecha_entrega_estimada,
            guia_envio=pedido.guia_envio,
            disputable_hasta=pedido.disputable_hasta,
            created_at=pedido.created_at,
            updated_at=pedido.updated_at,
            cobros=[CobroRespuesta.desde(c) for c in detalle.cobros],
            vistas_previas=[
                VistaPreviaRespuesta.desde(v, almacenamiento)
                for v in detalle.vistas_previas
            ],
        )


class ResultadoPagoRespuesta(BaseModel):
    resultado: Resultado
    # Solo con requiere_accion: la app la abre en el navegador y despues
    # llama a verificar el cobro
    url_autenticacion: str | None
    # Solo con rechazado
    mensaje: str | None
    # Nulos solo en La quiero rechazado: no queda pedido
    cobro: CobroRespuesta | None
    pedido: PedidoRespuesta | None

    @classmethod
    def desde(cls, resultado: ResultadoPago, almacenamiento: Almacenamiento) -> Self:
        return cls(
            resultado=resultado.resultado,
            url_autenticacion=resultado.url_autenticacion,
            mensaje=resultado.mensaje,
            cobro=None
            if resultado.cobro is None
            else CobroRespuesta.desde(resultado.cobro),
            pedido=None
            if resultado.pedido is None
            else PedidoRespuesta.desde(resultado.pedido, almacenamiento),
        )
