"""Sincronización idempotente (RNF-07). Los `datos` se guardan cifrados (RNF-02)."""

from collections import Counter
from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import iso
from app.db import obtener_sesion
from app.esquemas import EventoEntrada, SyncEntrada
from app.modelos import EventoSync, Usuario
from app.seguridad import cifrar_datos, usuario_actual

router = APIRouter(prefix="/sync", tags=["sincronización"])

TIPOS = ["animo", "cumplimiento", "descanso", "escudo", "tarea", "perfil", "riesgo"]


def _es_dia(valor) -> bool:
    try:
        date.fromisoformat(str(valor))
        return True
    except ValueError:
        return False


def _entero_en(valor, minimo: int, maximo: int) -> bool:
    return isinstance(valor, int) and not isinstance(valor, bool) and minimo <= valor <= maximo


def datos_validos(tipo: str, d: dict) -> bool:
    """Revisión ligera de los campos importantes de cada tipo (se permiten campos extra)."""
    if tipo in ("animo", "cumplimiento", "descanso", "escudo", "riesgo") and not _es_dia(d.get("dia")):
        return False
    if tipo == "animo":
        return _entero_en(d.get("animo"), 1, 5) and _entero_en(d.get("energia"), 1, 3)
    if tipo == "cumplimiento":
        return _entero_en(d.get("hora"), 0, 23)
    if tipo == "riesgo":
        return d.get("riesgo") in ("ALTO", "BAJO")
    if tipo == "tarea":
        return bool(d.get("id")) and bool(d.get("titulo"))
    return True  # descanso, escudo, perfil


def leer_fecha(texto: str) -> datetime | None:
    """ISO-8601 → datetime sin zona (si trae zona se pasa a UTC)."""
    try:
        instante = datetime.fromisoformat(texto)
    except ValueError:
        return None
    if instante.tzinfo is not None:
        instante = instante.astimezone(timezone.utc).replace(tzinfo=None)
    return instante


@router.post("")
def sincronizar(
    entrada: SyncEntrada,
    usuario: Usuario = Depends(usuario_actual),
    sesion: Session = Depends(obtener_sesion),
):
    ids = [e.id for e in entrada.eventos]
    existentes = set(
        sesion.scalars(
            select(EventoSync.evento_id).where(EventoSync.usuario_id == usuario.id, EventoSync.evento_id.in_(ids))
        )
    ) if ids else set()

    aceptados, duplicados, rechazados = [], [], []
    vistos: set[str] = set()
    for evento in entrada.eventos:
        if evento.id in existentes or evento.id in vistos:
            duplicados.append(evento.id)
            continue
        fecha = leer_fecha(evento.fecha)
        if evento.tipo not in TIPOS or fecha is None or not datos_validos(evento.tipo, evento.datos):
            rechazados.append(evento.id)
            continue
        sesion.add(_nuevo_evento(usuario, evento, fecha))
        vistos.add(evento.id)
        aceptados.append(evento.id)

    sesion.commit()
    return {"aceptados": aceptados, "duplicados": duplicados, "rechazados": rechazados}


def _nuevo_evento(usuario: Usuario, evento: EventoEntrada, fecha: datetime) -> EventoSync:
    return EventoSync(
        usuario_id=usuario.id,
        evento_id=evento.id,
        tipo=evento.tipo,
        fecha=fecha,
        datos_cifrados=cifrar_datos(evento.datos),
    )


@router.get("/resumen")
def resumen(usuario: Usuario = Depends(usuario_actual), sesion: Session = Depends(obtener_sesion)):
    filas = sesion.execute(
        select(EventoSync.tipo, func.count()).where(EventoSync.usuario_id == usuario.id).group_by(EventoSync.tipo)
    ).all()
    por_tipo = Counter({tipo: 0 for tipo in TIPOS})
    por_tipo.update(dict(filas))
    ultimo = sesion.scalar(select(func.max(EventoSync.recibido)).where(EventoSync.usuario_id == usuario.id))
    return {"total": sum(por_tipo.values()), "por_tipo": dict(por_tipo), "ultimo": iso(ultimo)}
