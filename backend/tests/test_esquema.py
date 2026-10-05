"""Esquema: dominio puro, defectos en la base y moderacion (lote 5d)."""

import os
import subprocess
import sys
import uuid
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

import src.domain.enums as enums_dominio
import src.models as modelos
from src.models import Base

RAIZ_BACKEND = Path(__file__).resolve().parents[1]
TABLAS_MODERACION = ("reportes", "acciones_moderacion")
COLUMNAS_INGLES = (
    "reporter_id",
    "admin_id",
    "target_type",
    "target_id",
    "reason",
    "action",
)


def _columnas_con_default() -> list[tuple[str, str]]:
    return [
        (tabla.name, columna.name)
        for tabla in Base.metadata.sorted_tables
        for columna in tabla.columns
        if columna.default is not None
    ]


def test_01_dominio_no_carga_sqlalchemy():
    codigo = (
        "import sys\n"
        "import src.domain.pedidos, src.domain.perfiles, src.domain.medios\n"
        "import src.domain.politicas, src.domain.enums\n"
        "cargados = [m for m in sys.modules if m.startswith('sqlalchemy')]\n"
        "assert not cargados, cargados\n"
    )
    resultado = subprocess.run(
        [sys.executable, "-c", codigo],
        cwd=RAIZ_BACKEND,
        env=os.environ.copy(),
        capture_output=True,
        text=True,
    )
    assert resultado.returncode == 0, resultado.stderr


def test_02_modelos_reexportan_la_misma_clase():
    assert modelos.PlanArtista is enums_dominio.PlanArtista
    assert modelos.EstadoPedido is enums_dominio.EstadoPedido
    assert modelos.EstadoReporte is enums_dominio.EstadoReporte


async def test_03_todo_default_tiene_server_default(async_session: AsyncSession):
    columnas = _columnas_con_default()
    assert columnas

    sin_server_default = [
        (tabla, columna)
        for tabla, columna in columnas
        if Base.metadata.tables[tabla].columns[columna].server_default is None
    ]
    assert sin_server_default == []

    filas = await async_session.execute(
        text(
            "SELECT table_name, column_name FROM information_schema.columns "
            "WHERE table_schema = 'public' AND column_default IS NOT NULL"
        )
    )
    en_la_base = {(f.table_name, f.column_name) for f in filas}
    assert [c for c in columnas if c not in en_la_base] == []


async def test_04_insert_crudo_en_profiles(async_session: AsyncSession):
    perfil_id = uuid.uuid4()
    await async_session.execute(
        text("INSERT INTO profiles (id, handle, nombre) VALUES (:id, :h, :n)"),
        {"id": perfil_id, "h": f"crudo_{perfil_id.hex[:8]}", "n": "Crudo"},
    )
    fila = (
        await async_session.execute(
            text(
                "SELECT rol::text, plan::text, is_verified, "
                "pasarela_onboarding::text, categorias, created_at, updated_at "
                "FROM profiles WHERE id = :id"
            ),
            {"id": perfil_id},
        )
    ).one()
    assert fila.rol == "publico"
    assert fila.plan == "taller"
    assert fila.is_verified is False
    assert fila.pasarela_onboarding == "no_iniciado"
    assert fila.categorias == []
    assert fila.created_at is not None
    assert fila.updated_at is not None


async def test_05_insert_crudo_en_jobs(async_session: AsyncSession):
    fila = (
        await async_session.execute(
            text(
                "INSERT INTO jobs (type, payload, run_after) "
                "VALUES ('prueba_esquema', '{}'::jsonb, now()) "
                "RETURNING id, status, attempts, max_attempts"
            )
        )
    ).one()
    assert isinstance(fila.id, uuid.UUID)
    assert fila.status == "pending"
    assert fila.attempts == 0
    assert fila.max_attempts == 3


async def test_06_moderacion_en_espanol_con_llaves(async_session: AsyncSession):
    tablas = set(
        (
            await async_session.execute(
                text(
                    "SELECT table_name FROM information_schema.tables "
                    "WHERE table_schema = 'public' AND table_name = ANY(:t)"
                ),
                {"t": ["moderation_actions", "acciones_moderacion"]},
            )
        ).scalars()
    )
    assert tablas == {"acciones_moderacion"}

    en_ingles = (
        await async_session.execute(
            text(
                "SELECT table_name, column_name FROM information_schema.columns "
                "WHERE table_schema = 'public' AND table_name = ANY(:t) "
                "AND column_name = ANY(:c)"
            ),
            {"t": list(TABLAS_MODERACION), "c": list(COLUMNAS_INGLES)},
        )
    ).all()
    assert en_ingles == []

    llaves = {
        (f.tabla, f.columna, f.referida, f.al_borrar)
        for f in await async_session.execute(
            text(
                "SELECT kcu.table_name AS tabla, kcu.column_name AS columna, "
                "ccu.table_name AS referida, rc.delete_rule AS al_borrar "
                "FROM information_schema.referential_constraints rc "
                "JOIN information_schema.key_column_usage kcu "
                "ON kcu.constraint_name = rc.constraint_name "
                "JOIN information_schema.constraint_column_usage ccu "
                "ON ccu.constraint_name = rc.constraint_name "
                "WHERE kcu.table_name = ANY(:t)"
            ),
            {"t": list(TABLAS_MODERACION)},
        )
    }
    assert ("reportes", "reportante_id", "profiles", "SET NULL") in llaves
    assert ("acciones_moderacion", "moderador_id", "profiles", "SET NULL") in llaves


async def test_07_rls_activo_y_sin_politicas(async_session: AsyncSession):
    rls = dict(
        (
            await async_session.execute(
                text(
                    "SELECT relname, relrowsecurity FROM pg_class "
                    "WHERE relname = ANY(:t) AND relkind = 'r'"
                ),
                {"t": list(TABLAS_MODERACION)},
            )
        ).all()
    )
    assert rls == {"reportes": True, "acciones_moderacion": True}

    politicas = (
        await async_session.execute(
            text("SELECT count(*) FROM pg_policies WHERE tablename = ANY(:t)"),
            {"t": list(TABLAS_MODERACION)},
        )
    ).scalar_one()
    assert politicas == 0
