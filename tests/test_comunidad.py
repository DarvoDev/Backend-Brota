from tests.conftest import cabecera, registrar

URL = "/api/v1/comunidad"


def test_frases_publicas(cliente):
    r = cliente.get(URL + "/frases")
    assert r.status_code == 200
    assert r.json()[0] == {"id": "f-1", "texto": "Hoy di un paso pequeño 🌱"}
    assert len(r.json()) == 6


def test_solo_frases_predefinidas_o_logros(cliente, usuario):
    r = cliente.post(URL + "/publicaciones", json={"frase_id": "f-2"}, headers=usuario)
    assert r.status_code == 201
    assert r.json()["texto"] == "Volví después de un descanso 💛" and r.json()["es_logro"] is False

    r = cliente.post(URL + "/publicaciones", json={"logro": {"racha": 5, "xp": 120}}, headers=usuario)
    assert r.status_code == 201 and r.json()["es_logro"] is True and "5" in r.json()["texto"]

    # Texto libre, frase inexistente, vacío o ambos → rechazado
    assert cliente.post(URL + "/publicaciones", json={"texto": "hola"}, headers=usuario).status_code == 422
    assert cliente.post(URL + "/publicaciones", json={"frase_id": "f-999"}, headers=usuario).status_code == 422
    assert cliente.post(URL + "/publicaciones", json={}, headers=usuario).status_code == 422
    ambos = {"frase_id": "f-1", "logro": {"racha": 1, "xp": 1}}
    assert cliente.post(URL + "/publicaciones", json=ambos, headers=usuario).status_code == 422

    muro = cliente.get(URL + "/publicaciones", headers=usuario).json()
    assert len(muro) == 2 and muro[0]["es_logro"] is True  # más reciente primero


def test_tres_reportes_ocultan_y_admin_resuelve(cliente, usuario, admin):
    pub_id = cliente.post(URL + "/publicaciones", json={"frase_id": "f-1"}, headers=usuario).json()["id"]
    reportadores = [cabecera(registrar(cliente)["token"]) for _ in range(3)]

    for i, quien in enumerate(reportadores):
        r = cliente.post(f"{URL}/publicaciones/{pub_id}/reportes", json={"motivo": "spam"}, headers=quien)
        assert r.status_code == 201
        assert r.json()["publicacion_oculta"] is (i == 2)

    # El mismo usuario no puede reportar dos veces
    r = cliente.post(f"{URL}/publicaciones/{pub_id}/reportes", json={"motivo": "x"}, headers=reportadores[0])
    assert r.status_code == 409

    assert cliente.get(URL + "/publicaciones", headers=usuario).json() == []

    pendientes = cliente.get("/api/v1/admin/reportes", headers=admin).json()
    assert len(pendientes) == 3
    assert set(pendientes[0]) == {"id", "publicacion_id", "texto", "motivo", "fecha"}

    r = cliente.post(f"/api/v1/admin/reportes/{pendientes[0]['id']}/resolver", json={"accion": "mantener"}, headers=admin)
    assert r.status_code == 200 and r.json()["visible"] is True
    assert cliente.get("/api/v1/admin/reportes", headers=admin).json() == []
    assert len(cliente.get(URL + "/publicaciones", headers=usuario).json()) == 1

    # Resolver dos veces el mismo reporte → 409
    r = cliente.post(f"/api/v1/admin/reportes/{pendientes[0]['id']}/resolver", json={"accion": "ocultar"}, headers=admin)
    assert r.status_code == 409


def test_admin_oculta_publicacion(cliente, usuario, admin):
    pub_id = cliente.post(URL + "/publicaciones", json={"frase_id": "f-3"}, headers=usuario).json()["id"]
    cliente.post(f"{URL}/publicaciones/{pub_id}/reportes", json={"motivo": "no me gustó"}, headers=usuario)
    reporte_id = cliente.get("/api/v1/admin/reportes", headers=admin).json()[0]["id"]
    r = cliente.post(f"/api/v1/admin/reportes/{reporte_id}/resolver", json={"accion": "ocultar"}, headers=admin)
    assert r.status_code == 200 and r.json()["visible"] is False
    assert cliente.get(URL + "/publicaciones", headers=usuario).json() == []
