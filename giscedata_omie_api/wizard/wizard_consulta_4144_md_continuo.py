# -*- coding: utf-8 -*-
from __future__ import absolute_import
from osv import osv, fields
from omie import ClientOMIE
from zeep import helpers
from giscedata_omie_api.giscedata_omie_oferta import SI_NO


class WizardConsultaSesiones(osv.osv_memory):

    _name = 'wizard.consulta.mercado.continuo'
    _description = """Datos de la consulta 4144 de la API de Omie en tiempo real"""

    NUM_RONDA = [
        '1', '2', '3', '4', '5', '6', '7', '8', '9', '10', '11', '12',
        '13', '14', '15', '16', '17', '18', '19', '20', '21', '22', '23', '24'
    ]

    # TODO: Mirar si volem mantenir això de l'estat
    # def consulta_sesiones(self, cursor, uid, ids, context=None):
    #     if context is None:
    #         context = {}
    #
    #     wiz_id = ids[0]
    #     ctx = context.copy()
    #     ctx.update({'prefetch': False})
    #     wiz_brw = self.browse(cursor, uid, wiz_id, context=ctx)
    #
    #     client = ClientOMIE()
    #     result = client.ServicioConsultaMercados()
    #     res_serialized = helpers.serialize_object(result)
    #     res = self.crear_sesion(cursor, uid, wiz_id, res_serialized, context=context)
    #     if res:
    #         wiz_brw.write({'state': 'end'})
    #     else:
    #         wiz_brw.write({'state': 'error'})

    def crear_sesion(self, cursor, uid, wiz_id, sesion_dicc, context=None):


        return True

    _columns = {
        'id_unidad': fields.many2one('giscere.unitat.oferta', 'ID Unidad', size=16),
        'num_fecha': fields.datetime('Fecha de ronda', size=32),
        'num_ronda': fields.selection(NUM_RONDA, 'Número de ronda', size=16),
        'unidad_medida': fields.char('Fecha último mensaje', size=16),
    }

    _defaults = {
        'num_ronda': NUM_RONDA[24],
        'unidad_medida': 'P'
    }


WizardConsultaSesiones()
