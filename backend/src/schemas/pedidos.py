"""Esquemas de pedidos y cobros. Las validaciones de forma dan 422.

Ninguna respuesta lleva la referencia de la pasarela. La url de autenticacion
del 3DS solo viaja en la respuesta al cliente que paga. El archivo final nunca
lleva URL en el pedido: se firma aparte, para quien participa.
"""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal, Self

from pydantic import (
    AfterValidator,
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
)

from src.domain.enums import EstadoCobro, EstadoPedido, TipoCobro, TipoPedido
from src.domain.pedidos import Rol
from src.models import Cobro, Disputa, EstadoDisputa
from src.schemas.catalogo import Monto
from src.schemas.medios import ImagenPublica
from src.schemas.social import PerfilResumido
from src.services.consultas import MensajeConRemitente
from src.services.contratacion import Resultado, ResultadoPago
from src.services.pedidos import (
    EntregableFinal,
    PedidoDetalle,
    VistaPrevia,
    esperando_autenticacion,
)
from src.storage import Almacenamiento
from src.storage.contrato import DescargaFirmada

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


class NuevoFinal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    medio_id: uuid.UUID
    nota: Nota | None = None


class Despacho(BaseModel):
    model_config = ConfigDict(extra="forbid")

    guia_envio: Guia


class NuevaDisputa(BaseModel):
    model_config = ConfigDict(extra="forbid")

    motivo: Texto2000


class ReembolsoOrdenado(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cobro_id: uuid.UUID
    # Que no supere lo reembolsable lo valida el dominio (409)
    monto: Annotated[Decimal, Field(gt=0, max_digits=12, decimal_places=2)]


def _sin_cobros_repetidos(
    reembolsos: list[ReembolsoOrdenado],
) -> list[ReembolsoOrdenado]:
    if len({r.cobro_id for r in reembolsos}) != len(reembolsos):
        raise ValueError("Un cobro aparece mas de una vez en los reembolsos")
    return reembolsos


class ResolucionDisputa(BaseModel):
    model_config = ConfigDict(extra="forbid")

    destino: Literal[EstadoPedido.COMPLETADO, EstadoPedido.CANCELADO]
    resolucion: Texto2000
    # Un pedido tiene a lo sumo dos cobros
    reembolsos: Annotated[
        list[ReembolsoOrdenado],
        Field(max_length=2),
        AfterValidator(_sin_cobros_repetidos),
    ] = []

    def reembolsos_por_cobro(self) -> dict[uuid.UUID, Decimal]:
        return {r.cobro_id: r.monto for r in self.reembolsos}


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
            esperando_autenticacion=esperando_autenticacion(cobro),
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


class FinalRespuesta(BaseModel):
    """Sin URL: el archivo es privado y se pide con el endpoint de descarga."""

    id: uuid.UUID
    nota: str | None
    created_at: datetime
    content_type: str | None

    @classmethod
    def desde(cls, final: EntregableFinal) -> Self:
        return cls(
            id=final.entregable.id,
            nota=final.entregable.nota,
            created_at=final.entregable.created_at,
            content_type=final.medio.content_type,
        )


class DescargaRespuesta(BaseModel):
    url: str
    expira_en: datetime

    @classmethod
    def desde(cls, descarga: DescargaFirmada) -> Self:
        return cls(url=descarga.url, expira_en=descarga.expira_en)


class DisputaRespuesta(BaseModel):
    estado: EstadoDisputa
    motivo: str
    abierta_por: PerfilResumido
    created_at: datetime
    resolucion: str | None
    resuelta_en: datetime | None

    @classmethod
    def desde(cls, disputa: Disputa, detalle: PedidoDetalle) -> Self:
        # La abre siempre una de las dos partes
        abierta_por = (
            detalle.cliente
            if disputa.abierta_por_id == detalle.cliente.id
            else detalle.artista
        )
        return cls(
            estado=disputa.estado,
            motivo=disputa.motivo,
            abierta_por=PerfilResumido.desde(abierta_por),
            created_at=disputa.created_at,
            resolucion=disputa.resolucion,
            resuelta_en=disputa.resuelta_en,
        )


class PedidoRespuesta(BaseModel):
    id: uuid.UUID
    consulta_id: uuid.UUID
    tipo: TipoPedido
    estado: EstadoPedido
    # Nulo cuando mira moderacion
    soy: Rol | None
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
    finales: list[FinalRespuesta]
    disputa: DisputaRespuesta | None

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
            finales=[FinalRespuesta.desde(f) for f in detalle.finales],
            disputa=None
            if detalle.disputa is None
            else DisputaRespuesta.desde(detalle.disputa, detalle),
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


class MensajeModeracion(BaseModel):
    """Un mensaje del chat de la consulta, como lo ve moderacion."""

    remitente: PerfilResumido
    texto: str
    aviso_contacto: bool
    created_at: datetime

    @classmethod
    def desde(cls, detalle: MensajeConRemitente) -> Self:
        mensaje = detalle.mensaje
        return cls(
            remitente=PerfilResumido.desde(detalle.remitente),
            texto=mensaje.texto,
            aviso_contacto=mensaje.aviso_contacto,
            created_at=mensaje.created_at,
        )
