"""Modelos de entrada (pydantic v2). Las respuestas se arman como diccionarios simples."""

from datetime import date
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class Estricto(BaseModel):
    # Rechaza campos desconocidos (p. ej. texto libre en el muro).
    model_config = ConfigDict(extra="forbid")


# ---------- Cuentas ----------
class RegistroEntrada(BaseModel):
    correo: str
    password: str
    nombre: str
    fecha_nac: date
    acepta_privacidad: bool = False
    consentimiento_tutor: bool = False


class LoginEntrada(BaseModel):
    correo: str
    password: str


# ---------- Sincronización ----------
class EventoEntrada(BaseModel):
    id: str = Field(min_length=1, max_length=64)
    tipo: str
    fecha: str
    datos: dict[str, Any] = Field(default_factory=dict)


class SyncEntrada(BaseModel):
    eventos: list[EventoEntrada] = Field(max_length=1000)


# ---------- Fantasma ----------
class ReaccionEntrada(BaseModel):
    senal_id: str
    reaccion: Literal["bien_hecho", "tu_puedes", "sigue_asi"]


# ---------- Muro ----------
class Logro(BaseModel):
    racha: int = Field(ge=0, le=100000)
    xp: int = Field(ge=0, le=10000000)


class PublicacionEntrada(Estricto):
    frase_id: str | None = None
    logro: Logro | None = None


class ReporteEntrada(BaseModel):
    motivo: str = Field(default="", max_length=300)


class ResolverEntrada(BaseModel):
    accion: Literal["ocultar", "mantener"]


# ---------- Mensajes ----------
class TextoEntrada(BaseModel):
    texto: str = Field(max_length=1000)


# ---------- Contenido administrable ----------
class ActividadEntrada(BaseModel):
    id: str | None = Field(default=None, min_length=1, max_length=40)
    titulo: str = Field(min_length=1, max_length=120)
    esfuerzo: int = Field(ge=1, le=3)
    duracion_min: int = Field(ge=1, le=600)


class MensajeEntrada(BaseModel):
    id: str | None = Field(default=None, min_length=1, max_length=40)
    texto: str = Field(min_length=1, max_length=300)
    categoria: str = Field(min_length=1, max_length=40)
    validado_por: str | None = Field(default=None, max_length=80)


class RecursoEntrada(BaseModel):
    id: str | None = Field(default=None, min_length=1, max_length=40)
    nombre: str = Field(min_length=1, max_length=120)
    telefono: str = Field(min_length=1, max_length=30)
    descripcion: str = Field(default="", max_length=300)
    es_emergencia: bool = False
    categoria: str = Field(min_length=1, max_length=60)


# ---------- Riesgo ----------
class PrediccionEntrada(BaseModel):
    x: list[float] | None = None
    # Extensión opcional: día d con el que se calculan las entradas (por defecto, hoy).
    dia: date | None = None
