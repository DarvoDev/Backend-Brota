"""Perceptrón de riesgo de procrastinación (idéntico en app y backend).

Python puro, sin numpy. Ver docs/CONTRATO_API.md, sección 8.
El modelo no diagnostica nada: solo sirve para adaptar la dificultad del día siguiente.
"""

from dataclasses import dataclass, field
from datetime import date, timedelta

PESOS_INICIALES = [-1.2, 0.4, 0.6, 0.3, -0.4, -0.8, -0.6, -1.0]
SESGO_INICIAL = 1.4
ETA = 0.1
NOMBRES_ENTRADAS = [
    "constancia7", "hora_media", "escudos_semana", "fin_de_semana",
    "fantasma7", "animo", "energia", "activo_hoy",
]


@dataclass
class Historial:
    """Datos del usuario necesarios para calcular las entradas."""

    cumplimientos: list[tuple[date, int]] = field(default_factory=list)  # (día, hora 0-23)
    escudos: list[date] = field(default_factory=list)
    animos: list[tuple[date, int, int]] = field(default_factory=list)  # (día, ánimo 1-5, energía 1-3), en orden
    reacciones: list[date] = field(default_factory=list)  # días de reacciones enviadas + recibidas


def calcular_z(x: list[float], pesos: list[float], sesgo: float) -> float:
    return sum(w * xi for w, xi in zip(pesos, x)) + sesgo


def predecir(x: list[float], pesos: list[float], sesgo: float) -> dict:
    z = calcular_z(x, pesos, sesgo)
    return {"riesgo": "ALTO" if z > 0 else "BAJO", "puntaje": round(z, 2)}


def paso_aprendizaje(x: list[float], y: int, pesos: list[float], sesgo: float) -> tuple[list[float], float]:
    """Regla del perceptrón: wᵢ ← wᵢ + η(y−ŷ)xᵢ ; b ← b + η(y−ŷ)."""
    y_gorro = 1 if calcular_z(x, pesos, sesgo) > 0 else 0
    error = y - y_gorro
    if error == 0:
        return list(pesos), sesgo
    nuevos = [w + ETA * error * xi for w, xi in zip(pesos, x)]
    return nuevos, sesgo + ETA * error


def calcular_entradas(d: date, h: Historial) -> list[float]:
    """Entradas x1..x8 al cierre del día d (para predecir d+1)."""
    inicio7 = d - timedelta(days=6)
    en7 = [(dia, hora) for dia, hora in h.cumplimientos if inicio7 <= dia <= d]

    x1 = len({dia for dia, _ in en7}) / 7
    x2 = (sum(hora for _, hora in en7) / len(en7)) / 23 if en7 else 0.5

    lunes = d - timedelta(days=d.weekday())
    escudos = sum(1 for dia in h.escudos if lunes <= dia <= d)
    x3 = min(1.0, escudos / 1)

    x4 = 1.0 if (d + timedelta(days=1)).weekday() >= 5 else 0.0

    reacciones = sum(1 for dia in h.reacciones if inicio7 <= dia <= d)
    x5 = min(1.0, reacciones / 7)

    # sorted() es estable: dentro del mismo día queda al final el último registrado.
    previos = sorted((a for a in h.animos if a[0] <= d), key=lambda a: a[0])
    if previos:
        ultimo = previos[-1]
        x6 = (ultimo[1] - 1) / 4
        x7 = (ultimo[2] - 1) / 2
    else:
        x6 = x7 = 0.5

    x8 = 1.0 if any(dia == d for dia, _ in h.cumplimientos) else 0.0
    return [x1, x2, x3, x4, x5, x6, x7, x8]


def entrenar(h: Historial, pesos: list[float] | None = None, sesgo: float | None = None) -> dict:
    """Reproduce el historial día por día aplicando la regla de aprendizaje.

    Para cada día d (desde el primer día con datos hasta el penúltimo) se calculan
    las entradas, y con lo ocurrido en d+1 se obtiene y (1 = no hubo cumplimiento).
    """
    pesos = list(PESOS_INICIALES if pesos is None else pesos)
    sesgo = SESGO_INICIAL if sesgo is None else sesgo
    dias = [dia for dia, _ in h.cumplimientos] + h.escudos + [a[0] for a in h.animos]
    if not dias:
        return {"pesos": pesos, "sesgo": sesgo, "dias_entrenados": 0, "ajustes": 0}

    con_cumplimiento = {dia for dia, _ in h.cumplimientos}
    d, ultimo = min(dias), max(dias)
    entrenados = ajustes = 0
    while d < ultimo:
        x = calcular_entradas(d, h)
        y = 0 if (d + timedelta(days=1)) in con_cumplimiento else 1
        nuevos, nuevo_sesgo = paso_aprendizaje(x, y, pesos, sesgo)
        if nuevo_sesgo != sesgo:
            ajustes += 1
        pesos, sesgo = nuevos, nuevo_sesgo
        entrenados += 1
        d += timedelta(days=1)
    return {"pesos": pesos, "sesgo": sesgo, "dias_entrenados": entrenados, "ajustes": ajustes}
