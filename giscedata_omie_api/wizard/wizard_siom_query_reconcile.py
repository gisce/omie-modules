# -*- coding: utf-8 -*-
"""Conciliacion manual y auditada de una consulta SIOM bloqueada."""
from __future__ import absolute_import

from osv import osv, fields
from tools.translate import _


class WizardSiomQueryReconcile(osv.osv_memory):
    _name = 'wizard.siom.query.reconcile'
    _description = _('Conciliar reserva pendiente de consulta SIOM')

    def conciliar(self, cr, uid, ids, context=None):
        if not ids or len(ids) != 1:
            raise osv.except_osv('Error', _('Seleccione un unico asistente.'))
        permisos = self.pool.get('wizard.siom.minimum.time.update')
        if not permisos._puede_actualizar(cr, uid, context=context):
            raise osv.except_osv('Acceso denegado',
                                 _('Solo OMIE Manager puede conciliar consultas.'))
        wizard = self.simple_browse(cr, uid, ids[0], context=context)
        if wizard.state != 'init':
            raise osv.except_osv('Error', _('El asistente ya se ha ejecutado.'))
        if not wizard.intento_id or not wizard.motivo or not wizard.confirmado:
            raise osv.except_osv('Error',
                                 _('Seleccione reserva, indique motivo y confirme verificaciones.'))
        model = self.pool.get('giscedata.omie.siom.query.execution')
        # El metodo de negocio exige uid=1. La elevacion SOLO se realiza
        # tras validar grupo y parametros del solicitante.
        model.conciliar_reserva(cr, 1, wizard.intento_id.id, wizard.motivo,
                               confirmado=True, usuario_solicitante=uid)
        self.write(cr, uid, ids, {'state': 'end'}, context=context)
        return True

    _columns = {
        'state': fields.selection([('init', 'Inicial'), ('end', 'Finalizado')],
                                  'Estado', required=True, readonly=True),
        'intento_id': fields.many2one('giscedata.omie.siom.query.execution',
                                     'Reserva pendiente', required=True,
                                     domain=[('estado', '=', 'reservada')]),
        'motivo': fields.text('Motivo y comprobaciones realizadas', required=True),
        'confirmado': fields.boolean('He comprobado que la consulta ya no se ejecuta'),
    }
    _defaults = {'state': lambda *args: 'init'}


WizardSiomQueryReconcile()
