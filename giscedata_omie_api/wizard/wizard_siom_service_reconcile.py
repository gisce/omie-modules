# -*- coding: utf-8 -*-
"""Conciliacion manual de respuestas de alta MD/MI pendientes en SIOM.

La comprobacion externa es responsabilidad del usuario autorizado. Este wizard
NUNCA envia ofertas ni modifica los resultados recibidos de OMIE.
"""
from __future__ import absolute_import

import logging

from osv import osv, fields
from tools.translate import _

_logger = logging.getLogger(__name__)


class WizardSiomServiceReconcile(osv.osv_memory):
    _name = 'wizard.siom.service.reconcile'
    _description = _('Conciliar envio de oferta SIOM pendiente')

    def conciliar(self, cr, uid, ids, context=None):
        if not ids or len(ids) != 1:
            raise osv.except_osv('Error', _('Seleccione un unico asistente.'))

        # No confiar en la visibilidad del boton: comprobar permisos tambien
        # para invocaciones RPC directas, ANTES de elevar a administrador.
        permisos = self.pool.get('wizard.siom.minimum.time.update')
        if not permisos._puede_actualizar(cr, uid, context=context):
            raise osv.except_osv('Acceso denegado',
                                 _('Solo OMIE Manager puede conciliar envios SIOM.'))

        wizard = self.simple_browse(cr, uid, ids[0], context=context)
        if wizard.state != 'init':
            raise osv.except_osv('Error', _('El asistente ya se ha ejecutado.'))
        if (not wizard.intento_id or not wizard.comprobado_omie or
                not wizard.proceso_terminado):
            raise osv.except_osv(
                'Error',
                _('Seleccione un envio y confirme la comprobacion en OMIE '
                  'y que el proceso emisor ha terminado.'))

        motivo = (wizard.justificacion or '').strip()
        if len(motivo) < 15 or len(motivo) > 190:
            raise osv.except_osv(
                'Error', _('Indique una justificacion de entre 15 y 190 caracteres.'))

        # Guardar el UID real en el diagnostico durable de conciliacion,
        # sin alterar el modelo persistente ni sus restricciones transaccionales.
        # El backend usa una conexion separada y registra fecha_fin en UTC.
        justificacion = 'Usuario ERP %s: %s' % (uid, motivo)
        servicio = self.pool.get('giscedata.omie.siom.service.execution')
        servicio.conciliar_envio(
            cr, 1, wizard.intento_id.id, justificacion,
            proceso_terminado=True
        )
        _logger.warning('Envio SIOM %s conciliado por uid=%s',
                        wizard.intento_id.id, uid)
        self.write(cr, uid, ids, {'state': 'end'}, context=context)
        return True

    _columns = {
        'state': fields.selection([('init', 'Inicial'), ('end', 'Finalizado')],
                                  'Estado', required=True, readonly=True),
        'intento_id': fields.many2one(
            'giscedata.omie.siom.service.execution', 'Envio SIOM', required=True,
            readonly=True),
        'servicio': fields.related('intento_id', 'servicio', type='char',
                                   string='Servicio', size=100, readonly=True),
        'oferta_id': fields.related('intento_id', 'oferta_id', type='integer',
                                    string='Oferta ERP', readonly=True),
        'estado_envio': fields.related('intento_id', 'estado', type='char',
                                      string='Estado del envio', size=32, readonly=True),
        'codigo_respuesta': fields.related('intento_id', 'codigo_respuesta',
                                           type='char', string='Codigo general OMIE',
                                           size=64, readonly=True),
        'respuesta_json': fields.related('intento_id', 'respuesta_json',
                                         type='text', string='Respuesta SOAP',
                                         readonly=True),
        'justificacion': fields.text('Justificacion y comprobaciones', required=True),
        'comprobado_omie': fields.boolean(
            'He verificado en OMIE el resultado de este envio'),
        'proceso_terminado': fields.boolean(
            'Confirmo que el proceso emisor ha terminado'),
    }
    _defaults = {
        'state': lambda *args: 'init',
        'intento_id': lambda self, cr, uid, context=None:
            (context or {}).get('default_intento_id') or
            (context or {}).get('active_id'),
    }


WizardSiomServiceReconcile()
