"""Muro de aliento moderado (CU-14, CU-23, CU-24).

No se acepta texto libre: solo frases predefinidas o un logro con números.
Con 3 reportes pendientes una publicación se oculta sola hasta que un admin decida.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import iso
from app.db import obtener_sesion
from app.esquemas import PublicacionEntrada, ReporteEntrada
from app.modelos import FraseMuro, Publicacion, Reporte, Usuario
from app.seguridad import usuario_actual

router = APIRouter(prefix="/comunidad", tags=["muro"])

REPORTES_PARA_OCULTAR = 3


def publicacion_a_dict(p: Publicacion) -> dict:
    return {"id": p.id, "texto": p.texto, "fecha": iso(p.creada), "es_logro": p.es_logro}


def texto_logro(racha: int, xp: int) -> str:
    dias = "día" if racha == 1 else "días"
    return f"¡Logré una racha de {racha} {dias} y {xp} XP! 🌱"


@router.get("/frases")
def frases(sesion: Session = Depends(obtener_sesion)):
    return [{"id": f.id, "texto": f.texto} for f in sesion.scalars(select(FraseMuro).order_by(FraseMuro.orden))]


@router.get("/publicaciones")
def publicaciones(usuario: Usuario = Depends(usuario_actual), sesion: Session = Depends(obtener_sesion)):
    visibles = sesion.scalars(
        select(Publicacion).where(Publicacion.visible.is_(True)).order_by(Publicacion.creada.desc()).limit(50)
    )
    return [publicacion_a_dict(p) for p in visibles]


@router.post("/publicaciones", status_code=201)
def publicar(
    entrada: PublicacionEntrada,
    usuario: Usuario = Depends(usuario_actual),
    sesion: Session = Depends(obtener_sesion),
):
    if (entrada.frase_id is None) == (entrada.logro is None):
        raise HTTPException(422, "Envía una frase predefinida (frase_id) o un logro, no ambos")
    if entrada.frase_id is not None:
        frase = sesion.get(FraseMuro, entrada.frase_id)
        if frase is None:
            raise HTTPException(422, "Solo se pueden publicar frases predefinidas")
        publicacion = Publicacion(usuario_id=usuario.id, texto=frase.texto, es_logro=False)
    else:
        texto = texto_logro(entrada.logro.racha, entrada.logro.xp)
        publicacion = Publicacion(usuario_id=usuario.id, texto=texto, es_logro=True)
    sesion.add(publicacion)
    sesion.commit()
    return publicacion_a_dict(publicacion)


@router.post("/publicaciones/{publicacion_id}/reportes", status_code=201)
def reportar(
    publicacion_id: str,
    entrada: ReporteEntrada,
    usuario: Usuario = Depends(usuario_actual),
    sesion: Session = Depends(obtener_sesion),
):
    publicacion = sesion.get(Publicacion, publicacion_id)
    if publicacion is None:
        raise HTTPException(404, "La publicación no existe")
    ya = sesion.scalar(
        select(Reporte).where(Reporte.publicacion_id == publicacion.id, Reporte.usuario_id == usuario.id)
    )
    if ya:
        raise HTTPException(409, "Ya reportaste esta publicación")

    reporte = Reporte(publicacion_id=publicacion.id, usuario_id=usuario.id, motivo=entrada.motivo.strip())
    sesion.add(reporte)
    sesion.flush()
    pendientes = sesion.scalar(
        select(func.count()).select_from(Reporte).where(
            Reporte.publicacion_id == publicacion.id, Reporte.pendiente.is_(True)
        )
    )
    if pendientes >= REPORTES_PARA_OCULTAR:
        publicacion.visible = False
    sesion.commit()
    return {"id": reporte.id, "publicacion_oculta": not publicacion.visible}
