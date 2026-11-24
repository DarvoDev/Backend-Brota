"""Tablas de la base de datos (SQLAlchemy 2)."""

import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.config import ahora
from app.db import Base


def nuevo_id() -> str:
    return str(uuid.uuid4())


class Usuario(Base):
    __tablename__ = "usuarios"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=nuevo_id)
    correo: Mapped[str] = mapped_column(String(254), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(100))
    nombre: Mapped[str] = mapped_column(String(80))
    fecha_nac: Mapped[date] = mapped_column(Date)
    rol: Mapped[str] = mapped_column(String(20), default="usuario")  # usuario | administrador
    consentimiento_tutor: Mapped[bool] = mapped_column(Boolean, default=False)
    creado: Mapped[datetime] = mapped_column(DateTime, default=ahora)


class EventoSync(Base):
    """Evento sincronizado desde la app. `datos_cifrados` va cifrado con Fernet (RNF-02)."""

    __tablename__ = "eventos_sync"
    __table_args__ = (UniqueConstraint("usuario_id", "evento_id", name="uq_evento_usuario"),)

    pk: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    usuario_id: Mapped[str] = mapped_column(ForeignKey("usuarios.id", ondelete="CASCADE"), index=True)
    evento_id: Mapped[str] = mapped_column(String(64))
    tipo: Mapped[str] = mapped_column(String(20))
    fecha: Mapped[datetime] = mapped_column(DateTime)
    datos_cifrados: Mapped[str] = mapped_column(Text)
    recibido: Mapped[datetime] = mapped_column(DateTime, default=ahora)


class PesosRiesgo(Base):
    """Pesos del perceptrón de cada usuario (JSON con 8 números)."""

    __tablename__ = "pesos_riesgo"

    usuario_id: Mapped[str] = mapped_column(ForeignKey("usuarios.id", ondelete="CASCADE"), primary_key=True)
    pesos: Mapped[str] = mapped_column(Text)
    sesgo: Mapped[float] = mapped_column(Float)
    actualizado: Mapped[datetime] = mapped_column(DateTime, default=ahora)


class SenalFantasma(Base):
    """'Completé mi misión de hoy'. Una por usuario y día."""

    __tablename__ = "senales_fantasma"
    __table_args__ = (UniqueConstraint("usuario_id", "dia", name="uq_senal_dia"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=nuevo_id)
    usuario_id: Mapped[str] = mapped_column(ForeignKey("usuarios.id", ondelete="CASCADE"), index=True)
    dia: Mapped[date] = mapped_column(Date)
    creada: Mapped[datetime] = mapped_column(DateTime, default=ahora)


class ReaccionFantasma(Base):
    __tablename__ = "reacciones_fantasma"
    __table_args__ = (UniqueConstraint("senal_id", "usuario_id", name="uq_reaccion_usuario"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=nuevo_id)
    senal_id: Mapped[str] = mapped_column(ForeignKey("senales_fantasma.id", ondelete="CASCADE"), index=True)
    usuario_id: Mapped[str] = mapped_column(ForeignKey("usuarios.id", ondelete="CASCADE"), index=True)
    reaccion: Mapped[str] = mapped_column(String(20))
    creada: Mapped[datetime] = mapped_column(DateTime, default=ahora)
    entregada: Mapped[bool] = mapped_column(Boolean, default=False)


class FraseMuro(Base):
    __tablename__ = "frases_muro"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    texto: Mapped[str] = mapped_column(String(200))
    orden: Mapped[int] = mapped_column(Integer, default=0)


class Publicacion(Base):
    __tablename__ = "publicaciones"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=nuevo_id)
    usuario_id: Mapped[str] = mapped_column(ForeignKey("usuarios.id", ondelete="CASCADE"), index=True)
    texto: Mapped[str] = mapped_column(String(200))
    es_logro: Mapped[bool] = mapped_column(Boolean, default=False)
    visible: Mapped[bool] = mapped_column(Boolean, default=True)
    creada: Mapped[datetime] = mapped_column(DateTime, default=ahora)


class Reporte(Base):
    __tablename__ = "reportes"
    __table_args__ = (UniqueConstraint("publicacion_id", "usuario_id", name="uq_reporte_usuario"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=nuevo_id)
    publicacion_id: Mapped[str] = mapped_column(ForeignKey("publicaciones.id", ondelete="CASCADE"), index=True)
    usuario_id: Mapped[str] = mapped_column(ForeignKey("usuarios.id", ondelete="CASCADE"))
    motivo: Mapped[str] = mapped_column(String(300), default="")
    creado: Mapped[datetime] = mapped_column(DateTime, default=ahora)
    pendiente: Mapped[bool] = mapped_column(Boolean, default=True)
    accion: Mapped[str | None] = mapped_column(String(20), nullable=True)  # ocultar | mantener


class ActividadCatalogo(Base):
    __tablename__ = "catalogo"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    titulo: Mapped[str] = mapped_column(String(120))
    esfuerzo: Mapped[int] = mapped_column(Integer)
    duracion_min: Mapped[int] = mapped_column(Integer)
    orden: Mapped[int] = mapped_column(Integer, default=0)


class MensajeValidado(Base):
    __tablename__ = "mensajes"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    texto: Mapped[str] = mapped_column(String(300))
    categoria: Mapped[str] = mapped_column(String(40))
    validado_por: Mapped[str] = mapped_column(String(80))
    orden: Mapped[int] = mapped_column(Integer, default=0)


class RecursoAyuda(Base):
    __tablename__ = "directorio"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    nombre: Mapped[str] = mapped_column(String(120))
    telefono: Mapped[str] = mapped_column(String(30))
    descripcion: Mapped[str] = mapped_column(String(300))
    es_emergencia: Mapped[bool] = mapped_column(Boolean, default=False)
    categoria: Mapped[str] = mapped_column(String(60))
    orden: Mapped[int] = mapped_column(Integer, default=0)
