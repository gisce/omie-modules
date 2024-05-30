# -*- coding: utf-8 -*-
from __future__ import absolute_import
from osv import osv, fields
from omie import ClientOMIE
from zeep import helpers


class WizardConsultaFechaHora(osv.osv_memory):

    _name = 'wizard.consulta.fecha.hora'
    _description = """Este servicio permite consultar la fecha y hora oficial del Mercado"""

    def consulta_fecha_hora(self, cursor, uid, ids, context=None):
        if context is None:
            context = {}

        wiz_id = ids[0]
        ctx = context.copy()
        ctx.update({'prefetch': False})
        wiz_brw = self.browse(cursor, uid, wiz_id, context=ctx)

        client = ClientOMIE(
            crt_path='/home/aorellana/proyectos/OMIE/omie-base/omie/data/omie.cert',
            crt_key='/home/aorellana/proyectos/OMIE/omie-base/omie/data/omie.key'
        )
        result = client.ServicioConsultaFechaHora()
        res_serialized = helpers.serialize_object(result)
        fecha_hora = res_serialized.get('v', False)
        if fecha_hora:
            fecha_hora = fecha_hora.strftime("%Y-%m-%d %H:%M:%s")[:19]
            wiz_brw.write({'fecha_hora': fecha_hora, 'state': 'end'})
        else:
            wiz_brw.write({'state': 'error'})

    _columns = {
        'state': fields.selection([('init', 'init'), ('end', 'end'), ('error', 'error')], 'Estat'),
        'fecha_hora': fields.char('Fecha y Hora Oficial del Mercado', size=32, readonly=True)
    }

    _defaults = {
        'state': lambda *a: 'init',
    }


WizardConsultaFechaHora()
