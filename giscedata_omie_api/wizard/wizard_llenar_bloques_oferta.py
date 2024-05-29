# -*- coding: utf-8 -*-
from __future__ import absolute_import
from osv import osv, fields

class WizardLlenarBloquesOferta(osv.osv_memory):

    _name = 'wizard.llenar.bloques.oferta'
    _description = """Asistente para llenar los bloques de una oferta"""

    def llenar_bloques_oferta(self, cursor, uid, ids, context=None):
        if context is None:
            context = {}

        bloque_obj = self.pool.get('giscedata.omie.oferta.bloque')

        wiz_id = ids[0]
        ctx = context.copy()
        ctx.update({'prefetch': False})
        wiz_brw = self.browse(cursor, uid, wiz_id, context=ctx)
        if context.get('active_ids', False):
            for i in range(1, 26):
                precio = 'precio_' + str(i)
                energia = 'energia_' + str(i)
                oferta_ids = context.get('active_ids')
                if len(oferta_ids) == 1:
                    oferta_ids = '({})'.format(oferta_ids[0])
                else:
                    oferta_ids = tuple(oferta_ids)
                sql = """
                    SELECT id
                    FROM giscedata_omie_oferta_bloque
                    WHERE
                        per = '{}' AND
                        oferta_id in {}
                """.format(str(i), oferta_ids)
                cursor.execute(sql)
                bloque_ids = [x[0] for x in cursor.fetchall()]
                write_vals = {
                    'div': 'S' if wiz_brw.es_divisible else 'N',
                    'ret': 'S' if wiz_brw.es_retirable else 'N',
                    'ctn': getattr(wiz_brw, energia),
                    'prc': getattr(wiz_brw, precio),
                }
                bloque_obj.write(cursor, uid, bloque_ids, write_vals, context=context)
        wiz_brw.write({'state': 'end'}, context=context)


    _columns = {
        'es_divisible': fields.boolean('Es divisible', help="Se marcará esta opción para todos los bloques"),
        'es_retirable': fields.boolean('Es retirable',  help="Se marcará esta opción para todos los bloques"),
        'energia_1': fields.float("Energía 1", digits=(8, 3), help="Energía de la oferta, sin signo"),
        'precio_1': fields.float("Precio 1", digits=(8, 3)),
        'energia_2': fields.float("Energía 2", digits=(8, 3), help="Energía de la oferta, sin signo"),
        'precio_2': fields.float("Precio 2", digits=(8, 3)),
        'energia_3': fields.float("Energía 3", digits=(8, 3), help="Energía de la oferta, sin signo"),
        'precio_3': fields.float("Precio 3", digits=(8, 3)),
        'energia_4': fields.float("Energía 4", digits=(8, 3), help="Energía de la oferta, sin signo"),
        'precio_4': fields.float("Precio 4", digits=(8, 3)),
        'energia_5': fields.float("Energía 5", digits=(8, 3), help="Energía de la oferta, sin signo"),
        'precio_5': fields.float("Precio 5", digits=(8, 3)),
        'energia_6': fields.float("Energía 6", digits=(8, 3), help="Energía de la oferta, sin signo"),
        'precio_6': fields.float("Precio 6", digits=(8, 3)),
        'energia_7': fields.float("Energía 7", digits=(8, 3), help="Energía de la oferta, sin signo"),
        'precio_7': fields.float("Precio 7", digits=(8, 3)),
        'energia_8': fields.float("Energía 8", digits=(8, 3), help="Energía de la oferta, sin signo"),
        'precio_8': fields.float("Precio 8", digits=(8, 3)),
        'energia_9': fields.float("Energía 9", digits=(8, 3), help="Energía de la oferta, sin signo"),
        'precio_9': fields.float("Precio 9", digits=(8, 3)),
        'energia_10': fields.float("Energía 10", digits=(8, 3), help="Energía de la oferta, sin signo"),
        'precio_10': fields.float("Precio 10", digits=(8, 3)),
        'energia_11': fields.float("Energía 11", digits=(8, 3), help="Energía de la oferta, sin signo"),
        'precio_11': fields.float("Precio 11", digits=(8, 3)),
        'energia_12': fields.float("Energía 12", digits=(8, 3), help="Energía de la oferta, sin signo"),
        'precio_12': fields.float("Precio 12", digits=(8, 3)),
        'energia_13': fields.float("Energía 13", digits=(8, 3), help="Energía de la oferta, sin signo"),
        'precio_13': fields.float("Precio 13", digits=(8, 3)),
        'energia_14': fields.float("Energía 14", digits=(8, 3), help="Energía de la oferta, sin signo"),
        'precio_14': fields.float("Precio 14", digits=(8, 3)),
        'energia_15': fields.float("Energía 15", digits=(8, 3), help="Energía de la oferta, sin signo"),
        'precio_15': fields.float("Precio 15", digits=(8, 3)),
        'energia_16': fields.float("Energía 16", digits=(8, 3), help="Energía de la oferta, sin signo"),
        'precio_16': fields.float("Precio 16", digits=(8, 3)),
        'energia_17': fields.float("Energía 17", digits=(8, 3), help="Energía de la oferta, sin signo"),
        'precio_17': fields.float("Precio 17", digits=(8, 3)),
        'energia_18': fields.float("Energía 18", digits=(8, 3), help="Energía de la oferta, sin signo"),
        'precio_18': fields.float("Precio 18", digits=(8, 3)),
        'energia_19': fields.float("Energía 19", digits=(8, 3), help="Energía de la oferta, sin signo"),
        'precio_19': fields.float("Precio 19", digits=(8, 3)),
        'energia_20': fields.float("Energía 20", digits=(8, 3), help="Energía de la oferta, sin signo"),
        'precio_20': fields.float("Precio 20", digits=(8, 3)),
        'energia_21': fields.float("Energía 21", digits=(8, 3), help="Energía de la oferta, sin signo"),
        'precio_21': fields.float("Precio 21", digits=(8, 3)),
        'energia_22': fields.float("Energía 22", digits=(8, 3), help="Energía de la oferta, sin signo"),
        'precio_22': fields.float("Precio 22", digits=(8, 3)),
        'energia_23': fields.float("Energía 23", digits=(8, 3), help="Energía de la oferta, sin signo"),
        'precio_23': fields.float("Precio 23", digits=(8, 3)),
        'energia_24': fields.float("Energía 24", digits=(8, 3), help="Energía de la oferta, sin signo"),
        'precio_24': fields.float("Precio 24", digits=(8, 3)),
        'energia_25': fields.float("Energía 25", digits=(8, 3), help="Energía de la oferta, sin signo"),
        'precio_25': fields.float("Precio 25", digits=(8, 3)),
        'state': fields.selection([('init', 'init'), ('end', 'end')], 'Estat'),
    }

    _defaults = {
        'state': lambda *a: 'init',
    }


WizardLlenarBloquesOferta()
