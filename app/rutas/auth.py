"""Cuentas: registro, inicio de sesión y perfil (CU-01, CU-02)."""

import re

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import hoy
from app.db import obtener_sesion
from app.esquemas import LoginEntrada, RegistroEntrada
from app.modelos import Usuario
from app.seguridad import cifrar_password, crear_token, usuario_actual, verificar_password

router = APIRouter(prefix="/auth", tags=["cuentas"])

PATRON_CORREO = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def calcular_edad(fecha_nac, referencia) -> int:
    return referencia.year - fecha_nac.year - ((referencia.month, referencia.day) < (fecha_nac.month, fecha_nac.day))


def respuesta_sesion(usuario: Usuario) -> dict:
    return {
        "token": crear_token(usuario),
        "usuario": {"id": usuario.id, "nombre": usuario.nombre, "rol": usuario.rol},
    }


@router.post("/registro", status_code=201)
def registro(datos: RegistroEntrada, sesion: Session = Depends(obtener_sesion)):
    correo = datos.correo.strip().lower()
    nombre = datos.nombre.strip()
    if not PATRON_CORREO.match(correo) or len(correo) > 254:
        raise HTTPException(422, "El correo no es válido")
    if len(datos.password) < 6:
        raise HTTPException(422, "La contraseña debe tener al menos 6 caracteres")
    if not nombre or len(nombre) > 80:
        raise HTTPException(422, "Escribe un nombre (máximo 80 caracteres)")
    if not datos.acepta_privacidad:
        raise HTTPException(422, "Debes aceptar el aviso de privacidad")
    if datos.fecha_nac > hoy():
        raise HTTPException(422, "La fecha de nacimiento no puede ser futura")

    edad = calcular_edad(datos.fecha_nac, hoy())
    if edad < 13:
        raise HTTPException(422, "Brota es para personas de 13 años o más")
    if edad < 18 and not datos.consentimiento_tutor:
        raise HTTPException(422, "Si tienes entre 13 y 17 años necesitas el consentimiento de tu madre, padre o tutor")

    if sesion.scalar(select(Usuario).where(Usuario.correo == correo)):
        raise HTTPException(409, "Ya existe una cuenta con ese correo")

    usuario = Usuario(
        correo=correo,
        password_hash=cifrar_password(datos.password),
        nombre=nombre,
        fecha_nac=datos.fecha_nac,
        consentimiento_tutor=datos.consentimiento_tutor,
    )
    sesion.add(usuario)
    sesion.commit()
    return {**respuesta_sesion(usuario), "aviso_edad": edad > 35}


@router.post("/login")
def login(datos: LoginEntrada, sesion: Session = Depends(obtener_sesion)):
    usuario = sesion.scalar(select(Usuario).where(Usuario.correo == datos.correo.strip().lower()))
    if usuario is None or not verificar_password(datos.password, usuario.password_hash):
        raise HTTPException(401, "Correo o contraseña incorrectos")
    return respuesta_sesion(usuario)


@router.get("/yo")
def yo(usuario: Usuario = Depends(usuario_actual)):
    return {
        "id": usuario.id,
        "correo": usuario.correo,
        "nombre": usuario.nombre,
        "rol": usuario.rol,
        "fecha_nac": usuario.fecha_nac.isoformat(),
    }
