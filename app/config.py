"""Configuración leída de variables de entorno.

Todas las variables tienen un valor por defecto pensado SOLO para desarrollo.
En un despliegue real se definen en el archivo .env (ver .env.example).
"""

import logging
import os
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

log = logging.getLogger("brota")

SECRETO_DESARROLLO = "secreto-de-desarrollo-cambialo"
CLAVE_DESARROLLO = "clave-de-datos-de-desarrollo-cambiala"


def _lista(valor: str) -> list[str]:
    return [v.strip() for v in valor.split(",") if v.strip()]


@dataclass
class Configuracion:
    database_url: str = field(
        default_factory=lambda: os.getenv("DATABASE_URL", "sqlite:///./brota_local.db")
    )
    jwt_secreto: str = field(
        default_factory=lambda: os.getenv("BROTA_JWT_SECRETO", SECRETO_DESARROLLO)
    )
    clave_datos: str = field(
        default_factory=lambda: os.getenv("BROTA_CLAVE_DATOS", CLAVE_DESARROLLO)
    )
    admin_correo: str = field(default_factory=lambda: os.getenv("ADMIN_CORREO", ""))
    admin_password: str = field(default_factory=lambda: os.getenv("ADMIN_PASSWORD", ""))
    cors_origenes: list[str] = field(
        default_factory=lambda: _lista(os.getenv("BROTA_CORS_ORIGENES", "*"))
    )
    # Zona horaria con la que se decide "qué día es hoy" (señales del fantasma, edad).
    zona_horaria: str = field(
        default_factory=lambda: os.getenv("BROTA_ZONA_HORARIA", "America/Mexico_City")
    )
    jwt_dias: int = 7

    def advertir_si_inseguro(self) -> None:
        if self.jwt_secreto == SECRETO_DESARROLLO or self.clave_datos == CLAVE_DESARROLLO:
            log.warning(
                "Se están usando secretos de DESARROLLO. Define BROTA_JWT_SECRETO y "
                "BROTA_CLAVE_DATOS en el archivo .env antes de usar datos reales."
            )


config = Configuracion()


def ahora() -> datetime:
    """Instante actual en UTC sin zona (así se guarda en la base de datos)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def hoy() -> date:
    """Fecha de hoy según la zona horaria configurada."""
    return datetime.now(ZoneInfo(config.zona_horaria)).date()


def dia_local(instante_utc: datetime) -> date:
    """Convierte un instante UTC (sin zona) al día local configurado."""
    return instante_utc.replace(tzinfo=timezone.utc).astimezone(ZoneInfo(config.zona_horaria)).date()


def iso(instante_utc: datetime | None) -> str | None:
    """Instante UTC → texto ISO-8601 con 'Z'."""
    if instante_utc is None:
        return None
    return instante_utc.replace(microsecond=0).isoformat() + "Z"
