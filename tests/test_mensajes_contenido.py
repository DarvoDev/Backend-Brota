import pytest

from app.clasificador import DICCIONARIO, clasificar, normalizar


@pytest.mark.parametrize("ejemplo", DICCIONARIO["ejemplos"], ids=lambda e: e["texto"])
def test_ejemplos_del_diccionario(ejemplo):
    resultado = clasificar(ejemplo["texto"])
    assert resultado["categoria"] == ejemplo["esperado"]
    assert resultado["estilo"] == ejemplo["estilo"]


def test_normalizar():
    assert normalizar("¡Ánimo, PEQUEÑO paso!🌱") == ["animo", "pequeno", "paso"]


def test_cada_palabra_se_usa_una_vez():
    # "no tienes que" (+2) no debe contar también "tienes que" (-2)
    terminos = [c["termino"] for c in clasificar("No tienes que correr")["coincidencias"]]
    assert terminos == ["no tienes que"]


def test_endpoint_clasificar_y_diccionario(cliente):
    r = cliente.post("/api/v1/mensajes/clasificar", json={"texto": "Tú puedes, no te rindas"})
    assert r.status_code == 200
    cuerpo = r.json()
    assert cuerpo["categoria"] == "motivadora" and cuerpo["estilo"] == "explicito" and cuerpo["puntaje"] == 2
    assert {"termino": "tu puedes", "categoria": "exhortacion_explicita", "peso": 1} in cuerpo["coincidencias"]

    r = cliente.get("/api/v1/mensajes/diccionario")
    assert r.status_code == 200 and r.json()["version"] == 1


def test_contenido_publico_sembrado(cliente):
    catalogo = cliente.get("/api/v1/contenido/catalogo").json()
    assert len(catalogo) == 12
    assert catalogo[0] == {"id": "m-agua", "titulo": "Tomar un vaso de agua", "esfuerzo": 1, "duracion_min": 1}
    assert len(cliente.get("/api/v1/contenido/mensajes").json()) == 6
    directorio = cliente.get("/api/v1/contenido/directorio").json()
    assert directorio[0]["telefono"] == "911" and directorio[0]["es_emergencia"] is True


def test_admin_mensaje_debe_ser_motivador(cliente, admin):
    r = cliente.post(
        "/api/v1/admin/mensajes",
        json={"texto": "Deberías esforzarte más, no hay excusas", "categoria": "Aliento"},
        headers=admin,
    )
    assert r.status_code == 422
    assert isinstance(r.json()["detail"], str)
    assert r.json()["clasificacion"]["categoria"] == "no_apta"

    r = cliente.post(
        "/api/v1/admin/mensajes",
        json={"id": "msg-7", "texto": "Respirar con calma también cuenta", "categoria": "Descanso"},
        headers=admin,
    )
    assert r.status_code == 201 and r.json()["id"] == "msg-7"
    assert r.json()["validado_por"] == "Administración Brota"
    assert any(m["id"] == "msg-7" for m in cliente.get("/api/v1/contenido/mensajes").json())

    # Editar también reclasifica
    r = cliente.put(
        "/api/v1/admin/mensajes/msg-7", json={"texto": "Hoy comí a las tres", "categoria": "x"}, headers=admin
    )
    assert r.status_code == 422 and r.json()["clasificacion"]["categoria"] == "neutra"


def test_admin_crud_catalogo_y_directorio(cliente, admin):
    nuevo = {"titulo": "Saltar 20 veces", "esfuerzo": 2, "duracion_min": 2}
    r = cliente.post("/api/v1/admin/catalogo", json=nuevo, headers=admin)
    assert r.status_code == 201
    actividad_id = r.json()["id"]
    assert cliente.get("/api/v1/contenido/catalogo").json()[-1]["id"] == actividad_id

    r = cliente.put(f"/api/v1/admin/catalogo/{actividad_id}", json={**nuevo, "esfuerzo": 3}, headers=admin)
    assert r.status_code == 200 and r.json()["esfuerzo"] == 3
    assert cliente.post("/api/v1/admin/catalogo", json={**nuevo, "esfuerzo": 7}, headers=admin).status_code == 422
    assert cliente.post("/api/v1/admin/catalogo", json={**nuevo, "id": "m-agua"}, headers=admin).status_code == 409

    assert cliente.delete(f"/api/v1/admin/catalogo/{actividad_id}", headers=admin).status_code == 204
    assert cliente.delete(f"/api/v1/admin/catalogo/{actividad_id}", headers=admin).status_code == 404

    recurso = {"nombre": "Línea local", "telefono": "5555555555", "categoria": "Apoyo psicológico"}
    r = cliente.post("/api/v1/admin/directorio", json=recurso, headers=admin)
    assert r.status_code == 201 and r.json()["es_emergencia"] is False


def test_roles_solo_admin(cliente, usuario):
    assert cliente.get("/api/v1/admin/reportes", headers=usuario).status_code == 403
    r = cliente.post("/api/v1/admin/catalogo", json={"titulo": "x", "esfuerzo": 1, "duracion_min": 1}, headers=usuario)
    assert r.status_code == 403
    assert cliente.delete("/api/v1/admin/mensajes/msg-1", headers=usuario).status_code == 403
    assert cliente.get("/api/v1/admin/reportes").status_code == 401
