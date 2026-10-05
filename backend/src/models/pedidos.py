import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from src.domain.enums import (
    EstadoCobro,
    EstadoDisputa,
    EstadoPedido,
    TipoCobro,
    TipoEntregable,
    TipoPedido,
)

from .base import Base, IdMixin, TimestampMixin, pg_enum

OBRA_ACTIVA = "tipo = 'obra_disponible' AND estado NOT IN ('rechazado', 'cancelado')"


class Pedido(Base, IdMixin, TimestampMixin):
    __tablename__ = "pedidos"
    __table_args__ = (
        CheckConstraint("monto_total > 0", name="monto_total_positivo"),
        # El rango de negocio (30 a 50) es configurable y no va en la base
        CheckConstraint(
            "(tipo = 'obra_disponible') = (anticipo_porcentaje IS NULL)",
            name="anticipo_solo_con_hitos",
        ),
        CheckConstraint(
            "anticipo_porcentaje > 0 AND anticipo_porcentaje < 100",
            name="anticipo_porcentaje_en_rango",
        ),
        Index("ix_pedidos_artista_id_estado", "artista_id", "estado"),
        # Una obra tiene como mucho un pedido vivo
        Index(
            "ux_pedidos_obra_activa",
            "obra_id",
            unique=True,
            postgresql_where=text(OBRA_ACTIVA),
        ),
    )

    consulta_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("consultas.id"), unique=True
    )
    cliente_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("profiles.id"), index=True)
    artista_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("profiles.id"))
    tipo: Mapped[TipoPedido] = mapped_column(pg_enum(TipoPedido, "tipo_pedido"))
    estado: Mapped[EstadoPedido] = mapped_column(
        pg_enum(EstadoPedido, "estado_pedido"),
        default=EstadoPedido.COTIZADO,
        server_default=EstadoPedido.COTIZADO.value,
    )
    descripcion: Mapped[str] = mapped_column(String)
    monto_total: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    moneda: Mapped[str] = mapped_column(String(3), default="CRC", server_default="CRC")
    # Tarifa vigente al crear el pedido. No cambia si el artista cambia de plan.
    tarifa_porcentaje: Mapped[Decimal] = mapped_column(Numeric(5, 2))
    # Nulo solo en obra disponible, que se cobra en un solo hito
    anticipo_porcentaje: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 2), nullable=True
    )
    obra_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("obras.id"), nullable=True
    )
    fecha_evento: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    lugar_evento: Mapped[str | None] = mapped_column(String, nullable=True)
    guia_envio: Mapped[str | None] = mapped_column(String, nullable=True)
    fecha_entrega_estimada: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # Se fija al entrar en saldo_pagado. Vencida, el pedido pasa a completado.
    disputable_hasta: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class Cobro(Base, IdMixin, TimestampMixin):
    """Un hito de pago de un pedido. El dinero lo custodia la pasarela."""

    __tablename__ = "cobros"
    __table_args__ = (
        CheckConstraint("monto > 0", name="monto_positivo"),
        CheckConstraint(
            "monto_reembolsado >= 0 AND monto_reembolsado <= monto",
            name="monto_reembolsado_en_rango",
        ),
    )

    pedido_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("pedidos.id"), index=True)
    tipo: Mapped[TipoCobro] = mapped_column(pg_enum(TipoCobro, "tipo_cobro"))
    estado: Mapped[EstadoCobro] = mapped_column(
        pg_enum(EstadoCobro, "estado_cobro"),
        default=EstadoCobro.PENDIENTE,
        server_default=EstadoCobro.PENDIENTE.value,
    )
    monto: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    # Hecho del cobro, no un saldo. Menor que monto en un reembolso parcial.
    monto_reembolsado: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), default=Decimal("0"), server_default="0"
    )
    pasarela: Mapped[str] = mapped_column(String)
    referencia_pasarela: Mapped[str | None] = mapped_column(
        String, nullable=True, unique=True
    )
    autorizado_hasta: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    capturado_en: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class Resena(Base, IdMixin, TimestampMixin):
    __tablename__ = "resenas"
    __table_args__ = (
        UniqueConstraint("pedido_id", "autor_id"),
        CheckConstraint(
            "calificacion BETWEEN 1 AND 5", name="calificacion_entre_1_y_5"
        ),
    )

    pedido_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("pedidos.id"))
    autor_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("profiles.id"))
    destinatario_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("profiles.id"))
    calificacion: Mapped[int] = mapped_column(Integer)
    texto: Mapped[str | None] = mapped_column(String, nullable=True)


class Entregable(Base, IdMixin, TimestampMixin):
    """Vista previa con marca de agua o archivo final de un pedido."""

    __tablename__ = "entregables"

    pedido_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("pedidos.id"), index=True)
    media_asset_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("media_assets.id"))
    tipo: Mapped[TipoEntregable] = mapped_column(
        pg_enum(TipoEntregable, "tipo_entregable")
    )
    nota: Mapped[str | None] = mapped_column(String, nullable=True)


class Disputa(Base, IdMixin, TimestampMixin):
    """Una por pedido. La resuelve moderacion con el chat y los entregables."""

    __tablename__ = "disputas"

    pedido_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("pedidos.id"), unique=True)
    abierta_por_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("profiles.id"))
    motivo: Mapped[str] = mapped_column(String)
    estado: Mapped[EstadoDisputa] = mapped_column(
        pg_enum(EstadoDisputa, "estado_disputa"),
        default=EstadoDisputa.ABIERTA,
        server_default=EstadoDisputa.ABIERTA.value,
    )
    resolucion: Mapped[str | None] = mapped_column(String, nullable=True)
    resuelta_por_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("profiles.id"), nullable=True
    )
    resuelta_en: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
