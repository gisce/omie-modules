# -*- coding: utf-8 -*-
"""Resultado seguro de lotes de ofertas SIOM para automatismos OpenERP 5.

Esta capa NO envia correo ni hace commit: los automatismos externos deben
persistir la transaccion del ERP ANTES de usar el asunto/texto de informe.
No reintenta jamas una oferta con resultado incierto.
"""
from __future__ import absolute_import

from datetime import datetime
import uuid


class EstadoOfertaNoConfirmado(Exception):
    """La escritura local no acredita el resultado de la oferta."""


def _unicode_seguro(valor):
    """No propagar un UnicodeDecodeError al construir el informe (Py2.7)."""
    try:
        text_type = unicode
    except NameError:
        text_type = str
    if isinstance(valor, BaseException) and valor.args:
        return _unicode_seguro(valor.args[0])
    if isinstance(valor, text_type):
        return valor
    if isinstance(valor, bytes):
        return valor.decode('utf-8', 'replace')
    try:
        return text_type(valor)
    except (UnicodeError, TypeError, ValueError):
        return u'<detalle no representable>'


def _validar_ids(ids):
    if isinstance(ids, (int, long_type())):
        ids = [ids]
    elif not isinstance(ids, (list, tuple)):
        raise ValueError('ids debe ser una lista de identificadores de oferta')
    ids = list(ids)
    if any(isinstance(i, bool) or not isinstance(i, (int, long_type())) or i <= 0
           for i in ids):
        raise ValueError('Los identificadores deben ser enteros positivos')
    if len(ids) != len(set(ids)):
        raise ValueError('No se puede enviar la misma oferta dos veces en un lote')
    return ids


def long_type():
    try:
        return long
    except NameError:
        return int


def _resumen(informe):
    conteos = dict((estado, 0) for estado in (
        'enviada', 'enviada_error', 'bloqueada', 'no_confirmada', 'pendiente'))
    for item in informe['ofertas']:
        conteos[item['estado']] += 1
    informe['totales'] = conteos
    informe['resultado'] = ('con_incidencias' if (conteos['no_confirmada'] or
                            conteos['bloqueada'] or conteos['pendiente']) else
                            'completado_con_rechazos' if conteos['enviada_error']
                            else 'completado')
    informe['asunto_correo'] = (u'OMIE SIOM - Envio automatizado %s - %s' %
                                 (informe['id_ejecucion'], informe['resultado']))
    lineas = [u'Resultado del envio automatizado a OMIE',
              u'Ejecucion: %s' % informe['id_ejecucion'],
              u'Fecha UTC: %s' % informe['fecha_inicio_utc'],
              u'Estado: %s' % informe['resultado'],
              u'Ofertas recibidas: %s' % len(informe['ofertas']),
              u'Enviadas aceptadas: %s' % conteos['enviada'],
              u'Respondidas con rechazo: %s' % conteos['enviada_error'],
              u'Bloqueadas antes del SOAP: %s' % conteos['bloqueada'],
              u'Resultado no confirmado: %s' % conteos['no_confirmada'],
              u'No intentadas: %s' % conteos['pendiente'], u'']
    for item in informe['ofertas']:
        lineas.append(u'Oferta %s: %s%s' % (
            item['oferta_id'], item['estado'],
            (u' - %s' % item['detalle']) if item['detalle'] else u''))
    if conteos['no_confirmada'] or conteos['bloqueada'] or conteos['pendiente']:
        lineas.extend((u'', u'ATENCION: existen ofertas sin envio confirmado.',
                       u'No reenviar automaticamente; revisar el registro de SIOM.',
                       u'Este informe no acredita que OMIE haya rechazado la oferta no confirmada.'))
    informe['texto_correo'] = u'\n'.join(lineas)
    return informe


def ejecutar_lote(cr, ids, enviar, leer_estado, es_bloqueo=None):
    """Envio sincrono por oferta, con SAVEPOINT y cierre controlado.

    * enviar(oferta_id): llama al metodo ORM existente SIN reintentos.
    * leer_estado(oferta_id): obtiene el estado tras la escritura local.
    * es_bloqueo(exc): True unicamente si se sabe que NO se llamo a SOAP.
    * No hay excepcion por incidencias conocidas: retorna reporte estructurado.
    * Si falla la gestion del SAVEPOINT se eleva: NO se puede dar por fiable
      el cursor ni garantizar el commit del resto de resultados.
    """
    ids = _validar_ids(ids)
    if es_bloqueo is None:
        es_bloqueo = lambda exc: False
    informe = {
        'id_ejecucion': uuid.uuid4().hex,
        'fecha_inicio_utc': datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'),
        'ofertas': [],
    }
    for indice, oferta_id in enumerate(ids):
        # Literal construido solo con un entero controlado; no SQL inyectable.
        savepoint = 'siom_auto_%s' % indice
        cr.execute('SAVEPOINT ' + savepoint)
        try:
            enviar(oferta_id)
            estado = leer_estado(oferta_id)
            if estado not in ('enviada', 'enviada_error'):
                # Ya podria existir una respuesta SOAP; NO seguir enviando.
                raise EstadoOfertaNoConfirmado(
                    'Estado local inesperado tras SOAP: %s' % _unicode_seguro(estado))
            cr.execute('RELEASE SAVEPOINT ' + savepoint)
        except Exception as exc:
            # Solo etiquetar como bloqueada si el controlador confirma
            # que no se inicio la comunicacion de ESTA oferta.
            bloqueada = es_bloqueo(exc)
            detalle = u'%s: %s' % (type(exc).__name__, _unicode_seguro(exc))
            # Si el cursor de negocio quedo abortado, el rollback al savepoint
            # permite confirmar ofertas anteriores sin perder su trabajo.
            cr.execute('ROLLBACK TO SAVEPOINT ' + savepoint)
            cr.execute('RELEASE SAVEPOINT ' + savepoint)
            informe['ofertas'].append({
                'oferta_id': oferta_id,
                'estado': 'bloqueada' if bloqueada else 'no_confirmada',
                'detalle': detalle[:400]})
            for sin_intentar in ids[indice + 1:]:
                informe['ofertas'].append({
                    'oferta_id': sin_intentar, 'estado': 'pendiente',
                    'detalle': u'No se ha intentado por una incidencia anterior'})
            # Nunca continuar tras un fallo: puede haberse iniciado SOAP,
            # y reintentar o continuar seria potencialmente inseguro.
            break
        else:
            informe['ofertas'].append({
                'oferta_id': oferta_id, 'estado': estado, 'detalle': u''})
    return _resumen(informe)
