"""Compañero fantasma anónimo: señales de "completé mi misión" y reacciones.

Nunca se devuelve información personal de otros usuarios: solo ids opacos.
"""

from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import ahora, hoy, iso
from app.db import obtener_sesion
from app.esquemas import ReaccionEntrada
from app.modelos import ReaccionFantasma, SenalFantasma, Usuario
from app.seguridad import usuario_actual

router = APIRouter(prefix="/fantasma", tags=["fantasma"])


@router.post("/senales", status_code=201)
def crear_senal(
    response: Response,
    usuario: Usuario = Depends(usuario_actual),
    sesion: Session = Depends(obtener_sesion),
):
    dia = hoy()
    existente = sesion.scalar(
        select(SenalFantasma).where(SenalFantasma.usuario_id == usuario.id, SenalFantasma.dia == dia)
    )
    if existente:
        response.status_code = 200
        return {"id": existente.id}
    senal = SenalFantasma(usuario_id=usuario.id, dia=dia)
    sesion.add(senal)
    sesion.commit()
    return {"id": senal.id}


@router.get("/senales")
def listar_senales(usuario: Usuario = Depends(usuario_actual), sesion: Session = Depends(obtener_sesion)):
    momento = ahora()
    ya_reaccione = select(ReaccionFantasma.senal_id).where(ReaccionFantasma.usuario_id == usuario.id)
    senales = sesion.scalars(
        select(SenalFantasma)
        .where(
            SenalFantasma.usuario_id != usuario.id,
            SenalFantasma.creada >= momento - timedelta(hours=24),
            SenalFantasma.id.not_in(ya_reaccione),
        )
        .order_by(SenalFantasma.creada.desc())
        .limit(10)
    ).all()
    return [
        {"id": s.id, "hace_minutos": max(0, int((momento - s.creada).total_seconds() // 60))} for s in senales
    ]


@router.post("/reacciones", status_code=201)
def reaccionar(
    entrada: ReaccionEntrada,
    usuario: Usuario = Depends(usuario_actual),
    sesion: Session = Depends(obtener_sesion),
):
    senal = sesion.get(SenalFantasma, entrada.senal_id)
    if senal is None:
        raise HTTPException(404, "La señal no existe")
    if senal.usuario_id == usuario.id:
        raise HTTPException(400, "No puedes reaccionar a tu propia señal")
    repetida = sesion.scalar(
        select(ReaccionFantasma).where(
            ReaccionFantasma.senal_id == senal.id, ReaccionFantasma.usuario_id == usuario.id
        )
    )
    if repetida:
        raise HTTPException(409, "Ya reaccionaste a esta señal")
    reaccion = ReaccionFantasma(senal_id=senal.id, usuario_id=usuario.id, reaccion=entrada.reaccion)
    sesion.add(reaccion)
    sesion.commit()
    return {"id": reaccion.id}


@router.get("/recibidas")
def recibidas(usuario: Usuario = Depends(usuario_actual), sesion: Session = Depends(obtener_sesion)):
    pendientes = sesion.scalars(
        select(ReaccionFantasma)
        .join(SenalFantasma, ReaccionFantasma.senal_id == SenalFantasma.id)
        .where(SenalFantasma.usuario_id == usuario.id, ReaccionFantasma.entregada.is_(False))
        .order_by(ReaccionFantasma.creada)
    ).all()
    respuesta = [{"id": r.id, "reaccion": r.reaccion, "fecha": iso(r.creada)} for r in pendientes]
    for r in pendientes:
        r.entregada = True
    sesion.commit()
    return respuesta
