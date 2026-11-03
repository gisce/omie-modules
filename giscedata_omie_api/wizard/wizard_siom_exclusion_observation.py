# -*- coding: utf-8 -*-
"""Asistente manual 8100; el grupo Manager autoriza elevación a uid=1."""
from __future__ import absolute_import

import logging
from osv import osv, fields
from tools.translate import _

_logger = logging.getLogger(__name__)


class WizardSiomExclusionObservation(osv.osv_memory):
    _name = 'wizard.siom.exclusion.observation'
    _description = _('Consultar períodos de exclusión SIOM 8100 (diagnóstico)')

    def _puede_consultar(self, cursor, uid, context=None):
        if uid == 1:
            return True
        if context is None:
            context = {}
        data = self.pool.get('ir.model.data')
        users = self.pool.get('res.users')
        try:
            _model, grupo_id = data.get_object_reference(
                cursor, 1, 'giscedata_omie_api', 'group_giscedata_omie_oferta_u')
        except ValueError:
            return False
        usuario = users.simple_browse(cursor, uid, uid, context=context)
        return grupo_id in [g.id for g in usuario.groups_id]

    def consultar_desde_omie(self, cursor, uid, ids, context=None):
        if context is None:
            context = {}
        if not ids or len(ids) != 1:
            raise osv.except_osv('Error', _('Seleccione un único asistente.'))
        if not self._puede_consultar(cursor, uid, context=context):
            raise osv.except_osv('Acceso denegado',
                                 _('Solo OMIE Manager puede consultar la 8100.'))
        wizard = self.simple_browse(cursor, uid, ids[0], context=context)
        if wizard.state != 'init':
            raise osv.except_osv('Error', _('La consulta ya se ha ejecutado.'))
        _logger.info('Observación manual SIOM 8100 solicitada por uid=%s', uid)
        modelo = self.pool.get('giscedata.omie.siom.exclusion.observation')
        resultado = modelo.registrar_observacion_8100(cursor, 1, context=context)
        if resultado['estado'] == 'vacia':
            mensaje = (_('OMIE ha respondido sin filas. NO implica ausencia de '
                         'períodos de exclusión; no se modifican reglas.'))
        else:
            mensaje = (_('Filas registradas para analizar su estructura. '
                         'No se han activado restricciones.'))
        mensaje += ('\nObservación: %(observacion_id)s'
                    '\nFilas: %(total_filas)s'
                    '\nSHA-256: %(huella_sha256)s') % resultado
        self.write(cursor, uid, ids, {'state': 'end', 'info': mensaje},
                   context=context)
        return True

    _columns = {
        'state': fields.selection([('init', 'Inicial'), ('end', 'Finalizado')],
                                  'Estado', required=True, readonly=True),
        'info': fields.text('Resultado', readonly=True),
    }
    _defaults = {'state': lambda *args: 'init'}


WizardSiomExclusionObservation()
