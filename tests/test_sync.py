import uuid

from tests.conftest import cabecera, registrar

URL = "/api/v1/sync"


def evento(tipo, datos, id=None):
    return {"id": id or str(uuid.uuid4()), "tipo": tipo, "fecha": "2026-11-20T10:30:00Z", "datos": datos}


def test_sync_idempotente(cliente, usuario):
    lote = {
        "eventos": [
            evento("animo", {"dia": "2026-11-20", "animo": 2, "energia": 1}),
            evento("cumplimiento", {"dia": "2026-11-20", "actividad_id": "m-agua", "titulo": "Agua", "xp": 10, "hora": 9}),
            evento("escudo", {"dia": "2026-11-20"}),
        ]
    }
    ids = [e["id"] for e in lote["eventos"]]

    r = cliente.post(URL, json=lote, headers=usuario)
    assert r.status_code == 200
    assert r.json() == {"aceptados": ids, "duplicados": [], "rechazados": []}

    # Reenviar el mismo lote no duplica
    r = cliente.post(URL, json=lote, headers=usuario)
    assert r.json() == {"aceptados": [], "duplicados": ids, "rechazados": []}

    r = cliente.get(URL + "/resumen", headers=usuario)
    assert r.status_code == 200
    resumen = r.json()
    assert resumen["total"] == 3
    assert resumen["por_tipo"]["animo"] == 1 and resumen["por_tipo"]["tarea"] == 0
    assert resumen["ultimo"] is not None


def test_rechaza_solo_eventos_invalidos(cliente, usuario):
    bueno = evento("descanso", {"dia": "2026-11-21"})
    desconocido = evento("baile", {"dia": "2026-11-21"})
    animo_fuera = evento("animo", {"dia": "2026-11-21", "animo": 9, "energia": 1})
    r = cliente.post(URL, json={"eventos": [bueno, desconocido, animo_fuera]}, headers=usuario)
    assert r.status_code == 200
    assert r.json()["aceptados"] == [bueno["id"]]
    assert r.json()["rechazados"] == [desconocido["id"], animo_fuera["id"]]


def test_mismo_id_en_el_mismo_lote(cliente, usuario):
    e = evento("descanso", {"dia": "2026-11-21"})
    r = cliente.post(URL, json={"eventos": [e, e]}, headers=usuario)
    assert r.json()["aceptados"] == [e["id"]] and r.json()["duplicados"] == [e["id"]]


def test_unicidad_es_por_usuario(cliente, usuario):
    e = evento("descanso", {"dia": "2026-11-21"})
    otro = cabecera(registrar(cliente)["token"])
    assert cliente.post(URL, json={"eventos": [e]}, headers=usuario).json()["aceptados"] == [e["id"]]
    assert cliente.post(URL, json={"eventos": [e]}, headers=otro).json()["aceptados"] == [e["id"]]


def test_datos_cifrados_en_reposo(cliente, usuario, motor):
    e = evento("animo", {"dia": "2026-11-20", "animo": 1, "energia": 1, "nota": "me siento muy triste"})
    cliente.post(URL, json={"eventos": [e]}, headers=usuario)
    with motor.connect() as c:
        crudo = c.exec_driver_sql("SELECT datos_cifrados FROM eventos_sync").scalar()
    assert "triste" not in crudo and "animo" not in crudo and "2026-11-20" not in crudo

    from app.seguridad import descifrar_datos

    assert descifrar_datos(crudo)["nota"] == "me siento muy triste"


def test_sync_requiere_token(cliente):
    assert cliente.post(URL, json={"eventos": []}).status_code == 401
