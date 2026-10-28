# -*- coding: utf-8 -*-
"""Inspeccion sin efectos de la respuesta ENCOL 8100.

Paso preliminar: todavía NO interpreta horarios ni permite habilitar bloqueos.
No inventa nombres de columnas de OMIE. Compatible con Python 2.7.
"""
from __future__ import absolute_import

try:
    basestring
except NameError:
    basestring = str


class Formato8100NoReconocido(ValueError):
    pass


def _valor(nodo):
    if isinstance(nodo, dict) and 'v' in nodo:
        return nodo['v']
    return nodo


def _texto_seguro(valor):
    valor = _valor(valor)
    try:
        texto = unicode(valor)
    except NameError:
        texto = str(valor)
    except (TypeError, ValueError, UnicodeError):
        return u'<valor no convertible>'
    return texto[:160]


def _columnas_fila(nodo, resultado, tipo=None):
    """Explora contenedores ENCOL sin imponer el esquema de la 8100."""
    if isinstance(nodo, (list, tuple)):
        for item in nodo:
            _columnas_fila(item, resultado, tipo=tipo)
        return
    if not isinstance(nodo, dict):
        return
    if 'n' in nodo and 'v' in nodo:
        nombre = nodo['n']
        if isinstance(nombre, basestring) and nombre:
            # Conservar duplicados durante el diagnóstico para detectarlos.
            resultado.append({'nombre': nombre, 'tipo': tipo or '?',
                              'valor': _texto_seguro(nodo['v'])})
        return
    for nombre, hijo in nodo.items():
        # Txt/Num/Fec/Feh/etc., o elementos _value_1/Columna/Columnas.
        _columnas_fila(hijo, resultado, tipo=nombre if nombre not in
                       ('_value_1', 'Columna', 'Columnas') else tipo)


def diagnosticar_respuesta_8100(datos, max_muestras=3):
    """Describe la estructura recibida; NUNCA devuelve reglas operativas.

    Una respuesta vacía es válida pero NO significa que no haya exclusiones.
    Un error funcional OMIE no puede confundirse con datos vacíos.
    """
    if not isinstance(datos, dict):
        raise Formato8100NoReconocido('Respuesta 8100 sin cuerpo de diccionario')
    codigo = _valor(datos.get('CodConsulta'))
    if isinstance(codigo, bool) or str(codigo).strip() != '8100':
        raise Formato8100NoReconocido('Respuesta distinta de la consulta 8100')
    if datos.get('Respuesta'):
        raise Formato8100NoReconocido('OMIE devolvio mensajes: %r' %
                                     (datos['Respuesta'],))
    if 'Fila' not in datos or not isinstance(datos['Fila'], list):
        raise Formato8100NoReconocido('8100 no contiene una lista Fila')
    filas = datos['Fila']
    columnas = {}
    muestras = []
    for indice, fila in enumerate(filas):
        celdas = []
        _columnas_fila(fila, celdas)
        for celda in celdas:
            nombre = celda['nombre']
            if nombre not in columnas:
                columnas[nombre] = []
            if celda['tipo'] not in columnas[nombre]:
                columnas[nombre].append(celda['tipo'])
        if indice < max_muestras:
            muestras.append(celdas)
    return {
        'consulta': 8100,
        'total_filas': len(filas),
        'columnas_y_tipos': columnas,
        'muestras': muestras,
        'solo_diagnostico': True,
    }
