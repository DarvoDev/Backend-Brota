"""Contraseñas (bcrypt), tokens (JWT HS256) y cifrado de datos (Fernet)."""

import base64
import hashlib
import json
from datetime import timedelta

import bcrypt
import jwt
from cryptography.fernet import Fernet, InvalidToken
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.config import ahora, config
from app.db import obtener_sesion
from app.modelos import Usuario

# ---------- Contraseñas ----------


def _bytes_password(password: str) -> bytes:
    # bcrypt solo usa los primeros 72 bytes; recortamos de forma explícita.
    return password.encode("utf-8")[:72]


def cifrar_password(password: str) -> str:
    return bcrypt.hashpw(_bytes_password(password), bcrypt.gensalt()).decode("ascii")


def verificar_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(_bytes_password(password), password_hash.encode("ascii"))
    except ValueError:
        return False


# ---------- JWT ----------


def crear_token(usuario: Usuario) -> str:
    momento = ahora()
    datos = {
        "sub": usuario.id,
        "rol": usuario.rol,
        "iat": momento,
        "exp": momento + timedelta(days=config.jwt_dias),
    }
    return jwt.encode(datos, config.jwt_secreto, algorithm="HS256")


def leer_token(token: str) -> dict:
    return jwt.decode(token, config.jwt_secreto, algorithms=["HS256"])


# ---------- Cifrado de datos sensibles (RNF-02) ----------


def _clave_fernet(clave: str) -> bytes:
    """Acepta una clave Fernet válida o, si no lo es, deriva una con SHA-256."""
    try:
        Fernet(clave.encode())
        return clave.encode()
    except (ValueError, TypeError):
        return base64.urlsafe_b64encode(hashlib.sha256(clave.encode()).digest())


_fernet = Fernet(_clave_fernet(config.clave_datos))


def cifrar_datos(datos: dict) -> str:
    texto = json.dumps(datos, ensure_ascii=False, separators=(",", ":"))
    return _fernet.encrypt(texto.encode("utf-8")).decode("ascii")


def descifrar_datos(cifrado: str) -> dict:
    try:
        return json.loads(_fernet.decrypt(cifrado.encode("ascii")))
    except InvalidToken as error:
        raise ValueError("No se pudieron descifrar los datos (¿cambió BROTA_CLAVE_DATOS?)") from error


# ---------- Dependencias de FastAPI ----------

_bearer = HTTPBearer(auto_error=False)


def usuario_actual(
    credenciales: HTTPAuthorizationCredentials | None = Depends(_bearer),
    sesion: Session = Depends(obtener_sesion),
) -> Usuario:
    if credenciales is None:
        raise HTTPException(401, "Falta el token de acceso", headers={"WWW-Authenticate": "Bearer"})
    try:
        datos = leer_token(credenciales.credentials)
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "La sesión expiró, vuelve a iniciar sesión") from None
    except jwt.InvalidTokenError:
        raise HTTPException(401, "Token inválido") from None
    usuario = sesion.get(Usuario, datos.get("sub"))
    if usuario is None:
        raise HTTPException(401, "El usuario del token ya no existe")
    return usuario


def solo_admin(usuario: Usuario = Depends(usuario_actual)) -> Usuario:
    # El rol se toma de la base de datos, no solo del token.
    if usuario.rol != "administrador":
        raise HTTPException(403, "Esta acción es solo para administradores")
    return usuario
