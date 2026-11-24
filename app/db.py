"""Conexión a la base de datos (PostgreSQL en Docker, SQLite en pruebas)."""

import logging
import time

from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import config

log = logging.getLogger("brota")


class Base(DeclarativeBase):
    pass


def crear_motor(url: str):
    opciones = {"pool_pre_ping": True}
    if url.startswith("sqlite"):
        opciones = {"connect_args": {"check_same_thread": False}}
    return create_engine(url, **opciones)


motor = crear_motor(config.database_url)
SesionLocal = sessionmaker(bind=motor, autoflush=False, expire_on_commit=False)


def obtener_sesion():
    """Dependencia de FastAPI: abre una sesión por petición y la cierra al final."""
    sesion = SesionLocal()
    try:
        yield sesion
    finally:
        sesion.close()


def esperar_base_de_datos(intentos: int = 10) -> None:
    """Reintenta la conexión unos segundos (la base puede tardar en arrancar)."""
    for intento in range(1, intentos + 1):
        try:
            with motor.connect() as conexion:
                conexion.execute(text("SELECT 1"))
            return
        except Exception as error:  # noqa: BLE001
            log.warning("Base de datos no disponible (intento %s): %s", intento, error)
            time.sleep(2)
    raise RuntimeError("No se pudo conectar a la base de datos")
