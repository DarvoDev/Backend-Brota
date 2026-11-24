from datetime import date

import pytest

from app import perceptron

X = [0, 0.5, 0, 1, 0, 0.5, 0.5, 0]


def test_prediccion_con_pesos_iniciales():
    # z = 0.4·0.5 + 0.3·1 − 0.8·0.5 − 0.6·0.5 + 1.4 = 1.2
    resultado = perceptron.predecir(X, perceptron.PESOS_INICIALES, perceptron.SESGO_INICIAL)
    assert resultado == {"riesgo": "ALTO", "puntaje": 1.2}


def test_un_paso_de_aprendizaje():
    # Predijo ALTO (ŷ=1) pero sí cumplió (y=0): w ← w − 0.1·x ; b ← b − 0.1
    pesos, sesgo = perceptron.paso_aprendizaje(X, 0, perceptron.PESOS_INICIALES, perceptron.SESGO_INICIAL)
    assert pesos == pytest.approx([-1.2, 0.35, 0.6, 0.2, -0.4, -0.85, -0.65, -1.0])
    assert sesgo == pytest.approx(1.3)
    # Si acierta, no cambia nada
    assert perceptron.paso_aprendizaje(X, 1, perceptron.PESOS_INICIALES, 1.4) == (perceptron.PESOS_INICIALES, 1.4)


def historial_de_prueba():
    return perceptron.Historial(
        cumplimientos=[(date(2026, 11, 16), 10), (date(2026, 11, 18), 20)],
        escudos=[date(2026, 11, 17)],
        animos=[(date(2026, 11, 15), 5, 3), (date(2026, 11, 18), 3, 2)],
    )


def test_calcular_entradas():
    x = perceptron.calcular_entradas(date(2026, 11, 18), historial_de_prueba())  # miércoles
    assert x == pytest.approx([2 / 7, 15 / 23, 1, 0, 0, 0.5, 0.5, 1])
    # Sin datos: valores neutros (el 21 es sábado → x4 = 1)
    assert perceptron.calcular_entradas(date(2026, 11, 20), perceptron.Historial()) == [0, 0.5, 0, 1, 0, 0.5, 0.5, 0]


def test_entrenar_repite_dia_por_dia():
    h = historial_de_prueba()
    resultado = perceptron.entrenar(h)
    # Días d = 15, 16, 17 (el 18 es el último y su d+1 aún no se conoce)
    assert resultado["dias_entrenados"] == 3
    pesos, sesgo = list(perceptron.PESOS_INICIALES), perceptron.SESGO_INICIAL
    for dia in (15, 16, 17):
        y = 0 if dia + 1 in (16, 18) else 1
        x = perceptron.calcular_entradas(date(2026, 11, dia), h)
        pesos, sesgo = perceptron.paso_aprendizaje(x, y, pesos, sesgo)
    assert resultado["pesos"] == pytest.approx(pesos) and resultado["sesgo"] == pytest.approx(sesgo)
    assert resultado["pesos"] != perceptron.PESOS_INICIALES  # sí aprendió algo


def test_endpoints_de_riesgo(cliente, usuario):
    r = cliente.post("/api/v1/riesgo/prediccion", json={"x": X}, headers=usuario)
    assert r.status_code == 200
    cuerpo = r.json()
    assert cuerpo["riesgo"] == "ALTO" and cuerpo["puntaje"] == 1.2
    assert cuerpo["pesos"] == perceptron.PESOS_INICIALES and cuerpo["sesgo"] == 1.4 and cuerpo["entradas"] == X

    assert cliente.post("/api/v1/riesgo/prediccion", json={"x": [1, 2]}, headers=usuario).status_code == 422
    assert cliente.post("/api/v1/riesgo/prediccion", json={}, headers=usuario).status_code == 200
    assert cliente.post("/api/v1/riesgo/prediccion", headers=usuario).status_code == 200

    def cumplimiento(id, dia, hora):
        datos = {"dia": dia, "actividad_id": "m-agua", "titulo": "Agua", "xp": 10, "hora": hora}
        return {"id": id, "tipo": "cumplimiento", "fecha": f"{dia}T12:00:00Z", "datos": datos}

    def animo(id, dia, a, e):
        return {"id": id, "tipo": "animo", "fecha": f"{dia}T08:00:00Z", "datos": {"dia": dia, "animo": a, "energia": e}}

    eventos = [
        cumplimiento("c1", "2026-11-16", 10),
        {"id": "e1", "tipo": "escudo", "fecha": "2026-11-17T10:00:00Z", "datos": {"dia": "2026-11-17"}},
        animo("a0", "2026-11-15", 5, 3),
        animo("a1", "2026-11-18", 3, 2),
        cumplimiento("c2", "2026-11-18", 20),
    ]
    assert len(cliente.post("/api/v1/sync", json={"eventos": eventos}, headers=usuario).json()["aceptados"]) == 5

    # Entradas calculadas desde lo sincronizado
    r = cliente.post("/api/v1/riesgo/prediccion", json={"dia": "2026-11-18"}, headers=usuario)
    assert r.json()["entradas"] == pytest.approx([2 / 7, 15 / 23, 1, 0, 0, 0.5, 0.5, 1])

    # Entrenar guarda los pesos del usuario y la predicción los usa
    r = cliente.post("/api/v1/riesgo/entrenar", headers=usuario)
    assert r.status_code == 200
    esperado = perceptron.entrenar(historial_de_prueba())
    assert r.json()["pesos"] == pytest.approx(esperado["pesos"]) and r.json()["dias_entrenados"] == 3
    r = cliente.post("/api/v1/riesgo/prediccion", json={"x": X}, headers=usuario)
    assert r.json()["pesos"] == pytest.approx(esperado["pesos"])
