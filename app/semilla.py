"""Carga inicial: contenido de semilla.json y la cuenta de administrador."""

import json
import logging
from datetime import date
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modelos import ActividadCatalogo, FraseMuro, MensajeValidado, RecursoAyuda, Usuario
from app.seguridad import cifrar_password

log = logging.getLogger("brota")

RUTA_SEMILLA = Path(__file__).parent / "datos" / "semilla.json"

TABLAS = [
    ("catalogo", ActividadCatalogo),
    ("mensajes", MensajeValidado),
    ("directorio", RecursoAyuda),
    ("frases_muro", FraseMuro),
]


def cargar_semilla(sesion: Session) -> None:
    """Inserta el contenido inicial en cada tabla que esté vacía."""
    with RUTA_SEMILLA.open(encoding="utf-8") as archivo:
        semilla = json.load(archivo)
    for clave, modelo in TABLAS:
        if sesion.scalar(select(func.count()).select_from(modelo)):
            continue
        for orden, fila in enumerate(semilla[clave], start=1):
            sesion.add(modelo(orden=orden, **fila))
        log.info("Semilla cargada: %s (%s filas)", clave, len(semilla[clave]))
    sesion.commit()


def crear_admin(sesion: Session, correo: str, password: str) -> Usuario | None:
    """Crea la cuenta de administrador si no existe (o le da el rol si ya existía)."""
    if not correo or not password:
        return None
    correo = correo.strip().lower()
    usuario = sesion.scalar(select(Usuario).where(Usuario.correo == correo))
    if usuario is None:
        usuario = Usuario(
            correo=correo,
            password_hash=cifrar_password(password),
            nombre="Administración Brota",
            fecha_nac=date(2000, 1, 1),
            rol="administrador",
        )
        sesion.add(usuario)
        log.info("Administrador creado: %s", correo)
    else:
        usuario.rol = "administrador"
    sesion.commit()
    return usuario
