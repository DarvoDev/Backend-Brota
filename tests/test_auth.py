from datetime import date

from app.config import hoy
from tests.conftest import cabecera, registrar

URL = "/api/v1/auth/registro"


def fecha_con_edad(anios: int) -> str:
    h = hoy()
    try:
        return date(h.year - anios, h.month, h.day).isoformat()
    except ValueError:  # 29 de febrero
        return date(h.year - anios, h.month, 28).isoformat()


def datos(**cambios):
    base = {
        "correo": "ana@correo.mx",
        "password": "secreta1",
        "nombre": "Ana",
        "fecha_nac": fecha_con_edad(20),
        "acepta_privacidad": True,
        "consentimiento_tutor": False,
    }
    base.update(cambios)
    return base


def test_salud(cliente):
    r = cliente.get("/api/v1/salud")
    assert r.status_code == 200
    assert r.json() == {"estado": "ok", "version": "1.0.0"}


def test_registro_login_y_yo(cliente):
    r = cliente.post(URL, json=datos())
    assert r.status_code == 201
    cuerpo = r.json()
    assert cuerpo["aviso_edad"] is False
    assert cuerpo["usuario"]["nombre"] == "Ana" and cuerpo["usuario"]["rol"] == "usuario"
    assert cuerpo["token"]

    r = cliente.post("/api/v1/auth/login", json={"correo": "ANA@correo.mx", "password": "secreta1"})
    assert r.status_code == 200
    assert "aviso_edad" not in r.json()
    assert r.json()["usuario"]["id"] == cuerpo["usuario"]["id"]

    r = cliente.get("/api/v1/auth/yo", headers=cabecera(r.json()["token"]))
    assert r.status_code == 200
    assert r.json()["correo"] == "ana@correo.mx"
    assert r.json()["fecha_nac"] == datos()["fecha_nac"]


def test_login_incorrecto(cliente):
    cliente.post(URL, json=datos())
    r = cliente.post("/api/v1/auth/login", json={"correo": "ana@correo.mx", "password": "otra-cosa"})
    assert r.status_code == 401
    assert isinstance(r.json()["detail"], str)


def test_correo_duplicado(cliente):
    assert cliente.post(URL, json=datos()).status_code == 201
    assert cliente.post(URL, json=datos()).status_code == 409


def test_validaciones_basicas(cliente):
    assert cliente.post(URL, json=datos(correo="no-es-correo")).status_code == 422
    assert cliente.post(URL, json=datos(password="123")).status_code == 422
    assert cliente.post(URL, json=datos(nombre="  ")).status_code == 422
    assert cliente.post(URL, json=datos(acepta_privacidad=False)).status_code == 422


def test_reglas_de_edad(cliente):
    r = cliente.post(URL, json=datos(fecha_nac=fecha_con_edad(12)))
    assert r.status_code == 422
    assert r.json()["detail"] == "Brota es para personas de 13 años o más"

    # 13-17 sin consentimiento → 422; con consentimiento → 201
    assert cliente.post(URL, json=datos(fecha_nac=fecha_con_edad(15))).status_code == 422
    r = cliente.post(URL, json=datos(fecha_nac=fecha_con_edad(15), consentimiento_tutor=True))
    assert r.status_code == 201

    # Mayores de 35 se permiten con aviso
    r = cliente.post(URL, json=datos(correo="b@correo.mx", fecha_nac=fecha_con_edad(40)))
    assert r.status_code == 201 and r.json()["aviso_edad"] is True


def test_token_requerido_e_invalido(cliente):
    assert cliente.get("/api/v1/auth/yo").status_code == 401
    assert cliente.get("/api/v1/auth/yo", headers=cabecera("basura")).status_code == 401


def test_password_guardada_con_bcrypt(cliente, motor):
    registrar(cliente, correo="hash@correo.mx", password="mi-clave-secreta")
    with motor.connect() as c:
        guardada = c.exec_driver_sql("SELECT password_hash FROM usuarios WHERE correo='hash@correo.mx'").scalar()
    assert guardada.startswith("$2") and "mi-clave-secreta" not in guardada


def test_errores_de_validacion_en_espanol(cliente):
    r = cliente.post(URL, json={"correo": "x@y.mx"})
    assert r.status_code == 422
    assert isinstance(r.json()["detail"], str) and "obligatorio" in r.json()["detail"]
