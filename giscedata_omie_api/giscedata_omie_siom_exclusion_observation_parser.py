# -*- coding: utf-8 -*-
"""Evidencia JSON de 8100, sin inferir reglas operativas de exclusión.

No depende de OpenERP. Se preservan las filas ENCOL originales para poder
validar el parser futuro cuando OMIE devuelva datos. Python 2.7 / 3.x.
"""
from __future__ import absolute_import

import hashlib
import json
from datetime import date, datetime, time
from decimal import Decimal

from giscedata_omie_api.giscedata_omie_siom_exclusion_diagnostic import (
    diagnosticar_respuesta_8100, Formato8100NoReconocido)

MAX_FILAS = 5000
MAX_BYTES = 1024 * 1024


def _json_desconocido(valor):
    if isinstance(valor, (datetime, date, time)):
        return valor.isoformat()
    if isinstance(valor, Decimal):
        return str(valor)
    raise TypeError('Valor 8100 no serializable: %s' % type(valor).__name__)


def preparar_observacion_8100(datos, max_bytes=MAX_BYTES):
    """Valida y devuelve una observación inerte y acotada, lista para ORM.

    La respuesta vacía es una OBSERVACION, nunca una lista de exclusiones
    confirmadamente vacía ni una orden para borrar reglas anteriores.
    Ninguna salida de esta función se usa para autorizar/bloquear consultas.
    """
    diagnostico = diagnosticar_respuesta_8100(datos)
    filas = datos['Fila']
    if len(filas) > MAX_FILAS:
        raise Formato8100NoReconocido('Demasiadas filas 8100 para guardar evidencia')

    try:
        respuesta_json = json.dumps(
            {'CodConsulta': datos['CodConsulta'], 'Fila': filas},
            default=_json_desconocido, ensure_ascii=True, sort_keys=True,
            allow_nan=False, separators=(',', ':'))
        columnas_json = json.dumps(
            diagnostico['columnas_y_tipos'], ensure_ascii=True, sort_keys=True)
        muestras_json = json.dumps(
            diagnostico['muestras'], ensure_ascii=True, sort_keys=True)
    except (TypeError, ValueError, OverflowError) as exc:
        raise Formato8100NoReconocido('8100 no serializable sin perdidas: %s' % exc)
    if len(respuesta_json.encode('utf-8')) > max_bytes:
        raise Formato8100NoReconocido('Respuesta 8100 mayor que el limite seguro de evidencia')

    return {
        'estado': 'con_datos' if filas else 'vacia',
        'total_filas': len(filas),
        'columnas_json': columnas_json,
        'muestras_json': muestras_json,
        'respuesta_json': respuesta_json,
        'huella_sha256': hashlib.sha256(respuesta_json.encode('utf-8')).hexdigest(),
    }
