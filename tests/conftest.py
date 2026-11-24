"""Configuración de pruebas: SQLite en memoria mediante dependency override."""

import os

# Variables de entorno de prueba ANTES de importar la app.
os.environ["DATABASE_URL"] = "sqlite://"
os.environ["BROTA_JWT_SECRETO"] = "secreto-solo-para-pruebas"
os.environ["BROTA_CLAVE_DATOS"] = "clave-solo-para-pruebas"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app.db import Base, obtener_sesion  # noqa: E402
from app.main import app  # noqa: E402
from app.semilla import cargar_semilla, crear_admin  # noqa: E402

ADMIN_CORREO = "admin@brota.mx"
ADMIN_PASSWORD = "admin123"


@pytest.fixture
def motor():
    motor = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(motor)
    yield motor
    motor.dispose()


@pytest.fixture
def cliente(motor):
    Sesion = sessionmaker(bind=motor, autoflush=False, expire_on_commit=False)
    with Sesion() as sesion:
        cargar_semilla(sesion)
        crear_admin(sesion, ADMIN_CORREO, ADMIN_PASSWORD)

    def sesion_de_prueba():
        with Sesion() as sesion:
            yield sesion

    app.dependency_overrides[obtener_sesion] = sesion_de_prueba
    # Sin "with": no se ejecuta el ciclo de vida (que apunta a la base real).
    yield TestClient(app)
    app.dependency_overrides.clear()


_contador = {"n": 0}


def registrar(cliente, **cambios) -> dict:
    """Registra un usuario adulto nuevo y devuelve el cuerpo de la respuesta."""
    _contador["n"] += 1
    datos = {
        "correo": f"persona{_contador['n']}@correo.mx",
        "password": "secreta1",
        "nombre": "Persona",
        "fecha_nac": "2005-05-10",
        "acepta_privacidad": True,
        "consentimiento_tutor": False,
    }
    datos.update(cambios)
    respuesta = cliente.post("/api/v1/auth/registro", json=datos)
    assert respuesta.status_code == 201, respuesta.text
    return respuesta.json()


def cabecera(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def usuario(cliente):
    return cabecera(registrar(cliente)["token"])


@pytest.fixture
def admin(cliente):
    r = cliente.post("/api/v1/auth/login", json={"correo": ADMIN_CORREO, "password": ADMIN_PASSWORD})
    assert r.status_code == 200, r.text
    return cabecera(r.json()["token"])
