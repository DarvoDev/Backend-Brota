"""Clasificador de mensajes por diccionario de palabras clave.

Mismo algoritmo que la app (ver docs/CONTRATO_API.md, sección 6):
1. Normalizar el texto: minúsculas, sin acentos (NFD), todo lo que no sea
   a-z/0-9 se vuelve espacio y se separa en palabras.
2. Recorrer los términos de más a menos palabras (empates: orden del archivo).
3. Para cada término buscar la primera posición donde todas sus palabras
   coinciden (palabra con '*' = prefijo) sin usar palabras ya usadas.
4. Aplicar las reglas del diccionario.
"""

import json
import re
import unicodedata
from pathlib import Path

RUTA_DICCIONARIO = Path(__file__).parent / "datos" / "diccionario_motivacional.json"

with RUTA_DICCIONARIO.open(encoding="utf-8") as archivo:
    DICCIONARIO: dict = json.load(archivo)


def normalizar(texto: str) -> list[str]:
    sin_acentos = "".join(
        c for c in unicodedata.normalize("NFD", texto.lower()) if unicodedata.category(c) != "Mn"
    )
    return re.sub(r"[^a-z0-9]+", " ", sin_acentos).split()


def _preparar_terminos(diccionario: dict) -> list[dict]:
    terminos = []
    for categoria, info in diccionario["categorias"].items():
        for termino in info["terminos"]:
            palabras = []
            for palabra in termino.split():
                es_prefijo = palabra.endswith("*")
                base = normalizar(palabra.rstrip("*"))
                palabras.append((" ".join(base), es_prefijo))
            terminos.append(
                {"termino": termino, "categoria": categoria, "peso": info["peso"], "palabras": palabras}
            )
    # sorted() es estable: los empates conservan el orden del archivo.
    return sorted(terminos, key=lambda t: -len(t["palabras"]))


TERMINOS = _preparar_terminos(DICCIONARIO)


def _coincide(palabra_texto: str, palabra_termino: str, es_prefijo: bool) -> bool:
    return palabra_texto.startswith(palabra_termino) if es_prefijo else palabra_texto == palabra_termino


def clasificar(texto: str) -> dict:
    palabras = normalizar(texto)
    usadas = [False] * len(palabras)
    coincidencias = []

    for termino in TERMINOS:
        largo = len(termino["palabras"])
        for inicio in range(len(palabras) - largo + 1):
            if all(
                not usadas[inicio + j] and _coincide(palabras[inicio + j], base, prefijo)
                for j, (base, prefijo) in enumerate(termino["palabras"])
            ):
                for j in range(largo):
                    usadas[inicio + j] = True
                coincidencias.append(
                    {"termino": termino["termino"], "categoria": termino["categoria"], "peso": termino["peso"]}
                )
                break  # cada término cuenta máximo una vez

    categorias = {c["categoria"] for c in coincidencias}
    puntaje = sum(c["peso"] for c in coincidencias)
    umbrales = DICCIONARIO["umbrales"]

    if "riesgo" in categorias:
        categoria = "riesgo"
    elif "ofensiva" in categorias:
        categoria = "no_apta"
    elif puntaje >= umbrales["motivadora_minimo"]:
        categoria = "motivadora"
    elif puntaje <= umbrales["no_apta_maximo"]:
        categoria = "no_apta"
    else:
        categoria = "neutra"

    estilo = "explicito" if "exhortacion_explicita" in categorias else "implicito"
    return {"categoria": categoria, "estilo": estilo, "puntaje": puntaje, "coincidencias": coincidencias}
