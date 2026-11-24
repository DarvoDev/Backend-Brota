"""Moderación del muro por parte de administradores (CU-24)."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import iso
from app.db import obtener_sesion
from app.esquemas import ResolverEntrada
from app.modelos import Publicacion, Reporte
from app.seguridad import solo_admin

router = APIRouter(prefix="/admin/reportes", tags=["administración"], dependencies=[Depends(solo_admin)])


@router.get("")
def pendientes(sesion: Session = Depends(obtener_sesion)):
    filas = sesion.execute(
        select(Reporte, Publicacion.texto)
        .join(Publicacion, Reporte.publicacion_id == Publicacion.id)
        .where(Reporte.pendiente.is_(True))
        .order_by(Reporte.creado)
    ).all()
    return [
        {"id": r.id, "publicacion_id": r.publicacion_id, "texto": texto, "motivo": r.motivo, "fecha": iso(r.creado)}
        for r, texto in filas
    ]


@router.post("/{reporte_id}/resolver")
def resolver(reporte_id: str, entrada: ResolverEntrada, sesion: Session = Depends(obtener_sesion)):
    reporte = sesion.get(Reporte, reporte_id)
    if reporte is None:
        raise HTTPException(404, "El reporte no existe")
    if not reporte.pendiente:
        raise HTTPException(409, "Este reporte ya fue resuelto")

    publicacion = sesion.get(Publicacion, reporte.publicacion_id)
    publicacion.visible = entrada.accion == "mantener"
    # La decisión aplica a todos los reportes pendientes de esa publicación.
    otros = sesion.scalars(
        select(Reporte).where(Reporte.publicacion_id == publicacion.id, Reporte.pendiente.is_(True))
    )
    resueltos = 0
    for r in otros:
        r.pendiente = False
        r.accion = entrada.accion
        resueltos += 1
    sesion.commit()
    return {
        "id": reporte.id,
        "publicacion_id": publicacion.id,
        "accion": entrada.accion,
        "visible": publicacion.visible,
        "reportes_resueltos": resueltos,
    }
