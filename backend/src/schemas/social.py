"""Esquemas de seguir: el resumen del perfil y las listas de seguidores."""

from typing import Self

from pydantic import BaseModel

from src.domain.enums import RolPerfil
from src.models import Profile
from src.services.social import Resumen


class ResumenSocial(BaseModel):
    seguidores: int
    siguiendo: int
    # Nulo sin token; falso en el propio perfil
    lo_sigo: bool | None

    @classmethod
    def desde(cls, resumen: Resumen) -> Self:
        return cls(
            seguidores=resumen.seguidores,
            siguiendo=resumen.siguiendo,
            lo_sigo=resumen.lo_sigo,
        )


class PerfilResumido(BaseModel):
    handle: str
    nombre: str
    verificado: bool
    es_artista: bool

    @classmethod
    def desde(cls, perfil: Profile) -> Self:
        return cls(
            handle=perfil.handle,
            nombre=perfil.nombre,
            verificado=perfil.is_verified,
            es_artista=perfil.rol == RolPerfil.ARTISTA,
        )
