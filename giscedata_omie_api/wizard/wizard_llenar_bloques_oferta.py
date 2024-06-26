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

    def default_get(self, cursor, uid, fields, context=None):
        if context is None:
            context = {}
        res = super(WizardLlenarBloquesOferta, self).default_get(cursor, uid, fields, context=context)
        oferta_obj = self.pool.get('giscedata.omie.oferta')
        bloque_obj = self.pool.get('giscedata.omie.oferta.bloque')
        for active_id in context.get('active_ids', []):
            bloque_ids = oferta_obj.read(cursor, uid, active_id, ['bloque_ids'], context=context)['bloque_ids']
            for bloque_id in bloque_ids:
                bloque_vals = bloque_obj.read(cursor, uid, bloque_id, ['num', 'ctn'], context=context)
                name_field = 'energia_{}'.format(bloque_vals['num'])
                res[name_field] = bloque_vals['ctn']
        return res

    _columns = {
        'es_divisible': fields.boolean('Es divisible', help="Se marcará esta opción para todos los bloques"),
        'es_retirable': fields.boolean('Es retirable',  help="Se marcará esta opción para todos los bloques"),
        'energia_1': fields.float("Energía(MWh)", digits=(8, 3), help="Energía de la oferta, sin signo", readonly=True),
        'precio_1': fields.float("Precio(€)", digits=(8, 3)),
        'energia_2': fields.float("Energía(MWh)", digits=(8, 3), help="Energía de la oferta, sin signo", readonly=True),
        'precio_2': fields.float("Precio(€)", digits=(8, 3)),
        'energia_3': fields.float("Energía(MWh)", digits=(8, 3), help="Energía de la oferta, sin signo", readonly=True),
        'precio_3': fields.float("Precio(€)", digits=(8, 3)),
        'energia_4': fields.float("Energía(MWh)", digits=(8, 3), help="Energía de la oferta, sin signo", readonly=True),
        'precio_4': fields.float("Precio(€)", digits=(8, 3)),
        'energia_5': fields.float("Energía(MWh)", digits=(8, 3), help="Energía de la oferta, sin signo", readonly=True),
        'precio_5': fields.float("Precio(€)", digits=(8, 3)),
        'energia_6': fields.float("Energía(MWh)", digits=(8, 3), help="Energía de la oferta, sin signo", readonly=True),
        'precio_6': fields.float("Precio(€)", digits=(8, 3)),
        'energia_7': fields.float("Energía(MWh)", digits=(8, 3), help="Energía de la oferta, sin signo", readonly=True),
        'precio_7': fields.float("Precio(€)", digits=(8, 3)),
        'energia_8': fields.float("Energía(MWh)", digits=(8, 3), help="Energía de la oferta, sin signo", readonly=True),
        'precio_8': fields.float("Precio(€)", digits=(8, 3)),
        'energia_9': fields.float("Energía(MWh)", digits=(8, 3), help="Energía de la oferta, sin signo", readonly=True),
        'precio_9': fields.float("Precio(€)", digits=(8, 3)),
        'energia_10': fields.float("Energía(MWh)", digits=(8, 3), help="Energía de la oferta, sin signo", readonly=True),
        'precio_10': fields.float("Precio(€)", digits=(8, 3)),
        'energia_11': fields.float("Energía(MWh)", digits=(8, 3), help="Energía de la oferta, sin signo", readonly=True),
        'precio_11': fields.float("Precio(€)", digits=(8, 3)),
        'energia_12': fields.float("Energía(MWh)", digits=(8, 3), help="Energía de la oferta, sin signo", readonly=True),
        'precio_12': fields.float("Precio(€)", digits=(8, 3)),
        'energia_13': fields.float("Energía(MWh)", digits=(8, 3), help="Energía de la oferta, sin signo", readonly=True),
        'precio_13': fields.float("Precio(€)", digits=(8, 3)),
        'energia_14': fields.float("Energía(MWh)", digits=(8, 3), help="Energía de la oferta, sin signo", readonly=True),
        'precio_14': fields.float("Precio(€)", digits=(8, 3)),
        'energia_15': fields.float("Energía(MWh)", digits=(8, 3), help="Energía de la oferta, sin signo", readonly=True),
        'precio_15': fields.float("Precio(€)", digits=(8, 3)),
        'energia_16': fields.float("Energía(MWh)", digits=(8, 3), help="Energía de la oferta, sin signo", readonly=True),
        'precio_16': fields.float("Precio(€)", digits=(8, 3)),
        'energia_17': fields.float("Energía(MWh)", digits=(8, 3), help="Energía de la oferta, sin signo", readonly=True),
        'precio_17': fields.float("Precio(€)", digits=(8, 3)),
        'energia_18': fields.float("Energía(MWh)", digits=(8, 3), help="Energía de la oferta, sin signo", readonly=True),
        'precio_18': fields.float("Precio(€)", digits=(8, 3)),
        'energia_19': fields.float("Energía(MWh)", digits=(8, 3), help="Energía de la oferta, sin signo", readonly=True),
        'precio_19': fields.float("Precio(€)", digits=(8, 3)),
        'energia_20': fields.float("Energía(MWh)", digits=(8, 3), help="Energía de la oferta, sin signo", readonly=True),
        'precio_20': fields.float("Precio(€)", digits=(8, 3)),
        'energia_21': fields.float("Energía(MWh)", digits=(8, 3), help="Energía de la oferta, sin signo", readonly=True),
        'precio_21': fields.float("Precio(€)", digits=(8, 3)),
        'energia_22': fields.float("Energía(MWh)", digits=(8, 3), help="Energía de la oferta, sin signo", readonly=True),
        'precio_22': fields.float("Precio(€)", digits=(8, 3)),
        'energia_23': fields.float("Energía(MWh)", digits=(8, 3), help="Energía de la oferta, sin signo", readonly=True),
        'precio_23': fields.float("Precio(€)", digits=(8, 3)),
        'energia_24': fields.float("Energía(MWh)", digits=(8, 3), help="Energía de la oferta, sin signo", readonly=True),
        'precio_24': fields.float("Precio(€)", digits=(8, 3)),
        'energia_25': fields.float("Energía(MWh)", digits=(8, 3), help="Energía de la oferta, sin signo", readonly=True),
        'precio_25': fields.float("Precio(€)", digits=(8, 3)),
        'state': fields.selection([('init', 'init'), ('end', 'end')], 'Estat'),
    }

    _defaults = {
        'state': lambda *a: 'init',
    }


WizardLlenarBloquesOferta()
