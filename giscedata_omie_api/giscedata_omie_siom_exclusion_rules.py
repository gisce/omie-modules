# -*- coding: utf-8 -*-
"""Contrato ENCOL 8100 observado en pruebas: parseo y evaluacion de horas.

SIN zona horaria asumida: la hora de evaluacion debe corresponder al huso
confirmado por OMIE. Se usa [inicio, fin) y se admiten cruces de medianoche.
La activacion en el controlador permanece deshabilitada por defecto.
"""
from __future__ import absolute_import

import re
from datetime import time

from giscedata_omie_api.giscedata_omie_siom_exclusion_diagnostic import (
    diagnosticar_respuesta_8100, Formato8100NoReconocido)

COLUMNAS = {
    'CdConsult': 'Num', 'Titulo': 'Txt', 'HoraIni': 'Hor',
    'HoraFin': 'Hor', 'TipoAcceso': 'Txt',
}
HORA = re.compile(r'^([0-2][0-9]):([0-5][0-9]):([0-5][0-9])$')
try:
    text_types = (basestring,)
except NameError:
    text_types = (str,)


def _segundos(valor, permitir_fracciones=False):
    if isinstance(valor, time):
        if valor.microsecond and not permitir_fracciones:
            raise Formato8100NoReconocido('Hora 8100 con fracciones no previstas')
        segundos = valor.hour * 3600 + valor.minute * 60 + valor.second
        return segundos + (valor.microsecond / 1000000.0 if permitir_fracciones else 0)
    # Zeep puede devolver texto Unicode (Py2/Py3) o un objeto time.
    if isinstance(valor, bytes) and not isinstance(valor, str):
        try:
            valor = valor.decode('ascii')
        except UnicodeError:
            raise Formato8100NoReconocido('Hora 8100 no ASCII')
    if not isinstance(valor, text_types):
        raise Formato8100NoReconocido('Hora 8100 no textual')
    match = HORA.match(valor)
    if not match:
        raise Formato8100NoReconocido('Hora 8100 invalida: %r' % (valor,))
    hora, minuto, segundo = (int(x) for x in match.groups())
    if hora > 23:
        raise Formato8100NoReconocido('Hora 8100 fuera de rango')
    return hora * 3600 + minuto * 60 + segundo


def _hora_texto(valor):
    segundos = _segundos(valor)
    return '%02d:%02d:%02d' % (segundos // 3600,
                                segundos // 60 % 60, segundos % 60)


def parsear_intervalos_8100(datos):
    """Devuelve la totalidad de filas validas, o falla sin resultados parciales.

    Solo conocemos el tipo de acceso AMBAS. Otros tipos requieren revisar
    la semantica oficial antes de usarlos para permitir o denegar accesos.
    """
    diagnosticar_respuesta_8100(datos)
    filas = datos['Fila']
    if not filas:
        return []  # El llamador NO debe interpretar vacio como borrar limites.
    resultados = []
    vistos = set()
    for fila in filas:
        if not isinstance(fila, dict) or not isinstance(fila.get('_value_1'), list):
            raise Formato8100NoReconocido('Fila 8100 sin _value_1')
        campos = {}
        for columna in fila['_value_1']:
            if not isinstance(columna, dict):
                raise Formato8100NoReconocido('Columna 8100 mal formada')
            for tipo, celda in columna.items():
                if celda is None:
                    continue
                if not isinstance(celda, dict) or set(celda) != set(('n', 'v')):
                    raise Formato8100NoReconocido('Celda 8100 mal formada')
                nombre = celda['n']
                if nombre not in COLUMNAS or COLUMNAS[nombre] != tipo or nombre in campos:
                    raise Formato8100NoReconocido('Columna 8100 no prevista o duplicada: %r' % nombre)
                campos[nombre] = celda['v']
        if set(campos) != set(COLUMNAS):
            raise Formato8100NoReconocido('Faltan campos en fila 8100')
        codigo = campos['CdConsult']
        if isinstance(codigo, bool):
            raise Formato8100NoReconocido('Codigo de consulta 8100 invalido')
        try:
            consulta = int(codigo)
        except (TypeError, ValueError, OverflowError):
            raise Formato8100NoReconocido('Codigo de consulta 8100 invalido')
        if not 0 < consulta <= 2147483647 or str(codigo).strip() != str(consulta):
            raise Formato8100NoReconocido('Codigo de consulta 8100 no entero')
        titulo = campos['Titulo']
        acceso = campos['TipoAcceso']
        if (not isinstance(titulo, text_types) or not titulo or
                len(titulo) > 256 or not isinstance(acceso, text_types) or
                acceso != 'AMBAS'):
            raise Formato8100NoReconocido('Titulo o TipoAcceso 8100 desconocido')
        inicio = _hora_texto(campos['HoraIni'])
        fin = _hora_texto(campos['HoraFin'])
        if inicio == fin:
            raise Formato8100NoReconocido('Ventana 8100 de inicio y fin identicos')
        clave = (consulta, inicio, fin, acceso)
        if clave in vistos:
            raise Formato8100NoReconocido('Intervalo 8100 repetido')
        vistos.add(clave)
        resultados.append({'consulta': consulta, 'titulo': titulo, 'inicio': inicio,
                           'fin': fin, 'tipo_acceso': acceso})
    return resultados


def consulta_excluida(intervalos, consulta, hora_local):
    """Evaluacion pura, requiere hora LOCAL en el huso confirmado.

    La interpretacion diaria y [inicio, fin) queda pendiente de confirmacion
    de OMIE. No usar sin activar expresamente esa semantica en produccion.
    """
    # PostgreSQL devuelve time con microsegundos; las ventanas OMIE siguen
    # usando exclusivamente horas HH:MM:SS validadas por el parser.
    actual = _segundos(hora_local, permitir_fracciones=True)
    for fila in intervalos:
        if fila['consulta'] != consulta:
            continue
        if fila['tipo_acceso'] != 'AMBAS':
            raise Formato8100NoReconocido('TipoAcceso no soportado para control')
        inicio, fin = _segundos(fila['inicio']), _segundos(fila['fin'])
        if inicio == fin:
            raise Formato8100NoReconocido('Ventana degenerada')
        if ((inicio < fin and inicio <= actual < fin) or
                (inicio > fin and (actual >= inicio or actual < fin))):
            return fila
    return None
