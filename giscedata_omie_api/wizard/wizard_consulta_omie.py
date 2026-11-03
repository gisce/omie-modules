# -*- coding: utf-8 -*-
from __future__ import absolute_import
from datetime import datetime, timedelta
from giscedata_omie_api.giscedata_omie_oferta import UNIDAD_MEDIDA
from giscedata_omie_api.utils import _OMIE_INDICATORS, _NUM_RONDA
from osv import osv, fields
from tools.translate import _


class WizardConsultaOMIE(osv.osv_memory):

    _name = 'wizard.consulta.omie'
    _description = _("""Datos de la consulta 4144 de la API de Omie en tiempo real""")

    def consultar_en_omie(self, cursor, uid, ids, context=None):
        if context is None:
            context = {}

        wiz_id = ids[0]
        ctx = context.copy()
        wiz = self.simple_browse(cursor, uid, wiz_id, context=ctx)

        if wiz.indicador_omie == 'phfc':
            self.get_phfc_casation(cursor, uid, ids, context=context)
        elif wiz.indicador_omie == 'pbc':
            self.get_pbc_casation(cursor, uid, ids, context=context)

        return True

    def get_phfc_casation(self, cursor, uid, ids, context=None):
        """
        Retrieves and stores PHFC values from OMIE if available
        :param cursor: OpenERP DB Cursor
        :param uid:  OpenERP User ID
        :param ids: OpenERP Active IDs
        :param context: OpenERP Current Context
        :return: boolean
        """
        if context is None:
            context = {}

        casation_obj = self.pool.get('giscedata.omie.casacion.continua')

        wiz_id = ids[0]
        ctx = context.copy()
        wiz = self.simple_browse(cursor, uid, wiz_id, context=ctx)

        # Do not allow future dates
        if wiz.fecha_ronda > datetime.today().strftime('%Y-%m-%d'):
            raise osv.except_osv('Error', _('La fecha de ronda no puede ser posterior al día en curso.'))

        # Read params from wizard
        params = {
            'id_unidad': wiz.id_unidad.name,
            'fecha_ronda': wiz.fecha_ronda,
            'num_ronda': wiz.num_ronda[0],
            'uni_medida': wiz.uni_medida
        }

        # Retrieve casation from OMIE
        res = casation_obj.get_phfc_casation(cursor, uid, params, context=context)

        # Update wizard state
        if res:
            wiz_vals = {'state': 'end',
                        'info': _('Casación descargada correctamente.')}
        else:
            wiz_vals = {'state': 'error',
                        'info': _('No se ha podido descargar la casación. Revise los ajustes del asistente.')}

        wiz.write(wiz_vals)

    def get_pbc_casation(self, cursor, uid, ids, context=None):
        """
        Retrieves and stores PBC values from OMIE if available
        :param cursor: OpenERP DB Cursor
        :param uid:  OpenERP User ID
        :param ids: OpenERP Active IDs
        :param context: OpenERP Current Context
        :return: boolean
        """
        if context is None:
            context = {}

        casation_obj = self.pool.get('giscedata.omie.programa.casacion')

        wiz_id = ids[0]
        ctx = context.copy()
        wiz = self.simple_browse(cursor, uid, wiz_id, context=ctx)

        # Do not allow future dates
        if wiz.fecha_ronda > (datetime.today() + timedelta(days=1)).strftime('%Y-%m-%d'):
            raise osv.except_osv('Error', _('La fecha de ronda no puede ser posterior a mañana.'))

        # Read params from wizard
        params = {
            'id_unidad': wiz.id_unidad.name,
            'fecha_ronda': wiz.fecha_ronda,
            'uni_medida': wiz.uni_medida
        }

        # Retrieve casation from OMIE
        res = casation_obj.get_pbc_casation(cursor, uid, params, context=context)

        # Update wizard state
        if res:
            wiz_vals = {'state': 'end',
                        'info': _('Programa de casación descargado correctamente.')}
        else:
            wiz_vals = {'state': 'error',
                        'info': _('No se ha podido descargar el programa de casación. Revise los ajustes del asistente.')}

        wiz.write(wiz_vals)



    _columns = {
        'indicador_omie': fields.selection(_OMIE_INDICATORS, 'Indicador de OMIE', required=True),
        'id_unidad': fields.many2one('giscere.unitat.oferta', 'Unidad de Oferta', required=True),
        'fecha_ronda': fields.date('Fecha de ronda', required=True),
        'num_ronda': fields.selection(_NUM_RONDA, 'Número de ronda', required=True),
        'uni_medida': fields.selection(UNIDAD_MEDIDA, 'Unidad de Medida', required=True),
        'state': fields.selection([('init', 'init'), ('error', 'error'), ('end', 'end')],
                                  'Estado', readonly=True),
        'info': fields.text('Información', readonly=True)
    }

    _defaults = {
        'indicador_omie': lambda *a: 'pbc',
        'fecha_ronda': lambda *a: datetime.now().strftime('%Y-%m-%d'),
        'num_ronda': lambda *a: _NUM_RONDA[-1],
        'uni_medida': 'P',
        'state': lambda *a: 'init'
    }


WizardConsultaOMIE()
