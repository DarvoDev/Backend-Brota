"""Contenido público y su administración (CU-06, CU-11, CU-12, CU-18, CU-19)."""

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.clasificador import clasificar
from app.db import obtener_sesion
from app.esquemas import ActividadEntrada, MensajeEntrada, RecursoEntrada
from app.modelos import ActividadCatalogo, MensajeValidado, RecursoAyuda, Usuario, nuevo_id
from app.seguridad import solo_admin

publico = APIRouter(prefix="/contenido", tags=["contenido"])
admin = APIRouter(prefix="/admin", tags=["administración"], dependencies=[Depends(solo_admin)])

CAMPOS = {
    ActividadCatalogo: ["id", "titulo", "esfuerzo", "duracion_min"],
    MensajeValidado: ["id", "texto", "categoria", "validado_por"],
    RecursoAyuda: ["id", "nombre", "telefono", "descripcion", "es_emergencia", "categoria"],
}


def a_dict(objeto) -> dict:
    return {campo: getattr(objeto, campo) for campo in CAMPOS[type(objeto)]}


def listar(sesion: Session, modelo) -> list[dict]:
    return [a_dict(o) for o in sesion.scalars(select(modelo).order_by(modelo.orden))]


@publico.get("/catalogo")
def catalogo(sesion: Session = Depends(obtener_sesion)):
    return listar(sesion, ActividadCatalogo)


@publico.get("/mensajes")
def mensajes(sesion: Session = Depends(obtener_sesion)):
    return listar(sesion, MensajeValidado)


@publico.get("/directorio")
def directorio(sesion: Session = Depends(obtener_sesion)):
    return listar(sesion, RecursoAyuda)


# ---------- Administración (CRUD) ----------


def validar_mensaje(entrada: MensajeEntrada, usuario: Usuario) -> dict:
    """Solo se aceptan mensajes que el diccionario clasifica como 'motivadora'."""
    clasificacion = clasificar(entrada.texto)
    if clasificacion["categoria"] != "motivadora":
        raise HTTPException(
            422,
            detail={
                "detail": f"El mensaje no es motivador (clasificación: {clasificacion['categoria']})",
                "clasificacion": clasificacion,
            },
        )
    datos = entrada.model_dump(exclude={"id"})
    datos["validado_por"] = entrada.validado_por or usuario.nombre
    return datos


def registrar_crud(ruta: str, modelo, esquema: type[BaseModel], preparar=None) -> None:
    """Crea POST /admin/{ruta}, PUT y DELETE /admin/{ruta}/{id} para un modelo.

    `preparar(entrada, usuario)` permite validar o completar los datos antes de guardar.
    """

    def datos_de(entrada, usuario) -> dict:
        return preparar(entrada, usuario) if preparar else entrada.model_dump(exclude={"id"})

    def crear(entrada: esquema, usuario: Usuario = Depends(solo_admin), sesion: Session = Depends(obtener_sesion)):
        datos = datos_de(entrada, usuario)
        identificador = entrada.id or nuevo_id()
        if sesion.get(modelo, identificador):
            raise HTTPException(409, "Ya existe un elemento con ese id")
        orden = (sesion.scalar(select(func.max(modelo.orden))) or 0) + 1
        objeto = modelo(id=identificador, orden=orden, **datos)
        sesion.add(objeto)
        sesion.commit()
        return a_dict(objeto)

    def actualizar(
        id: str, entrada: esquema, usuario: Usuario = Depends(solo_admin), sesion: Session = Depends(obtener_sesion)
    ):
        objeto = sesion.get(modelo, id)
        if objeto is None:
            raise HTTPException(404, "No existe un elemento con ese id")
        for campo, valor in datos_de(entrada, usuario).items():
            setattr(objeto, campo, valor)
        sesion.commit()
        return a_dict(objeto)

    def borrar(id: str, sesion: Session = Depends(obtener_sesion)):
        objeto = sesion.get(modelo, id)
        if objeto is None:
            raise HTTPException(404, "No existe un elemento con ese id")
        sesion.delete(objeto)
        sesion.commit()
        return Response(status_code=204)

    admin.add_api_route(f"/{ruta}", crear, methods=["POST"], status_code=201, name=f"crear_{ruta}")
    admin.add_api_route(f"/{ruta}/{{id}}", actualizar, methods=["PUT"], name=f"actualizar_{ruta}")
    admin.add_api_route(f"/{ruta}/{{id}}", borrar, methods=["DELETE"], status_code=204, name=f"borrar_{ruta}")


registrar_crud("catalogo", ActividadCatalogo, ActividadEntrada)
registrar_crud("mensajes", MensajeValidado, MensajeEntrada, preparar=validar_mensaje)
registrar_crud("directorio", RecursoAyuda, RecursoEntrada)
