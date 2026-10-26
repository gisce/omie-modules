# -*- coding: utf-8 -*-
"""Actualizacion manual de la consulta SIOM 8101 desde OpenERP 5.0.

El modelo persistente exige uid=1; solo elevamos al invocarlo DESPUES de
validar que el usuario solicitante pertenece al grupo OMIE Manager.
No escribe directamente las tablas de limites y no realiza commit.
"""
from __future__ import absolute_import

import logging
from osv import osv, fields
from tools.translate import _

_logger = logging.getLogger(__name__)


class WizardSiomMinimumTimeUpdate(osv.osv_memory):

    _name = 'wizard.siom.minimum.time.update'
    _description = _('Actualizar tiempos mínimos SIOM (8101) desde OMIE')

    def _puede_actualizar(self, cursor, uid, context=None):
        """Denegar por defecto, incluso en invocaciones RPC directas."""
        if context is None:
            context = {}

        data = self.pool.get('ir.model.data')
        users = self.pool.get('res.users')

        if uid == 1:
            return True

        try:
            model_name, group_id = data.get_object_reference(
                cursor, 1, 'giscedata_omie_api', 'group_giscedata_omie_oferta_u'
            )
        except ValueError:
            return False

        user = users.simple_browse(cursor, uid, uid, context=context)

        return group_id in [group.id for group in user.groups_id]

    def actualizar_desde_omie(self, cursor, uid, ids, context=None):
        if context is None:
            context = {}

        model = self.pool.get('giscedata.omie.siom.minimum.time')

        wizard = self.simple_browse(cursor, uid, ids[0], context=context)

        if not self._puede_actualizar(cursor, uid, context=context):
            raise osv.except_osv(
                'Acceso denegado',
                'Solo el grupo GISCEDATA Omie / Manager puede actualizar 8101.')

        if not ids or len(ids) != 1:
            raise osv.except_osv('Error', _('Seleccione un unico asistente.'))

        if wizard.state != 'init':
            raise osv.except_osv('Error', _('Este asistente ya se ha ejecutado.'))

        _logger.info('Actualizacion manual de SIOM 8101 solicitada por uid=%s', uid)

        # El modelo solo acepta uid=1. No elevar SIN la comprobacion previa.
        result = model.actualizar_tiempos_minimos(cursor, 1, context=context)

        if result['estado'] == 'vacia':
            info = ('OMIE ha respondido correctamente, pero sin filas. '
                    'Se conservan los limites anteriormente almacenados.')
        else:
            info = 'Tiempos minimos recibidos y actualizados correctamente.'

        info += ('\nFilas recibidas: {recibidas}'
                 '\nRegistros nuevos: {nuevas}'
                 '\nRegistros actualizados: {actualizadas}').format(**result)

        vals = {
            'state': 'end',
            'info': info,
            'recibidas': result['recibidas'],
            'nuevas': result['nuevas'],
            'actualizadas': result['actualizadas'],
        }
        self.write(cursor, uid, ids, vals, context=context)

        return True

    _columns = {
        'state': fields.selection([('init', 'Inicial'), ('end', 'Finalizado')],
                                  'Estado', required=True, readonly=True),
        'info': fields.text('Resultado', readonly=True),
        'recibidas': fields.integer('Filas recibidas', readonly=True),
        'nuevas': fields.integer('Nuevas', readonly=True),
        'actualizadas': fields.integer('Actualizadas', readonly=True)
    }

    _defaults = {
        'state': lambda *args: 'init'
    }


WizardSiomMinimumTimeUpdate()
