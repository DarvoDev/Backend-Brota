"""Perceptrón de riesgo de procrastinación por usuario."""

import json
from datetime import date

from fastapi import APIRouter, Body, Depends, HTTPException
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app import perceptron
from app.config import ahora, dia_local, hoy
from app.db import obtener_sesion
from app.esquemas import PrediccionEntrada
from app.modelos import EventoSync, PesosRiesgo, ReaccionFantasma, SenalFantasma, Usuario
from app.seguridad import descifrar_datos, usuario_actual

router = APIRouter(prefix="/riesgo", tags=["riesgo"])


def cargar_historial(sesion: Session, usuario: Usuario) -> perceptron.Historial:
    """Arma el historial del usuario a partir de sus eventos sincronizados (descifrados)."""
    historial = perceptron.Historial()
    eventos = sesion.scalars(
        select(EventoSync)
        .where(EventoSync.usuario_id == usuario.id, EventoSync.tipo.in_(["cumplimiento", "escudo", "animo"]))
        .order_by(EventoSync.fecha, EventoSync.pk)
    )
    for evento in eventos:
        datos = descifrar_datos(evento.datos_cifrados)
        dia = date.fromisoformat(str(datos["dia"]))
        if evento.tipo == "cumplimiento":
            historial.cumplimientos.append((dia, int(datos["hora"])))
        elif evento.tipo == "escudo":
            historial.escudos.append(dia)
        else:
            historial.animos.append((dia, int(datos["animo"]), int(datos["energia"])))

    # Reacciones enviadas por el usuario + recibidas en sus señales.
    reacciones = sesion.scalars(
        select(ReaccionFantasma.creada)
        .join(SenalFantasma, ReaccionFantasma.senal_id == SenalFantasma.id)
        .where(or_(ReaccionFantasma.usuario_id == usuario.id, SenalFantasma.usuario_id == usuario.id))
    )
    historial.reacciones = [dia_local(creada) for creada in reacciones]
    return historial


def pesos_de(sesion: Session, usuario: Usuario) -> tuple[list[float], float]:
    guardados = sesion.get(PesosRiesgo, usuario.id)
    if guardados is None:
        return list(perceptron.PESOS_INICIALES), perceptron.SESGO_INICIAL
    return json.loads(guardados.pesos), guardados.sesgo


@router.post("/prediccion")
def prediccion(
    entrada: PrediccionEntrada | None = Body(default=None),
    usuario: Usuario = Depends(usuario_actual),
    sesion: Session = Depends(obtener_sesion),
):
    entrada = entrada or PrediccionEntrada()
    if entrada.x is not None:
        if len(entrada.x) != 8 or any(not 0 <= v <= 1 for v in entrada.x):
            raise HTTPException(422, "x debe tener 8 números entre 0 y 1")
        x = list(entrada.x)
    else:
        x = perceptron.calcular_entradas(entrada.dia or hoy(), cargar_historial(sesion, usuario))

    pesos, sesgo = pesos_de(sesion, usuario)
    resultado = perceptron.predecir(x, pesos, sesgo)
    return {**resultado, "entradas": x, "pesos": pesos, "sesgo": sesgo}


@router.post("/entrenar")
def entrenar(usuario: Usuario = Depends(usuario_actual), sesion: Session = Depends(obtener_sesion)):
    # Se reentrena desde los pesos iniciales para que el resultado no dependa
    # de cuántas veces se llame a este endpoint.
    resultado = perceptron.entrenar(cargar_historial(sesion, usuario))
    guardados = sesion.get(PesosRiesgo, usuario.id)
    if guardados is None:
        guardados = PesosRiesgo(usuario_id=usuario.id)
        sesion.add(guardados)
    guardados.pesos = json.dumps(resultado["pesos"])
    guardados.sesgo = resultado["sesgo"]
    guardados.actualizado = ahora()
    sesion.commit()
    return resultado
