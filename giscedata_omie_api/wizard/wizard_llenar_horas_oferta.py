# -*- coding: utf-8 -*-
from __future__ import absolute_import
from osv import osv, fields
from tools.translate import _


class WizardLlenarHorasOferta(osv.osv_memory):

    _name = 'wizard.llenar.horas.oferta'
    _description = """Asistente para llenar los horas de una oferta"""

    def llenar_horas_oferta(self, cursor, uid, ids, context=None):
        if context is None:
            context = {}

        hora_obj = self.pool.get('giscedata.omie.oferta.hora')

        wiz_id = ids[0]
        ctx = context.copy()
        ctx.update({'prefetch': False})
        wiz_brw = self.browse(cursor, uid, wiz_id, context=ctx)
        if context.get('active_ids', False):
            for i in range(1, 26):
                precio = 'precio_' + str(i)
                energia = 'energia_' + str(i)
                retirable = 'es_retirable_' + str(i)
                divisible = 'es_divisible_' + str(i)
                oferta_ids = context.get('active_ids')
                if len(oferta_ids) == 1:
                    oferta_ids = '({})'.format(oferta_ids[0])
                else:
                    oferta_ids = str(tuple(oferta_ids))
                sql = """
                    SELECT id
                    FROM giscedata_omie_oferta_hora
                    WHERE
                        per = '{}' AND
                        oferta_id in {}
                """.format(str(i), oferta_ids)
                cursor.execute(sql)
                hora_ids = [x[0] for x in cursor.fetchall()]
                if getattr(wiz_brw, retirable):
                    es_retirable = 'S'
                else:
                    es_retirable = 'N'
                if getattr(wiz_brw, divisible):
                    es_divisible = 'S'
                else:
                    es_divisible = 'N'
                write_vals = {
                    'div': es_divisible,
                    'ret': es_retirable,
                    'ctn': getattr(wiz_brw, energia),
                    'prc': getattr(wiz_brw, precio),
                }
                hora_obj.write(cursor, uid, hora_ids, write_vals, context=context)
        wiz_brw.write({'state': 'end'}, context=context)

    def default_get(self, cursor, uid, fields, context=None):
        if context is None:
            context = {}
        res = super(WizardLlenarHorasOferta, self).default_get(cursor, uid, fields, context=context)
        oferta_obj = self.pool.get('giscedata.omie.oferta')
        hora_obj = self.pool.get('giscedata.omie.oferta.hora')

        for active_id in context.get('active_ids', []):
            oferta_vals = oferta_obj.read(cursor, uid, active_id, ['hora_ids', 'clase_oferta', 'state'],
                                          context=context)

            # No permitir modificar ofertas ya enviadas a OMIE
            if oferta_vals.get('state', 'no_enviada') != 'no_enviada':
                raise osv.except_osv('Error', _('No es posible editar una oferta ya enviada a OMIE.'))

            # Posem tots els valors dels blocs a 0 i False
            for i in range(1, 26):
                name_field_energia = 'energia_{}'.format(i)
                name_field_preu = 'precio_{}'.format(i)
                ret_name = 'es_retirable_{}'.format(i)
                div_name = 'es_divisible_{}'.format(i)
                creat_name = 'bloc_creat_{}'.format(i)
                res[name_field_energia] = 0
                res[name_field_preu] = 0
                res[ret_name] = True
                res[div_name] = False
                res[creat_name] = False

            # Posem els valors dels blocs que s'han creat realment
            hora_ids = oferta_vals.get('hora_ids', [])
            for hora_id in hora_ids:
                hora_vals = hora_obj.read(cursor, uid, hora_id, ['per', 'ctn', 'prc', 'div', 'ret'], context=context)
                name_field_energia = 'energia_{}'.format(hora_vals['per'])
                name_field_preu = 'precio_{}'.format(hora_vals['per'])
                ret_name = 'es_retirable_{}'.format(hora_vals['per'])
                div_name = 'es_divisible_{}'.format(hora_vals['per'])
                creat_name = 'bloc_creat_{}'.format(hora_vals['per'])
                res[name_field_energia] = hora_vals['ctn']
                res[name_field_preu] = hora_vals['prc']
                if hora_vals['div'] == 'S':
                    res[div_name] = True
                else:
                    res[div_name] = False
                if hora_vals['ret'] == 'S':
                    res[ret_name] = True
                else:
                    res[ret_name] = False
                res[creat_name] = True

        return res

    _columns = {
        'energia_1': fields.float("Energía(MWh)", digits=(8, 3), help="Energía de la oferta, sin signo", readonly=True),
        'precio_1': fields.float("Precio(€)", digits=(8, 3)),
        'es_divisible_1': fields.boolean('Es divisible 1'),
        'es_retirable_1': fields.boolean('Es retirable 1'),
        'energia_2': fields.float("Energía(MWh)", digits=(8, 3), help="Energía de la oferta, sin signo", readonly=True),
        'precio_2': fields.float("Precio(€)", digits=(8, 3)),
        'es_divisible_2': fields.boolean('Es divisible 2'),
        'es_retirable_2': fields.boolean('Es retirable 2'),
        'energia_3': fields.float("Energía(MWh)", digits=(8, 3), help="Energía de la oferta, sin signo", readonly=True),
        'precio_3': fields.float("Precio(€)", digits=(8, 3)),
        'es_divisible_3': fields.boolean('Es divisible 3'),
        'es_retirable_3': fields.boolean('Es retirable 3'),
        'energia_4': fields.float("Energía(MWh)", digits=(8, 3), help="Energía de la oferta, sin signo", readonly=True),
        'precio_4': fields.float("Precio(€)", digits=(8, 3)),
        'es_divisible_4': fields.boolean('Es divisible 4'),
        'es_retirable_4': fields.boolean('Es retirable 4'),
        'energia_5': fields.float("Energía(MWh)", digits=(8, 3), help="Energía de la oferta, sin signo", readonly=True),
        'precio_5': fields.float("Precio(€)", digits=(8, 3)),
        'es_divisible_5': fields.boolean('Es divisible 5'),
        'es_retirable_5': fields.boolean('Es retirable 5'),
        'energia_6': fields.float("Energía(MWh)", digits=(8, 3), help="Energía de la oferta, sin signo", readonly=True),
        'precio_6': fields.float("Precio(€)", digits=(8, 3)),
        'es_divisible_6': fields.boolean('Es divisible 6'),
        'es_retirable_6': fields.boolean('Es retirable 6'),
        'energia_7': fields.float("Energía(MWh)", digits=(8, 3), help="Energía de la oferta, sin signo", readonly=True),
        'precio_7': fields.float("Precio(€)", digits=(8, 3)),
        'es_divisible_7': fields.boolean('Es divisible 7'),
        'es_retirable_7': fields.boolean('Es retirable 7'),
        'energia_8': fields.float("Energía(MWh)", digits=(8, 3), help="Energía de la oferta, sin signo", readonly=True),
        'precio_8': fields.float("Precio(€)", digits=(8, 3)),
        'es_divisible_8': fields.boolean('Es divisible 8'),
        'es_retirable_8': fields.boolean('Es retirable 8'),
        'energia_9': fields.float("Energía(MWh)", digits=(8, 3), help="Energía de la oferta, sin signo", readonly=True),
        'precio_9': fields.float("Precio(€)", digits=(8, 3)),
        'es_divisible_9': fields.boolean('Es divisible 9'),
        'es_retirable_9': fields.boolean('Es retirable 9'),
        'energia_10': fields.float("Energía(MWh)", digits=(8, 3), help="Energía de la oferta, sin signo", readonly=True),
        'precio_10': fields.float("Precio(€)", digits=(8, 3)),
        'es_divisible_10': fields.boolean('Es divisible 10'),
        'es_retirable_10': fields.boolean('Es retirable 10'),
        'energia_11': fields.float("Energía(MWh)", digits=(8, 3), help="Energía de la oferta, sin signo", readonly=True),
        'precio_11': fields.float("Precio(€)", digits=(8, 3)),
        'es_divisible_11': fields.boolean('Es divisible 11'),
        'es_retirable_11': fields.boolean('Es retirable 11'),
        'energia_12': fields.float("Energía(MWh)", digits=(8, 3), help="Energía de la oferta, sin signo", readonly=True),
        'precio_12': fields.float("Precio(€)", digits=(8, 3)),
        'es_divisible_12': fields.boolean('Es divisible 12'),
        'es_retirable_12': fields.boolean('Es retirable 12'),
        'energia_13': fields.float("Energía(MWh)", digits=(8, 3), help="Energía de la oferta, sin signo", readonly=True),
        'precio_13': fields.float("Precio(€)", digits=(8, 3)),
        'es_divisible_13': fields.boolean('Es divisible 13'),
        'es_retirable_13': fields.boolean('Es retirable 13'),
        'energia_14': fields.float("Energía(MWh)", digits=(8, 3), help="Energía de la oferta, sin signo", readonly=True),
        'precio_14': fields.float("Precio(€)", digits=(8, 3)),
        'es_divisible_14': fields.boolean('Es divisible 14'),
        'es_retirable_14': fields.boolean('Es retirable 14'),
        'energia_15': fields.float("Energía(MWh)", digits=(8, 3), help="Energía de la oferta, sin signo", readonly=True),
        'precio_15': fields.float("Precio(€)", digits=(8, 3)),
        'es_divisible_15': fields.boolean('Es divisible 15'),
        'es_retirable_15': fields.boolean('Es retirable 15'),
        'energia_16': fields.float("Energía(MWh)", digits=(8, 3), help="Energía de la oferta, sin signo", readonly=True),
        'precio_16': fields.float("Precio(€)", digits=(8, 3)),
        'es_divisible_16': fields.boolean('Es divisible 16'),
        'es_retirable_16': fields.boolean('Es retirable 16'),
        'energia_17': fields.float("Energía(MWh)", digits=(8, 3), help="Energía de la oferta, sin signo", readonly=True),
        'precio_17': fields.float("Precio(€)", digits=(8, 3)),
        'es_divisible_17': fields.boolean('Es divisible 17'),
        'es_retirable_17': fields.boolean('Es retirable 17'),
        'energia_18': fields.float("Energía(MWh)", digits=(8, 3), help="Energía de la oferta, sin signo", readonly=True),
        'precio_18': fields.float("Precio(€)", digits=(8, 3)),
        'es_divisible_18': fields.boolean('Es divisible 18'),
        'es_retirable_18': fields.boolean('Es retirable 18'),
        'energia_19': fields.float("Energía(MWh)", digits=(8, 3), help="Energía de la oferta, sin signo", readonly=True),
        'precio_19': fields.float("Precio(€)", digits=(8, 3)),
        'es_divisible_19': fields.boolean('Es divisible 19'),
        'es_retirable_19': fields.boolean('Es retirable 19'),
        'energia_20': fields.float("Energía(MWh)", digits=(8, 3), help="Energía de la oferta, sin signo", readonly=True),
        'precio_20': fields.float("Precio(€)", digits=(8, 3)),
        'es_divisible_20': fields.boolean('Es divisible 20'),
        'es_retirable_20': fields.boolean('Es retirable 20'),
        'energia_21': fields.float("Energía(MWh)", digits=(8, 3), help="Energía de la oferta, sin signo", readonly=True),
        'precio_21': fields.float("Precio(€)", digits=(8, 3)),
        'es_divisible_21': fields.boolean('Es divisible 21'),
        'es_retirable_21': fields.boolean('Es retirable 21'),
        'energia_22': fields.float("Energía(MWh)", digits=(8, 3), help="Energía de la oferta, sin signo", readonly=True),
        'precio_22': fields.float("Precio(€)", digits=(8, 3)),
        'es_divisible_22': fields.boolean('Es divisible 22'),
        'es_retirable_22': fields.boolean('Es retirable 22'),
        'energia_23': fields.float("Energía(MWh)", digits=(8, 3), help="Energía de la oferta, sin signo", readonly=True),
        'precio_23': fields.float("Precio(€)", digits=(8, 3)),
        'es_divisible_23': fields.boolean('Es divisible 23'),
        'es_retirable_23': fields.boolean('Es retirable 23'),
        'energia_24': fields.float("Energía(MWh)", digits=(8, 3), help="Energía de la oferta, sin signo", readonly=True),
        'precio_24': fields.float("Precio(€)", digits=(8, 3)),
        'es_divisible_24': fields.boolean('Es divisible 24'),
        'es_retirable_24': fields.boolean('Es retirable 24'),
        'energia_25': fields.float("Energía(MWh)", digits=(8, 3), help="Energía de la oferta, sin signo", readonly=True),
        'precio_25': fields.float("Precio(€)", digits=(8, 3)),
        'es_divisible_25': fields.boolean('Es divisible 25'),
        'es_retirable_25': fields.boolean('Es retirable 25'),
        'state': fields.selection([('init', 'init'), ('end', 'end')], 'Estat'),
        'bloc_creat_1': fields.boolean('Existe hora 1'),
        'bloc_creat_2': fields.boolean('Existe hora 2'),
        'bloc_creat_3': fields.boolean('Existe hora 3'),
        'bloc_creat_4': fields.boolean('Existe hora 4'),
        'bloc_creat_5': fields.boolean('Existe hora 5'),
        'bloc_creat_6': fields.boolean('Existe hora 6'),
        'bloc_creat_7': fields.boolean('Existe hora 7'),
        'bloc_creat_8': fields.boolean('Existe hora 8'),
        'bloc_creat_9': fields.boolean('Existe hora 9'),
        'bloc_creat_10': fields.boolean('Existe hora 10'),
        'bloc_creat_11': fields.boolean('Existe hora 11'),
        'bloc_creat_12': fields.boolean('Existe hora 12'),
        'bloc_creat_13': fields.boolean('Existe hora 13'),
        'bloc_creat_14': fields.boolean('Existe hora 14'),
        'bloc_creat_15': fields.boolean('Existe hora 15'),
        'bloc_creat_16': fields.boolean('Existe hora 16'),
        'bloc_creat_17': fields.boolean('Existe hora 17'),
        'bloc_creat_18': fields.boolean('Existe hora 18'),
        'bloc_creat_19': fields.boolean('Existe hora 19'),
        'bloc_creat_20': fields.boolean('Existe hora 20'),
        'bloc_creat_21': fields.boolean('Existe hora 21'),
        'bloc_creat_22': fields.boolean('Existe hora 22'),
        'bloc_creat_23': fields.boolean('Existe hora 23'),
        'bloc_creat_24': fields.boolean('Existe hora 24'),
        'bloc_creat_25': fields.boolean('Existe hora 25'),
    }

    _defaults = {
        'state': lambda *a: 'init',
    }


WizardLlenarHorasOferta()
