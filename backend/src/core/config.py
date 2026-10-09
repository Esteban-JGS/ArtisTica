from decimal import Decimal

from pydantic import AnyHttpUrl, Field, PostgresDsn, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Valores de ENVIRONMENT que activan las reglas de produccion
ENTORNOS_PRODUCCION = frozenset({"production", "prod"})


class Settings(BaseSettings):
    PROJECT_NAME: str = "ArtisTica"
    API_V1_STR: str = "/api/v1"

    # Supabase / Database
    # Puerto 6543, pooler (Supavisor)
    DATABASE_URL: PostgresDsn
    # Puerto 5432, conexion directa para Alembic
    ALEMBIC_DATABASE_URL: PostgresDsn

    SUPABASE_URL: AnyHttpUrl
    # Clave service_role: salta RLS. Solo servidor, jamas en el cliente movil.
    SUPABASE_SERVICE_KEY: str | None = None

    # Environment
    ENVIRONMENT: str = "dev"
    SENTRY_DSN: str | None = None
    # Fraccion de trazas que se mandan a Sentry, entre 0 y 1
    SENTRY_TRACES_SAMPLE_RATE: float = Field(default=0.1, ge=0, le=1)
    # Procesos de uvicorn. Los adaptadores falsos guardan estado por proceso.
    WORKERS: int = Field(default=1, ge=1)
    # Pasarse a Estudio sin cobro. Solo para la demo: apagado en produccion.
    ESTUDIO_AUTOSERVICIO: bool = True

    # Pasarela de pagos. Texto libre: la valida src.payments.fabrica
    PASARELA: str = "falsa"
    # A donde vuelve la app despues del 3DS. Si el proveedor no acepta el
    # esquema propio (pregunta 19 de las preguntas al proveedor, en
    # orquestacion/), se cambia por una pagina https
    URL_RETORNO_PAGO: str = "artistica://pago"

    # Almacenamiento de medios. Texto libre: lo valida src.storage
    ALMACENAMIENTO: str = "falso"
    ALMACENAMIENTO_TIMEOUT_SEGUNDOS: int = 15
    BUCKET_MEDIOS: str = "medios"
    # Privado (D12): los archivos finales solo salen con URL firmada
    BUCKET_ENTREGABLES: str = "entregables"
    # Vigencia de la URL firmada para descargar un archivo final
    DESCARGA_FIRMADA_SEGUNDOS: int = Field(default=600, ge=60, le=3600)
    MEDIO_TAMANO_MAXIMO_BYTES: int = 5 * 1024 * 1024
    MEDIOS_PENDIENTES_MAXIMOS: int = 20

    # Politicas de pedido (D5). Unico lugar donde viven sus valores por defecto.
    ANTICIPO_PORCENTAJE_MINIMO: Decimal = Decimal("30")
    ANTICIPO_PORCENTAJE_MAXIMO: Decimal = Decimal("50")
    ANTICIPO_PORCENTAJE_DEFECTO: Decimal = Decimal("50")
    DIAS_VENTANA_DISPUTA: int = 7
    CANCELACION_EVENTO_DIAS_TOTAL: int = 30
    CANCELACION_EVENTO_DIAS_PARCIAL: int = 7
    CANCELACION_EVENTO_PORCENTAJE_PARCIAL: Decimal = Decimal("50")
    MONTO_MINIMO_PEDIDO: Decimal = Decimal("2500.00")
    # Limites del plan Taller (D11). Estudio no tiene limite.
    LIMITE_SERVICIOS_TALLER: int = Field(default=2, ge=1)
    LIMITE_OBRAS_DISPONIBLES_TALLER: int = Field(default=5, ge=1)
    # Imagenes por obra, para cualquier plan
    MEDIOS_POR_OBRA_MAXIMO: int = Field(default=10, ge=1)
    # Imagenes por publicacion del feed
    MEDIOS_POR_PUBLICACION_MAXIMO: int = Field(default=10, ge=1)
    # Explorar: una de cada N posiciones es de un nuevo talento
    EXPLORAR_CADA_N: int = Field(default=5, ge=2)
    # Un artista con menos seguidores que esto es nuevo talento
    NUEVO_TALENTO_MAX_SEGUIDORES: int = Field(default=50, ge=1)
    # Paginacion por cursor de los listados
    PAGINA_TAMANO_DEFECTO: int = Field(default=20, ge=1)
    PAGINA_TAMANO_MAXIMO: int = Field(default=50, ge=1)
    # Consultas: una cuenta con menos de estos dias abre pocas por cada 24 horas
    DIAS_CUENTA_RECIENTE: int = Field(default=7, ge=1)
    CONSULTAS_POR_DIA_CUENTA_RECIENTE: int = Field(default=5, ge=1)
    TARIFA_TALLER_PORCENTAJE: Decimal = Decimal("8")
    TARIFA_ESTUDIO_PORCENTAJE: Decimal = Decimal("5")
    # D9. Cuanto se supone que dura una autorizacion cuando la pasarela no
    # informa el vencimiento.
    DIAS_VIGENCIA_AUTORIZACION_SUPUESTA: int = Field(default=5, ge=1)
    # Dias para volver a autorizar un saldo vencido, contados desde que vencio
    DIAS_REAUTORIZACION_SALDO: int = Field(default=7, ge=1)
    # Minutos sin terminar el 3DS de La quiero para soltar la obra (DT25)
    MINUTOS_ABANDONO_3DS: int = Field(default=30, ge=5)

    # Barrido de vencimientos, dentro del proceso de la API
    BARRIDO_ACTIVO: bool = True
    BARRIDO_INTERVALO_SEGUNDOS: int = Field(default=60, ge=10)
    # Un job en processing por mas de esto cuenta como un intento fallido
    JOB_TIEMPO_MAXIMO_MINUTOS: int = Field(default=15, ge=1)

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=True, extra="ignore"
    )

    @model_validator(mode="after")
    def _rechazar_combinaciones_inseguras(self) -> "Settings":
        # Se normaliza igual que en las fabricas de pasarela y almacenamiento
        pasarela_falsa = self.PASARELA.strip().lower() == "falsa"
        almacenamiento_falso = self.ALMACENAMIENTO.strip().lower() == "falso"
        errores: list[str] = []
        if self.ENVIRONMENT.strip().lower() in ENTORNOS_PRODUCCION:
            if pasarela_falsa:
                errores.append("PASARELA=falsa no se permite en produccion")
            if almacenamiento_falso:
                errores.append("ALMACENAMIENTO=falso no se permite en produccion")
            if self.ESTUDIO_AUTOSERVICIO:
                errores.append(
                    "ESTUDIO_AUTOSERVICIO tiene que estar apagado en produccion"
                )
        if self.WORKERS > 1 and (pasarela_falsa or almacenamiento_falso):
            # Cada proceso tendria su propio estado en memoria
            errores.append(
                "WORKERS mayor que 1 no se permite con PASARELA=falsa "
                "o ALMACENAMIENTO=falso"
            )
        # DT21: con paginas mas chicas que N, la cuota de nuevos talentos da 0
        errores.extend(
            f"EXPLORAR_CADA_N ({self.EXPLORAR_CADA_N}) no puede ser mayor "
            f"que {nombre} ({tamano})"
            for nombre, tamano in (
                ("PAGINA_TAMANO_DEFECTO", self.PAGINA_TAMANO_DEFECTO),
                ("PAGINA_TAMANO_MAXIMO", self.PAGINA_TAMANO_MAXIMO),
            )
            if tamano < self.EXPLORAR_CADA_N
        )
        # Un archivo final en el bucket publico se descargaria sin pagar
        if self.BUCKET_ENTREGABLES.strip() == self.BUCKET_MEDIOS.strip():
            errores.append("BUCKET_ENTREGABLES tiene que ser distinto de BUCKET_MEDIOS")
        if errores:
            raise ValueError("; ".join(errores))
        return self


settings = Settings()
