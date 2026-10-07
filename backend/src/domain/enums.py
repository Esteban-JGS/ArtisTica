"""Enums del dominio. Solo biblioteca estandar: los modelos los importan de aca."""

import enum

# Perfiles


class RolPerfil(enum.StrEnum):
    PUBLICO = "publico"
    ARTISTA = "artista"
    ADMIN = "admin"


class PlanArtista(enum.StrEnum):
    TALLER = "taller"
    ESTUDIO = "estudio"


class EstadoOnboarding(enum.StrEnum):
    NO_INICIADO = "no_iniciado"
    PENDIENTE = "pendiente"
    COMPLETADO = "completado"
    RECHAZADO = "rechazado"


# Catalogo


class EstadoObra(enum.StrEnum):
    EXHIBICION = "exhibicion"
    DISPONIBLE = "disponible"
    VENDIDA = "vendida"


class TipoServicio(enum.StrEnum):
    ENCARGO = "encargo"
    EVENTO = "evento"


# Consultas


class EstadoConsulta(enum.StrEnum):
    ABIERTA = "abierta"
    COTIZADA = "cotizada"
    CONVERTIDA = "convertida"
    DESCARTADA = "descartada"


# Medios


class EstadoMedia(enum.StrEnum):
    PENDIENTE = "pendiente"
    PROCESADO = "procesado"
    FALLIDO = "fallido"


# Pedidos


class TipoPedido(enum.StrEnum):
    ENCARGO = "encargo"
    EVENTO = "evento"
    OBRA_DISPONIBLE = "obra_disponible"


class EstadoPedido(enum.StrEnum):
    COTIZADO = "cotizado"
    ANTICIPO_PAGADO = "anticipo_pagado"
    EN_PROCESO = "en_proceso"
    VISTA_PREVIA_ENTREGADA = "vista_previa_entregada"
    SALDO_PAGADO = "saldo_pagado"
    COMPLETADO = "completado"
    RECHAZADO = "rechazado"
    CANCELADO = "cancelado"
    EN_DISPUTA = "en_disputa"


class TipoEntregable(enum.StrEnum):
    VISTA_PREVIA = "vista_previa"
    FINAL = "final"


class EstadoDisputa(enum.StrEnum):
    ABIERTA = "abierta"
    EN_REVISION = "en_revision"
    RESUELTA = "resuelta"


class TipoCobro(enum.StrEnum):
    ANTICIPO = "anticipo"
    SALDO = "saldo"
    TOTAL = "total"


class EstadoCobro(enum.StrEnum):
    PENDIENTE = "pendiente"
    AUTORIZADO = "autorizado"
    CAPTURADO = "capturado"
    CANCELADO = "cancelado"
    REEMBOLSADO = "reembolsado"
    VENCIDO = "vencido"


# Operacion


class EstadoReporte(enum.StrEnum):
    PENDIENTE = "pendiente"
    REVISADO = "revisado"
    DESCARTADO = "descartado"
