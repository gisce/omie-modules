# -*- coding: utf-8 -*-
"""Conversor estricto de la consulta encolumnada OMIE 8101.

No importa OpenERP ni Zeep. Acepta los diccionarios retornados por
zeep.helpers.serialize_object, conservando los ceros como tiempos validos.
"""
from __future__ import absolute_import

try:
    basestring
except NameError:
    basestring = str

NOMBRES = ('CdConsult', 'Titulo', 'TMinAge', 'TMinCert', 'TipoAcceso')


class Formato8101Error(ValueError):
    pass


def _valor(elemento):
    if isinstance(elemento, dict):
        if 'v' in elemento:
            return elemento['v']
    return elemento


def _entero_no_negativo(valor, campo):
    valor = _valor(valor)
    if isinstance(valor, bool) or valor is None:
        raise Formato8101Error('%s debe ser entero no negativo' % campo)
    if isinstance(valor, basestring):
        valor = valor.strip()
        if not valor or not valor.isdigit():
            raise Formato8101Error('%s no es entero decimal' % campo)
    try:
        entero = int(valor)
    except (TypeError, ValueError, OverflowError):
        raise Formato8101Error('%s no es entero' % campo)
    # No admitir fracciones o conversiones truncadas.
    if entero != valor and not isinstance(valor, basestring):
        raise Formato8101Error('%s no es entero exacto' % campo)
    if not 0 <= entero <= 2147483647:
        raise Formato8101Error('%s fuera de rango' % campo)
    return entero


def _extraer_columnas(nodo, recogidas):
    """Desciende SOLO por los contenedores del formato encolumnado."""
    if isinstance(nodo, list):
        for item in nodo:
            _extraer_columnas(item, recogidas)
        return
    if not isinstance(nodo, dict):
        raise Formato8101Error('Estructura de fila desconocida')
    # Estructura directa, util en pruebas o adaptadores.
    if 'CdConsult' in nodo and not any(k in nodo for k in ('_value_1', 'Columna')):
        for clave in NOMBRES:
            if clave in nodo:
                if clave in recogidas:
                    raise Formato8101Error('Columna duplicada: %s' % clave)
                recogidas[clave] = _valor(nodo[clave])
        return
    # Cada columna SOAP es un elemento alternativo Txt/Num/Feh/...
    for tipo in ('Txt', 'Num'):
        columna = nodo.get(tipo)
        if columna is not None:
            if not isinstance(columna, dict):
                raise Formato8101Error('Columna %s invalida' % tipo)
            nombre = columna.get('n')
            if nombre in NOMBRES:
                if nombre in recogidas:
                    raise Formato8101Error('Columna duplicada: %s' % nombre)
                recogidas[nombre] = columna.get('v')
    for contenedor in ('_value_1', 'Columna', 'Columnas'):
        if contenedor in nodo and nodo[contenedor] is not None:
            _extraer_columnas(nodo[contenedor], recogidas)


def parsear_8101(datos):
    """Devuelve lista de dicts lista para ORM, o lanza Formato8101Error.

    Nunca interpreta filas vacias como limites de cero.
    """
    if not isinstance(datos, dict):
        raise Formato8101Error('Respuesta de OMIE sin cuerpo valido')
    codigo = datos.get('CodConsulta')
    if _entero_no_negativo(codigo, 'CodConsulta') != 8101:
        raise Formato8101Error('Respuesta de una consulta distinta de 8101')
    mensajes = datos.get('Respuesta')
    if mensajes:
        raise Formato8101Error('OMIE ha devuelto mensajes de respuesta: %r' % mensajes)
    filas = datos.get('Fila')
    if filas is None:
        raise Formato8101Error('Falta el campo Fila (diferente de lista vacia)')
    if not isinstance(filas, list):
        raise Formato8101Error('Fila debe ser una lista')
    resultado = []
    vistos = set()
    for fila in filas:
        c = {}
        _extraer_columnas(fila, c)
        faltantes = [nombre for nombre in NOMBRES if nombre not in c]
        if faltantes:
            raise Formato8101Error('Faltan columnas en 8101: %s' % ','.join(faltantes))
        codigo_fila = _entero_no_negativo(c['CdConsult'], 'CdConsult')
        if codigo_fila in vistos:
            raise Formato8101Error('Código de consulta duplicado: %s' % codigo_fila)
        vistos.add(codigo_fila)
        titulo, acceso = c['Titulo'], c['TipoAcceso']
        if not isinstance(titulo, basestring) or not titulo.strip():
            raise Formato8101Error('Titulo vacio o invalido')
        if not isinstance(acceso, basestring) or not acceso.strip():
            raise Formato8101Error('TipoAcceso vacio o invalido')
        resultado.append({
            'consulta': codigo_fila,
            'titulo': titulo.strip(),
            'tiempo_agente_ms': _entero_no_negativo(c['TMinAge'], 'TMinAge'),
            'tiempo_certificado_ms': _entero_no_negativo(c['TMinCert'], 'TMinCert'),
            'tipo_acceso': acceso.strip(),
        })
    return resultado
