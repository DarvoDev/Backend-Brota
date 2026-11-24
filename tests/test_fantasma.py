from tests.conftest import cabecera, registrar

URL = "/api/v1/fantasma"


def test_una_senal_por_dia(cliente, usuario):
    r1 = cliente.post(URL + "/senales", json={}, headers=usuario)
    assert r1.status_code == 201
    r2 = cliente.post(URL + "/senales", json={}, headers=usuario)
    assert r2.status_code == 200
    assert r1.json()["id"] == r2.json()["id"]


def test_flujo_de_reacciones(cliente, usuario):
    otro = cabecera(registrar(cliente)["token"])
    senal_id = cliente.post(URL + "/senales", json={}, headers=usuario).json()["id"]

    # No veo mi propia señal; el otro sí, sin datos personales
    assert cliente.get(URL + "/senales", headers=usuario).json() == []
    senales = cliente.get(URL + "/senales", headers=otro).json()
    assert len(senales) == 1
    assert set(senales[0]) == {"id", "hace_minutos"} and senales[0]["id"] == senal_id

    # No a la propia señal
    r = cliente.post(URL + "/reacciones", json={"senal_id": senal_id, "reaccion": "tu_puedes"}, headers=usuario)
    assert r.status_code == 400

    # Reacción válida y luego repetida
    r = cliente.post(URL + "/reacciones", json={"senal_id": senal_id, "reaccion": "tu_puedes"}, headers=otro)
    assert r.status_code == 201
    r = cliente.post(URL + "/reacciones", json={"senal_id": senal_id, "reaccion": "bien_hecho"}, headers=otro)
    assert r.status_code == 409

    # Ya reaccioné: deja de aparecer
    assert cliente.get(URL + "/senales", headers=otro).json() == []

    # El dueño recibe la reacción una sola vez
    recibidas = cliente.get(URL + "/recibidas", headers=usuario).json()
    assert len(recibidas) == 1 and recibidas[0]["reaccion"] == "tu_puedes" and recibidas[0]["fecha"]
    assert cliente.get(URL + "/recibidas", headers=usuario).json() == []


def test_reaccion_invalida_o_senal_inexistente(cliente, usuario):
    otro = cabecera(registrar(cliente)["token"])
    senal_id = cliente.post(URL + "/senales", json={}, headers=usuario).json()["id"]
    r = cliente.post(URL + "/reacciones", json={"senal_id": senal_id, "reaccion": "jaja"}, headers=otro)
    assert r.status_code == 422
    r = cliente.post(URL + "/reacciones", json={"senal_id": "no-existe", "reaccion": "sigue_asi"}, headers=otro)
    assert r.status_code == 404
