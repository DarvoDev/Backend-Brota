"""Clasificador de mensajes por diccionario de palabras clave."""

from fastapi import APIRouter

from app.clasificador import DICCIONARIO, clasificar
from app.esquemas import TextoEntrada

router = APIRouter(prefix="/mensajes", tags=["mensajes"])


@router.post("/clasificar")
def clasificar_texto(entrada: TextoEntrada):
    return clasificar(entrada.texto)


@router.get("/diccionario")
def diccionario():
    return DICCIONARIO
