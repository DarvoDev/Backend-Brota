"""Punto de entrada de la API de Brota."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app import VERSION
from app.config import config
from app.db import Base, SesionLocal, esperar_base_de_datos, motor
from app.rutas import auth, comunidad, contenido, fantasma, mensajes, moderacion, riesgo, sync
from app.semilla import cargar_semilla, crear_admin

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
PREFIJO = "/api/v1"


@asynccontextmanager
async def ciclo_de_vida(_app: FastAPI):
    config.advertir_si_inseguro()
    esperar_base_de_datos()
    Base.metadata.create_all(motor)
    with SesionLocal() as sesion:
        cargar_semilla(sesion)
        crear_admin(sesion, config.admin_correo, config.admin_password)
    yield


app = FastAPI(
    title="Brota API",
    version=VERSION,
    description="Backend opcional de Brota: cuentas, sincronización, compañero fantasma, muro y contenido.",
    lifespan=ciclo_de_vida,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.cors_origenes,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------- Errores siempre como {"detail": "<mensaje en español>"} ----------

MENSAJES_HTTP = {404: "Recurso no encontrado", 405: "Método no permitido"}

TRADUCCIONES = {
    "missing": "es obligatorio",
    "string_type": "debe ser texto",
    "int_type": "debe ser un número entero",
    "int_parsing": "debe ser un número entero",
    "float_parsing": "debe ser un número",
    "bool_parsing": "debe ser verdadero o falso",
    "bool_type": "debe ser verdadero o falso",
    "date_from_datetime_parsing": "debe ser una fecha aaaa-mm-dd",
    "date_parsing": "debe ser una fecha aaaa-mm-dd",
    "literal_error": "no es un valor permitido",
    "extra_forbidden": "no se acepta",
    "too_short": "es demasiado corto",
    "too_long": "es demasiado largo",
    "string_too_short": "es demasiado corto",
    "string_too_long": "es demasiado largo",
    "greater_than_equal": "es demasiado pequeño",
    "less_than_equal": "es demasiado grande",
    "json_invalid": "el JSON no es válido",
    "model_attributes_type": "debe ser un objeto JSON",
    "dict_type": "debe ser un objeto JSON",
    "list_type": "debe ser una lista",
}


@app.exception_handler(RequestValidationError)
async def error_validacion(_request, exc: RequestValidationError):
    partes = []
    for error in exc.errors():
        campo = ".".join(str(p) for p in error["loc"] if p != "body") or "cuerpo"
        partes.append(f"'{campo}' {TRADUCCIONES.get(error['type'], 'no es válido')}")
    return JSONResponse(status_code=422, content={"detail": "Datos inválidos: " + "; ".join(partes)})


@app.exception_handler(StarletteHTTPException)
async def error_http(_request, exc: StarletteHTTPException):
    if isinstance(exc.detail, dict):  # p. ej. {"detail": "...", "clasificacion": {...}}
        contenido = exc.detail
    elif isinstance(exc, HTTPException) or exc.status_code not in MENSAJES_HTTP:
        contenido = {"detail": exc.detail}
    else:
        contenido = {"detail": MENSAJES_HTTP[exc.status_code]}
    return JSONResponse(status_code=exc.status_code, content=contenido, headers=getattr(exc, "headers", None))


# ---------- Rutas ----------


@app.get(f"{PREFIJO}/salud", tags=["salud"])
def salud():
    return {"estado": "ok", "version": VERSION}


for modulo in (auth, sync, fantasma, comunidad, mensajes, riesgo, moderacion):
    app.include_router(modulo.router, prefix=PREFIJO)
app.include_router(contenido.publico, prefix=PREFIJO)
app.include_router(contenido.admin, prefix=PREFIJO)
