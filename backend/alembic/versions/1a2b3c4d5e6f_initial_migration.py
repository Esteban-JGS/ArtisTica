"""initial migration

Revision ID: 1a2b3c4d5e6f
Revises:
Create Date: 2026-09-12 21:05:00.000000

"""

from collections.abc import Sequence

import pgvector.sqlalchemy
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "1a2b3c4d5e6f"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


ENUMS: dict[str, tuple[str, ...]] = {
    "rol_perfil": ("publico", "artista", "admin"),
    "plan_artista": ("taller", "estudio"),
    "estado_onboarding": ("no_iniciado", "pendiente", "completado", "rechazado"),
    "estado_obra": ("exhibicion", "disponible", "vendida"),
    "tipo_servicio": ("encargo", "evento"),
    "estado_consulta": ("abierta", "cotizada", "convertida", "descartada"),
    "tipo_pedido": ("encargo", "evento", "obra_disponible"),
    "estado_pedido": (
        "cotizado",
        "anticipo_pagado",
        "en_proceso",
        "vista_previa_entregada",
        "saldo_pagado",
        "completado",
        "rechazado",
        "cancelado",
        "en_disputa",
    ),
    "tipo_cobro": ("anticipo", "saldo", "total"),
    "estado_cobro": (
        "pendiente",
        "autorizado",
        "capturado",
        "cancelado",
        "reembolsado",
        "vencido",
    ),
    "estado_media": ("pendiente", "procesado", "fallido"),
    "estado_reporte": ("pendiente", "revisado", "descartado"),
    "tipo_entregable": ("vista_previa", "final"),
    "estado_disputa": ("abierta", "en_revision", "resuelta"),
}

# En orden de creacion; el downgrade las borra al reves
TABLES = [
    "profiles",
    "follows",
    "obras",
    "servicios",
    "publicaciones",
    "comentarios",
    "reacciones",
    "media_assets",
    "consultas",
    "mensajes",
    "pedidos",
    "cobros",
    "resenas",
    "entregables",
    "disputas",
    "ledger_entries",
    "eventos_pasarela",
    "post_views",
    "jobs",
    "reportes",
    "moderation_actions",
]


def _enum(name: str) -> postgresql.ENUM:
    return postgresql.ENUM(*ENUMS[name], name=name, create_type=False)


def _uuid(name: str, nullable: bool = False) -> sa.Column:
    return sa.Column(name, postgresql.UUID(as_uuid=True), nullable=nullable)


def _money(name: str, nullable: bool = False) -> sa.Column:
    return sa.Column(name, sa.Numeric(precision=12, scale=2), nullable=nullable)


def _tz(name: str, nullable: bool = True) -> sa.Column:
    return sa.Column(name, sa.DateTime(timezone=True), nullable=nullable)


def _timestamps() -> list[sa.Column]:
    return [_tz("created_at", nullable=False), _tz("updated_at", nullable=False)]


def _fk(
    table: str, column: str, referred: str, ondelete: str | None = None
) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint(
        [column],
        [f"{referred}.id"],
        name=f"fk_{table}_{column}_{referred}",
        ondelete=ondelete,
    )


def _pk(table: str) -> sa.PrimaryKeyConstraint:
    return sa.PrimaryKeyConstraint("id", name=f"pk_{table}")


# Los CHECK van con op.f() porque la convencion de nombres de los modelos
# les antepondria el prefijo por segunda vez.


def upgrade() -> None:
    # 1. Extensiones
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp";')
    op.execute("CREATE EXTENSION IF NOT EXISTS vector;")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm;")

    # 2. Tipos enum
    for name, values in ENUMS.items():
        labels = ", ".join(f"'{v}'" for v in values)
        op.execute(f"CREATE TYPE {name} AS ENUM ({labels});")

    # 3. Perfiles y seguimiento
    op.create_table(
        "profiles",
        _uuid("id"),
        sa.Column("handle", sa.String(), nullable=False),
        sa.Column("nombre", sa.String(), nullable=False),
        sa.Column("bio", sa.String(), nullable=True),
        sa.Column("categorias", postgresql.ARRAY(sa.String()), nullable=False),
        sa.Column("provincia", sa.String(), nullable=True),
        sa.Column("rol", _enum("rol_perfil"), nullable=False),
        sa.Column("plan", _enum("plan_artista"), nullable=False),
        sa.Column("is_verified", sa.Boolean(), nullable=False),
        sa.Column("pasarela_cuenta_id", sa.String(), nullable=True),
        sa.Column("pasarela_onboarding", _enum("estado_onboarding"), nullable=False),
        *_timestamps(),
        _pk("profiles"),
    )
    op.create_index("ix_profiles_handle", "profiles", ["handle"], unique=True)

    op.create_table(
        "follows",
        _uuid("id"),
        _uuid("seguidor_id"),
        _uuid("seguido_id"),
        *_timestamps(),
        _fk("follows", "seguidor_id", "profiles", "CASCADE"),
        _fk("follows", "seguido_id", "profiles", "CASCADE"),
        sa.UniqueConstraint(
            "seguidor_id", "seguido_id", name="uq_follows_seguidor_id_seguido_id"
        ),
        sa.CheckConstraint(
            "seguidor_id <> seguido_id", name=op.f("ck_follows_no_autoseguimiento")
        ),
        _pk("follows"),
    )
    op.create_index("ix_follows_seguido_id", "follows", ["seguido_id"])

    # 4. Catalogo
    op.create_table(
        "obras",
        _uuid("id"),
        _uuid("artista_id"),
        sa.Column("titulo", sa.String(), nullable=False),
        sa.Column("descripcion", sa.String(), nullable=True),
        sa.Column("estado", _enum("estado_obra"), nullable=False),
        _money("precio", nullable=True),
        sa.Column("categorias", postgresql.ARRAY(sa.String()), nullable=False),
        sa.Column(
            "style_embedding", pgvector.sqlalchemy.Vector(dim=1536), nullable=True
        ),
        sa.Column("hash_imagen", sa.String(), nullable=True),
        *_timestamps(),
        _tz("deleted_at"),
        _fk("obras", "artista_id", "profiles", "CASCADE"),
        sa.CheckConstraint(
            "estado = 'exhibicion' OR (precio IS NOT NULL AND precio > 0)",
            name=op.f("ck_obras_precio_fuera_de_exhibicion"),
        ),
        _pk("obras"),
    )
    op.create_index("ix_obras_artista_id", "obras", ["artista_id"])
    op.create_index("ix_obras_hash_imagen", "obras", ["hash_imagen"])
    op.execute(
        "CREATE INDEX ix_obras_style_embedding ON obras "
        "USING hnsw (style_embedding vector_cosine_ops);"
    )

    op.create_table(
        "servicios",
        _uuid("id"),
        _uuid("artista_id"),
        sa.Column("titulo", sa.String(), nullable=False),
        sa.Column("descripcion", sa.String(), nullable=True),
        _money("precio_base"),
        sa.Column("tipo", _enum("tipo_servicio"), nullable=False),
        sa.Column("activo", sa.Boolean(), nullable=False),
        *_timestamps(),
        _tz("deleted_at"),
        _fk("servicios", "artista_id", "profiles", "CASCADE"),
        _pk("servicios"),
    )
    op.create_index("ix_servicios_artista_id", "servicios", ["artista_id"])

    # 5. Social
    op.create_table(
        "publicaciones",
        _uuid("id"),
        _uuid("artista_id"),
        sa.Column("texto", sa.String(), nullable=False),
        _uuid("obra_id", nullable=True),
        sa.Column(
            "search_vector",
            postgresql.TSVECTOR(),
            sa.Computed("to_tsvector('spanish', texto)", persisted=True),
            nullable=True,
        ),
        *_timestamps(),
        _tz("deleted_at"),
        _fk("publicaciones", "artista_id", "profiles", "CASCADE"),
        _fk("publicaciones", "obra_id", "obras", "SET NULL"),
        _pk("publicaciones"),
    )
    op.execute(
        "CREATE INDEX ix_publicaciones_search_vector ON publicaciones "
        "USING gin (search_vector);"
    )
    op.create_index(
        "ix_publicaciones_artista_id_created_at",
        "publicaciones",
        ["artista_id", sa.text("created_at DESC")],
    )

    op.create_table(
        "comentarios",
        _uuid("id"),
        _uuid("publicacion_id"),
        _uuid("profile_id"),
        sa.Column("texto", sa.String(), nullable=False),
        *_timestamps(),
        _tz("deleted_at"),
        _fk("comentarios", "publicacion_id", "publicaciones", "CASCADE"),
        _fk("comentarios", "profile_id", "profiles", "CASCADE"),
        _pk("comentarios"),
    )
    op.create_index("ix_comentarios_publicacion_id", "comentarios", ["publicacion_id"])

    op.create_table(
        "reacciones",
        _uuid("id"),
        _uuid("publicacion_id"),
        _uuid("profile_id"),
        sa.Column("tipo", sa.String(), nullable=False),
        *_timestamps(),
        _fk("reacciones", "publicacion_id", "publicaciones", "CASCADE"),
        _fk("reacciones", "profile_id", "profiles", "CASCADE"),
        sa.UniqueConstraint(
            "publicacion_id",
            "profile_id",
            "tipo",
            name="uq_reacciones_publicacion_id_profile_id_tipo",
        ),
        _pk("reacciones"),
    )

    # 6. Medios
    op.create_table(
        "media_assets",
        _uuid("id"),
        _uuid("propietario_id"),
        _uuid("obra_id", nullable=True),
        _uuid("publicacion_id", nullable=True),
        sa.Column("tipo", sa.String(), nullable=False),
        sa.Column("storage_path", sa.String(), nullable=False),
        sa.Column("thumbnail_path", sa.String(), nullable=True),
        sa.Column("estado", _enum("estado_media"), nullable=False),
        *_timestamps(),
        _tz("deleted_at"),
        _fk("media_assets", "propietario_id", "profiles", "CASCADE"),
        _fk("media_assets", "obra_id", "obras", "CASCADE"),
        _fk("media_assets", "publicacion_id", "publicaciones", "CASCADE"),
        _pk("media_assets"),
    )

    # 7. Consultas y chat
    op.create_table(
        "consultas",
        _uuid("id"),
        _uuid("cliente_id"),
        _uuid("artista_id"),
        _uuid("servicio_id", nullable=True),
        _uuid("obra_id", nullable=True),
        sa.Column("estado", _enum("estado_consulta"), nullable=False),
        *_timestamps(),
        _fk("consultas", "cliente_id", "profiles"),
        _fk("consultas", "artista_id", "profiles"),
        _fk("consultas", "servicio_id", "servicios"),
        _fk("consultas", "obra_id", "obras"),
        sa.CheckConstraint(
            "cliente_id <> artista_id", name=op.f("ck_consultas_cliente_no_es_artista")
        ),
        _pk("consultas"),
    )
    op.create_index("ix_consultas_cliente_id", "consultas", ["cliente_id"])
    op.create_index("ix_consultas_artista_id", "consultas", ["artista_id"])

    op.create_table(
        "mensajes",
        _uuid("id"),
        _uuid("consulta_id"),
        _uuid("remitente_id"),
        sa.Column("texto", sa.String(), nullable=False),
        *_timestamps(),
        _fk("mensajes", "consulta_id", "consultas"),
        _fk("mensajes", "remitente_id", "profiles"),
        _pk("mensajes"),
    )
    op.create_index("ix_mensajes_consulta_id", "mensajes", ["consulta_id"])

    # 8. Pedidos, cobros, resenas, entregables y disputas. Sin CASCADE: son historia.
    op.create_table(
        "pedidos",
        _uuid("id"),
        _uuid("consulta_id"),
        _uuid("cliente_id"),
        _uuid("artista_id"),
        sa.Column("tipo", _enum("tipo_pedido"), nullable=False),
        sa.Column("estado", _enum("estado_pedido"), nullable=False),
        sa.Column("descripcion", sa.String(), nullable=False),
        _money("monto_total"),
        sa.Column("moneda", sa.String(length=3), nullable=False),
        sa.Column(
            "tarifa_porcentaje", sa.Numeric(precision=5, scale=2), nullable=False
        ),
        _uuid("obra_id", nullable=True),
        _tz("fecha_evento"),
        sa.Column("lugar_evento", sa.String(), nullable=True),
        sa.Column("guia_envio", sa.String(), nullable=True),
        _tz("fecha_entrega_estimada"),
        *_timestamps(),
        _fk("pedidos", "consulta_id", "consultas"),
        _fk("pedidos", "cliente_id", "profiles"),
        _fk("pedidos", "artista_id", "profiles"),
        _fk("pedidos", "obra_id", "obras"),
        sa.UniqueConstraint("consulta_id", name="uq_pedidos_consulta_id"),
        sa.CheckConstraint(
            "monto_total > 0", name=op.f("ck_pedidos_monto_total_positivo")
        ),
        _pk("pedidos"),
    )
    op.create_index("ix_pedidos_cliente_id", "pedidos", ["cliente_id"])
    op.create_index("ix_pedidos_artista_id_estado", "pedidos", ["artista_id", "estado"])

    op.create_table(
        "cobros",
        _uuid("id"),
        _uuid("pedido_id"),
        sa.Column("tipo", _enum("tipo_cobro"), nullable=False),
        sa.Column("estado", _enum("estado_cobro"), nullable=False),
        _money("monto"),
        sa.Column("pasarela", sa.String(), nullable=False),
        sa.Column("referencia_pasarela", sa.String(), nullable=True),
        _tz("autorizado_hasta"),
        _tz("capturado_en"),
        *_timestamps(),
        _fk("cobros", "pedido_id", "pedidos"),
        sa.UniqueConstraint(
            "referencia_pasarela", name="uq_cobros_referencia_pasarela"
        ),
        sa.CheckConstraint("monto > 0", name=op.f("ck_cobros_monto_positivo")),
        _pk("cobros"),
    )
    op.create_index("ix_cobros_pedido_id", "cobros", ["pedido_id"])

    op.create_table(
        "resenas",
        _uuid("id"),
        _uuid("pedido_id"),
        _uuid("autor_id"),
        _uuid("destinatario_id"),
        sa.Column("calificacion", sa.Integer(), nullable=False),
        sa.Column("texto", sa.String(), nullable=True),
        *_timestamps(),
        _fk("resenas", "pedido_id", "pedidos"),
        _fk("resenas", "autor_id", "profiles"),
        _fk("resenas", "destinatario_id", "profiles"),
        sa.UniqueConstraint(
            "pedido_id", "autor_id", name="uq_resenas_pedido_id_autor_id"
        ),
        sa.CheckConstraint(
            "calificacion BETWEEN 1 AND 5",
            name=op.f("ck_resenas_calificacion_entre_1_y_5"),
        ),
        _pk("resenas"),
    )

    op.create_table(
        "entregables",
        _uuid("id"),
        _uuid("pedido_id"),
        _uuid("media_asset_id"),
        sa.Column("tipo", _enum("tipo_entregable"), nullable=False),
        sa.Column("nota", sa.String(), nullable=True),
        *_timestamps(),
        _fk("entregables", "pedido_id", "pedidos"),
        _fk("entregables", "media_asset_id", "media_assets"),
        _pk("entregables"),
    )
    op.create_index("ix_entregables_pedido_id", "entregables", ["pedido_id"])

    op.create_table(
        "disputas",
        _uuid("id"),
        _uuid("pedido_id"),
        _uuid("abierta_por_id"),
        sa.Column("motivo", sa.String(), nullable=False),
        sa.Column("estado", _enum("estado_disputa"), nullable=False),
        sa.Column("resolucion", sa.String(), nullable=True),
        _uuid("resuelta_por_id", nullable=True),
        _tz("resuelta_en"),
        *_timestamps(),
        _fk("disputas", "pedido_id", "pedidos"),
        _fk("disputas", "abierta_por_id", "profiles"),
        _fk("disputas", "resuelta_por_id", "profiles"),
        sa.UniqueConstraint("pedido_id", name="uq_disputas_pedido_id"),
        _pk("disputas"),
    )

    # 9. Conciliacion con la pasarela
    op.create_table(
        "ledger_entries",
        _uuid("id"),
        _uuid("pedido_id", nullable=True),
        _uuid("cobro_id", nullable=True),
        _uuid("profile_id"),
        sa.Column("tipo_evento", sa.String(), nullable=False),
        _money("monto_bruto"),
        _money("tarifa_artistica"),
        _money("costo_procesamiento"),
        _money("monto_neto_artista"),
        sa.Column("referencia_pasarela", sa.String(), nullable=True),
        _tz("ocurrido_en", nullable=False),
        *_timestamps(),
        _fk("ledger_entries", "pedido_id", "pedidos"),
        _fk("ledger_entries", "cobro_id", "cobros"),
        _fk("ledger_entries", "profile_id", "profiles"),
        _pk("ledger_entries"),
    )

    op.create_table(
        "eventos_pasarela",
        _uuid("id"),
        sa.Column("proveedor", sa.String(), nullable=False),
        sa.Column("evento_externo_id", sa.String(), nullable=False),
        sa.Column("tipo", sa.String(), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        _tz("procesado_en"),
        sa.Column("error", sa.String(), nullable=True),
        *_timestamps(),
        sa.UniqueConstraint(
            "proveedor",
            "evento_externo_id",
            name="uq_eventos_pasarela_proveedor_evento_externo_id",
        ),
        _pk("eventos_pasarela"),
    )

    # 10. Metricas
    op.create_table(
        "post_views",
        _uuid("id"),
        _uuid("publicacion_id"),
        _uuid("profile_id"),
        sa.Column("dia", sa.Date(), nullable=False),
        *_timestamps(),
        _fk("post_views", "publicacion_id", "publicaciones", "CASCADE"),
        _fk("post_views", "profile_id", "profiles", "CASCADE"),
        sa.UniqueConstraint(
            "publicacion_id",
            "profile_id",
            "dia",
            name="uq_post_views_publicacion_id_profile_id_dia",
        ),
        _pk("post_views"),
    )

    # 11. Operacion
    op.create_table(
        "jobs",
        _uuid("id"),
        sa.Column("type", sa.String(), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("max_attempts", sa.Integer(), nullable=False),
        _tz("run_after", nullable=False),
        _tz("locked_at"),
        sa.Column("locked_by", sa.String(), nullable=True),
        sa.Column("last_error", sa.String(), nullable=True),
        *_timestamps(),
        _pk("jobs"),
    )
    op.create_index("ix_jobs_status", "jobs", ["status"])
    op.create_index("ix_jobs_type", "jobs", ["type"])

    op.create_table(
        "reportes",
        _uuid("id"),
        _uuid("reporter_id"),
        sa.Column("target_type", sa.String(), nullable=False),
        _uuid("target_id"),
        sa.Column("reason", sa.String(), nullable=False),
        sa.Column("estado", _enum("estado_reporte"), nullable=False),
        *_timestamps(),
        _pk("reportes"),
    )

    op.create_table(
        "moderation_actions",
        _uuid("id"),
        _uuid("admin_id"),
        sa.Column("target_type", sa.String(), nullable=False),
        _uuid("target_id"),
        sa.Column("action", sa.String(), nullable=False),
        sa.Column("nota", sa.String(), nullable=True),
        *_timestamps(),
        _pk("moderation_actions"),
    )

    # 12. RLS activo y sin politicas: la app solo entra por la API
    for table in [*TABLES, "alembic_version"]:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;")


def downgrade() -> None:
    op.execute("ALTER TABLE alembic_version DISABLE ROW LEVEL SECURITY;")

    for table in reversed(TABLES):
        op.drop_table(table)

    for name in reversed(ENUMS):
        op.execute(f"DROP TYPE {name};")
