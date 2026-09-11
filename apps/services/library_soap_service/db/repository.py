"""Acceso a datos del modulo SOAP.

Reglas seguidas aqui (Parte 6, punto 12 del ejercicio guiado):
  - Siempre consultas parametrizadas (nunca se concatena SQL con datos
    del cliente): se llama a las funciones/vistas definidas en
    sql/soap_module.sql, pasando los valores como parametros de psycopg2.
  - Cada operacion abre su propia conexion/transaccion y hace commit solo
    si no hubo error; ante excepcion, rollback explicito.
  - Los errores de negocio (duplicado, no encontrado) se traducen aqui a
    excepciones propias para que soap/service.py los convierta en el
    SOAP Fault correcto, sin que la capa de datos conozca nada de XML.
"""

import psycopg2
import psycopg2.errors

from db.connection import get_connection


class RegistroDuplicadoError(Exception):
    """El clasificador ya habia clasificado este concepto en este libro."""


class RecursoNoEncontradoError(Exception):
    """El ISBN o el id de concepto referenciado no existen."""


def obtener_conceptos_pendientes(correo_clasificador):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id_clasificador FROM clasificadores WHERE correo = %s", (correo_clasificador,))
            row = cur.fetchone()
            id_clasificador = row[0] if row else None

            cur.execute("SELECT * FROM fn_obtener_conceptos_pendientes(%s)", (id_clasificador,))
            columnas = [c.name for c in cur.description]
            return [dict(zip(columnas, fila)) for fila in cur.fetchall()]
    finally:
        conn.close()


def registrar_clasificacion(nombre, apellido, correo, isbn, id_concepto, modelo_cloud, origen_cliente):
    conn = get_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT fn_registrar_clasificacion(%s, %s, %s, %s, %s, %s, %s)",
                    (nombre, apellido, correo, isbn, id_concepto, modelo_cloud, origen_cliente),
                )
                return cur.fetchone()[0]
    except psycopg2.errors.UniqueViolation:
        conn.rollback()
        raise RegistroDuplicadoError(
            f"El clasificador '{correo}' ya registro una clasificacion para este concepto en este libro."
        )
    except psycopg2.Error as exc:
        conn.rollback()
        mensaje = str(exc)
        if "LIBRO_NO_ENCONTRADO" in mensaje:
            raise RecursoNoEncontradoError(f"No existe ningun libro con isbn '{isbn}'.")
        if "CONCEPTO_NO_ENCONTRADO" in mensaje:
            raise RecursoNoEncontradoError(f"No existe el concepto con id '{id_concepto}'.")
        raise
    finally:
        conn.close()


def obtener_progreso_usuario(correo):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM fn_obtener_progreso_usuario(%s)", (correo,))
            total_conceptos, total_clasificados, total_pendientes = cur.fetchone()
            return {
                "totalConceptos": total_conceptos,
                "totalClasificados": total_clasificados,
                "totalPendientes": total_pendientes,
            }
    finally:
        conn.close()


def registrar_cliente_servido(tipo_cliente, identificador):
    conn = get_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("SELECT fn_registrar_cliente_servido(%s, %s)", (tipo_cliente, identificador))
    finally:
        conn.close()


MODELOS_CLOUD = ("IaaS", "PaaS", "SaaS", "FaaS")


def obtener_estadisticas_por_modelo():
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM fn_obtener_estadisticas_por_modelo()")
            encontrados = dict(cur.fetchall())
    finally:
        conn.close()
    # Se completan con 0 los modelos sin clasificaciones aun, para que el
    # cliente siempre reciba las 4 categorias (contrato estable).
    return [{"modeloCloud": modelo, "total": encontrados.get(modelo, 0)} for modelo in MODELOS_CLOUD]
