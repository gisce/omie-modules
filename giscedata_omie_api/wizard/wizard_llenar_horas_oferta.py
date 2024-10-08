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

        oferta_obj = self.pool.get('giscedata.omie.oferta')
        hora_obj = self.pool.get('giscedata.omie.oferta.hora')

        wiz_id = ids[0]
        ctx = context.copy()
        ctx.update({'prefetch': False})
        wiz_brw = self.browse(cursor, uid, wiz_id, context=ctx)
        if context.get('active_ids', False):
            oferta_ids = context.get('active_ids')
            qh_oferta = oferta_obj.read(cursor, uid, oferta_ids[0], ['qh_oferta'], context=context)['qh_oferta']
            rang = 26
            if qh_oferta:
                rang = 101
            if len(oferta_ids) == 1:
                oferta_ids = '({})'.format(oferta_ids[0])
            else:
                oferta_ids = str(tuple(oferta_ids))
            for i in range(1, rang):
                precio = 'precio_' + str(i)
                energia = 'energia_' + str(i)
                retirable = 'es_retirable_' + str(i)
                divisible = 'es_divisible_' + str(i)
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
            for i in range(1, 101):
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

    def get_qh_oferta(self, cursor, uid, context=None):
        if context is None:
            context = {}
        if context.get('active_ids'):
            oferta_obj = self.pool.get('giscedata.omie.oferta')
            qf_oferta = oferta_obj.read(
                cursor, uid, context.get('active_ids')[0], ['qh_oferta'], context=context
            )['qh_oferta']
            return qf_oferta

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
        'energia_26': fields.float("Energía(MWh)", digits=(8, 3), help="Energía de la oferta, sin signo", readonly=True),
        'precio_26': fields.float("Precio(€)", digits=(8, 3)),
        'es_divisible_26': fields.boolean('Es divisible 26'),
        'es_retirable_26': fields.boolean('Es retirable 26'),
        'energia_27': fields.float("Energía(MWh)", digits=(8, 3), help="Energía de la oferta, sin signo", readonly=True),
        'precio_27': fields.float("Precio(€)", digits=(8, 3)),
        'es_divisible_27': fields.boolean('Es divisible 27'),
        'es_retirable_27': fields.boolean('Es retirable 27'),
        'energia_28': fields.float("Energía(MWh)", digits=(8, 3), help="Energía de la oferta, sin signo", readonly=True),
        'precio_28': fields.float("Precio(€)", digits=(8, 3)),
        'es_divisible_28': fields.boolean('Es divisible 28'),
        'es_retirable_28': fields.boolean('Es retirable 28'),
        'energia_29': fields.float("Energía(MWh)", digits=(8, 3), help="Energía de la oferta, sin signo", readonly=True),
        'precio_29': fields.float("Precio(€)", digits=(8, 3)),
        'es_divisible_29': fields.boolean('Es divisible 29'),
        'es_retirable_29': fields.boolean('Es retirable 29'),
        'energia_30': fields.float("Energía(MWh)", digits=(8, 3), help="Energía de la oferta, sin signo", readonly=True),
        'precio_30': fields.float("Precio(€)", digits=(8, 3)),
        'es_divisible_30': fields.boolean('Es divisible 30'),
        'es_retirable_30': fields.boolean('Es retirable 30'),
        'energia_31': fields.float("Energía(MWh)", digits=(8, 3), help="Energía de la oferta, sin signo", readonly=True),
        'precio_31': fields.float("Precio(€)", digits=(8, 3)),
        'es_divisible_31': fields.boolean('Es divisible 31'),
        'es_retirable_31': fields.boolean('Es retirable 31'),
        'energia_32': fields.float("Energía(MWh)", digits=(8, 3), help="Energía de la oferta, sin signo", readonly=True),
        'precio_32': fields.float("Precio(€)", digits=(8, 3)),
        'es_divisible_32': fields.boolean('Es divisible 32'),
        'es_retirable_32': fields.boolean('Es retirable 32'),
        'energia_33': fields.float("Energía(MWh)", digits=(8, 3), help="Energía de la oferta, sin signo", readonly=True),
        'precio_33': fields.float("Precio(€)", digits=(8, 3)),
        'es_divisible_33': fields.boolean('Es divisible 33'),
        'es_retirable_33': fields.boolean('Es retirable 33'),
        'energia_34': fields.float("Energía(MWh)", digits=(8, 3), help="Energía de la oferta, sin signo", readonly=True),
        'precio_34': fields.float("Precio(€)", digits=(8, 3)),
        'es_divisible_34': fields.boolean('Es divisible 34'),
        'es_retirable_34': fields.boolean('Es retirable 34'),
        'energia_35': fields.float("Energía(MWh)", digits=(8, 3), help="Energía de la oferta, sin signo", readonly=True),
        'precio_35': fields.float("Precio(€)", digits=(8, 3)),
        'es_divisible_35': fields.boolean('Es divisible 35'),
        'es_retirable_35': fields.boolean('Es retirable 35'),
        'energia_36': fields.float("Energía(MWh)", digits=(8, 3), help="Energía de la oferta, sin signo", readonly=True),
        'precio_36': fields.float("Precio(€)", digits=(8, 3)),
        'es_divisible_36': fields.boolean('Es divisible 36'),
        'es_retirable_36': fields.boolean('Es retirable 36'),
        'energia_37': fields.float("Energía(MWh)", digits=(8, 3), help="Energía de la oferta, sin signo", readonly=True),
        'precio_37': fields.float("Precio(€)", digits=(8, 3)),
        'es_divisible_37': fields.boolean('Es divisible 37'),
        'es_retirable_37': fields.boolean('Es retirable 37'),
        'energia_38': fields.float("Energía(MWh)", digits=(8, 3), help="Energía de la oferta, sin signo", readonly=True),
        'precio_38': fields.float("Precio(€)", digits=(8, 3)),
        'es_divisible_38': fields.boolean('Es divisible 38'),
        'es_retirable_38': fields.boolean('Es retirable 38'),
        'energia_39': fields.float("Energía(MWh)", digits=(8, 3), help="Energía de la oferta, sin signo", readonly=True),
        'precio_39': fields.float("Precio(€)", digits=(8, 3)),
        'es_divisible_39': fields.boolean('Es divisible 39'),
        'es_retirable_39': fields.boolean('Es retirable 39'),
        'energia_40': fields.float("Energía(MWh)", digits=(8, 3), help="Energía de la oferta, sin signo", readonly=True),
        'precio_40': fields.float("Precio(€)", digits=(8, 3)),
        'es_divisible_40': fields.boolean('Es divisible 40'),
        'es_retirable_40': fields.boolean('Es retirable 40'),
        'energia_41': fields.float("Energía(MWh)", digits=(8, 3), help="Energía de la oferta, sin signo", readonly=True),
        'precio_41': fields.float("Precio(€)", digits=(8, 3)),
        'es_divisible_41': fields.boolean('Es divisible 41'),
        'es_retirable_41': fields.boolean('Es retirable 41'),
        'energia_42': fields.float("Energía(MWh)", digits=(8, 3), help="Energía de la oferta, sin signo", readonly=True),
        'precio_42': fields.float("Precio(€)", digits=(8, 3)),
        'es_divisible_42': fields.boolean('Es divisible 42'),
        'es_retirable_42': fields.boolean('Es retirable 42'),
        'energia_43': fields.float("Energía(MWh)", digits=(8, 3), help="Energía de la oferta, sin signo", readonly=True),
        'precio_43': fields.float("Precio(€)", digits=(8, 3)),
        'es_divisible_43': fields.boolean('Es divisible 43'),
        'es_retirable_43': fields.boolean('Es retirable 43'),
        'energia_44': fields.float("Energía(MWh)", digits=(8, 3), help="Energía de la oferta, sin signo", readonly=True),
        'precio_44': fields.float("Precio(€)", digits=(8, 3)),
        'es_divisible_44': fields.boolean('Es divisible 44'),
        'es_retirable_44': fields.boolean('Es retirable 44'),
        'energia_45': fields.float("Energía(MWh)", digits=(8, 3), help="Energía de la oferta, sin signo", readonly=True),
        'precio_45': fields.float("Precio(€)", digits=(8, 3)),
        'es_divisible_45': fields.boolean('Es divisible 45'),
        'es_retirable_45': fields.boolean('Es retirable 45'),
        'energia_46': fields.float("Energía(MWh)", digits=(8, 3), help="Energía de la oferta, sin signo", readonly=True),
        'precio_46': fields.float("Precio(€)", digits=(8, 3)),
        'es_divisible_46': fields.boolean('Es divisible 46'),
        'es_retirable_46': fields.boolean('Es retirable 46'),
        'energia_47': fields.float("Energía(MWh)", digits=(8, 3), help="Energía de la oferta, sin signo", readonly=True),
        'precio_47': fields.float("Precio(€)", digits=(8, 3)),
        'es_divisible_47': fields.boolean('Es divisible 47'),
        'es_retirable_47': fields.boolean('Es retirable 47'),
        'energia_48': fields.float("Energía(MWh)", digits=(8, 3), help="Energía de la oferta, sin signo", readonly=True),
        'precio_48': fields.float("Precio(€)", digits=(8, 3)),
        'es_divisible_48': fields.boolean('Es divisible 48'),
        'es_retirable_48': fields.boolean('Es retirable 48'),
        'energia_49': fields.float("Energía(MWh)", digits=(8, 3), help="Energía de la oferta, sin signo", readonly=True),
        'precio_49': fields.float("Precio(€)", digits=(8, 3)),
        'es_divisible_49': fields.boolean('Es divisible 49'),
        'es_retirable_49': fields.boolean('Es retirable 49'),
        'energia_50': fields.float("Energía(MWh)", digits=(8, 3), help="Energía de la oferta, sin signo", readonly=True),
        'precio_50': fields.float("Precio(€)", digits=(8, 3)),
        'es_divisible_50': fields.boolean('Es divisible 50'),
        'es_retirable_50': fields.boolean('Es retirable 50'),
        'energia_51': fields.float("Energía(MWh)", digits=(8, 3), help="Energía de la oferta, sin signo", readonly=True),
        'precio_51': fields.float("Precio(€)", digits=(8, 3)),
        'es_divisible_51': fields.boolean('Es divisible 51'),
        'es_retirable_51': fields.boolean('Es retirable 51'),
        'energia_52': fields.float("Energía(MWh)", digits=(8, 3), help="Energía de la oferta, sin signo", readonly=True),
        'precio_52': fields.float("Precio(€)", digits=(8, 3)),
        'es_divisible_52': fields.boolean('Es divisible 52'),
        'es_retirable_52': fields.boolean('Es retirable 52'),
        'energia_53': fields.float("Energía(MWh)", digits=(8, 3), help="Energía de la oferta, sin signo", readonly=True),
        'precio_53': fields.float("Precio(€)", digits=(8, 3)),
        'es_divisible_53': fields.boolean('Es divisible 53'),
        'es_retirable_53': fields.boolean('Es retirable 53'),
        'energia_54': fields.float("Energía(MWh)", digits=(8, 3), help="Energía de la oferta, sin signo", readonly=True),
        'precio_54': fields.float("Precio(€)", digits=(8, 3)),
        'es_divisible_54': fields.boolean('Es divisible 54'),
        'es_retirable_54': fields.boolean('Es retirable 54'),
        'energia_55': fields.float("Energía(MWh)", digits=(8, 3), help="Energía de la oferta, sin signo", readonly=True),
        'precio_55': fields.float("Precio(€)", digits=(8, 3)),
        'es_divisible_55': fields.boolean('Es divisible 55'),
        'es_retirable_55': fields.boolean('Es retirable 55'),
        'energia_56': fields.float("Energía(MWh)", digits=(8, 3), help="Energía de la oferta, sin signo", readonly=True),
        'precio_56': fields.float("Precio(€)", digits=(8, 3)),
        'es_divisible_56': fields.boolean('Es divisible 56'),
        'es_retirable_56': fields.boolean('Es retirable 56'),
        'energia_57': fields.float("Energía(MWh)", digits=(8, 3), help="Energía de la oferta, sin signo", readonly=True),
        'precio_57': fields.float("Precio(€)", digits=(8, 3)),
        'es_divisible_57': fields.boolean('Es divisible 57'),
        'es_retirable_57': fields.boolean('Es retirable 57'),
        'energia_58': fields.float("Energía(MWh)", digits=(8, 3), help="Energía de la oferta, sin signo", readonly=True),
        'precio_58': fields.float("Precio(€)", digits=(8, 3)),
        'es_divisible_58': fields.boolean('Es divisible 58'),
        'es_retirable_58': fields.boolean('Es retirable 58'),
        'energia_59': fields.float("Energía(MWh)", digits=(8, 3), help="Energía de la oferta, sin signo", readonly=True),
        'precio_59': fields.float("Precio(€)", digits=(8, 3)),
        'es_divisible_59': fields.boolean('Es divisible 59'),
        'es_retirable_59': fields.boolean('Es retirable 59'),
        'energia_60': fields.float("Energía(MWh)", digits=(8, 3), help="Energía de la oferta, sin signo", readonly=True),
        'precio_60': fields.float("Precio(€)", digits=(8, 3)),
        'es_divisible_60': fields.boolean('Es divisible 60'),
        'es_retirable_60': fields.boolean('Es retirable 60'),
        'energia_61': fields.float("Energía(MWh)", digits=(8, 3), help="Energía de la oferta, sin signo", readonly=True),
        'precio_61': fields.float("Precio(€)", digits=(8, 3)),
        'es_divisible_61': fields.boolean('Es divisible 61'),
        'es_retirable_61': fields.boolean('Es retirable 61'),
        'energia_62': fields.float("Energía(MWh)", digits=(8, 3), help="Energía de la oferta, sin signo", readonly=True),
        'precio_62': fields.float("Precio(€)", digits=(8, 3)),
        'es_divisible_62': fields.boolean('Es divisible 62'),
        'es_retirable_62': fields.boolean('Es retirable 62'),
        'energia_63': fields.float("Energía(MWh)", digits=(8, 3), help="Energía de la oferta, sin signo", readonly=True),
        'precio_63': fields.float("Precio(€)", digits=(8, 3)),
        'es_divisible_63': fields.boolean('Es divisible 63'),
        'es_retirable_63': fields.boolean('Es retirable 63'),
        'energia_64': fields.float("Energía(MWh)", digits=(8, 3), help="Energía de la oferta, sin signo", readonly=True),
        'precio_64': fields.float("Precio(€)", digits=(8, 3)),
        'es_divisible_64': fields.boolean('Es divisible 64'),
        'es_retirable_64': fields.boolean('Es retirable 64'),
        'energia_65': fields.float("Energía(MWh)", digits=(8, 3), help="Energía de la oferta, sin signo", readonly=True),
        'precio_65': fields.float("Precio(€)", digits=(8, 3)),
        'es_divisible_65': fields.boolean('Es divisible 65'),
        'es_retirable_65': fields.boolean('Es retirable 65'),
        'energia_66': fields.float("Energía(MWh)", digits=(8, 3), help="Energía de la oferta, sin signo", readonly=True),
        'precio_66': fields.float("Precio(€)", digits=(8, 3)),
        'es_divisible_66': fields.boolean('Es divisible 66'),
        'es_retirable_66': fields.boolean('Es retirable 66'),
        'energia_67': fields.float("Energía(MWh)", digits=(8, 3), help="Energía de la oferta, sin signo", readonly=True),
        'precio_67': fields.float("Precio(€)", digits=(8, 3)),
        'es_divisible_67': fields.boolean('Es divisible 67'),
        'es_retirable_67': fields.boolean('Es retirable 67'),
        'energia_68': fields.float("Energía(MWh)", digits=(8, 3), help="Energía de la oferta, sin signo", readonly=True),
        'precio_68': fields.float("Precio(€)", digits=(8, 3)),
        'es_divisible_68': fields.boolean('Es divisible 68'),
        'es_retirable_68': fields.boolean('Es retirable 68'),
        'energia_69': fields.float("Energía(MWh)", digits=(8, 3), help="Energía de la oferta, sin signo", readonly=True),
        'precio_69': fields.float("Precio(€)", digits=(8, 3)),
        'es_divisible_69': fields.boolean('Es divisible 69'),
        'es_retirable_69': fields.boolean('Es retirable 69'),
        'energia_70': fields.float("Energía(MWh)", digits=(8, 3), help="Energía de la oferta, sin signo", readonly=True),
        'precio_70': fields.float("Precio(€)", digits=(8, 3)),
        'es_divisible_70': fields.boolean('Es divisible 70'),
        'es_retirable_70': fields.boolean('Es retirable 70'),
        'energia_71': fields.float("Energía(MWh)", digits=(8, 3), help="Energía de la oferta, sin signo", readonly=True),
        'precio_71': fields.float("Precio(€)", digits=(8, 3)),
        'es_divisible_71': fields.boolean('Es divisible 71'),
        'es_retirable_71': fields.boolean('Es retirable 71'),
        'energia_72': fields.float("Energía(MWh)", digits=(8, 3), help="Energía de la oferta, sin signo", readonly=True),
        'precio_72': fields.float("Precio(€)", digits=(8, 3)),
        'es_divisible_72': fields.boolean('Es divisible 72'),
        'es_retirable_72': fields.boolean('Es retirable 72'),
        'energia_73': fields.float("Energía(MWh)", digits=(8, 3), help="Energía de la oferta, sin signo", readonly=True),
        'precio_73': fields.float("Precio(€)", digits=(8, 3)),
        'es_divisible_73': fields.boolean('Es divisible 73'),
        'es_retirable_73': fields.boolean('Es retirable 73'),
        'energia_74': fields.float("Energía(MWh)", digits=(8, 3), help="Energía de la oferta, sin signo", readonly=True),
        'precio_74': fields.float("Precio(€)", digits=(8, 3)),
        'es_divisible_74': fields.boolean('Es divisible 74'),
        'es_retirable_74': fields.boolean('Es retirable 74'),
        'energia_75': fields.float("Energía(MWh)", digits=(8, 3), help="Energía de la oferta, sin signo", readonly=True),
        'precio_75': fields.float("Precio(€)", digits=(8, 3)),
        'es_divisible_75': fields.boolean('Es divisible 75'),
        'es_retirable_75': fields.boolean('Es retirable 75'),
        'energia_76': fields.float("Energía(MWh)", digits=(8, 3), help="Energía de la oferta, sin signo", readonly=True),
        'precio_76': fields.float("Precio(€)", digits=(8, 3)),
        'es_divisible_76': fields.boolean('Es divisible 76'),
        'es_retirable_76': fields.boolean('Es retirable 76'),
        'energia_77': fields.float("Energía(MWh)", digits=(8, 3), help="Energía de la oferta, sin signo", readonly=True),
        'precio_77': fields.float("Precio(€)", digits=(8, 3)),
        'es_divisible_77': fields.boolean('Es divisible 77'),
        'es_retirable_77': fields.boolean('Es retirable 77'),
        'energia_78': fields.float("Energía(MWh)", digits=(8, 3), help="Energía de la oferta, sin signo", readonly=True),
        'precio_78': fields.float("Precio(€)", digits=(8, 3)),
        'es_divisible_78': fields.boolean('Es divisible 78'),
        'es_retirable_78': fields.boolean('Es retirable 78'),
        'energia_79': fields.float("Energía(MWh)", digits=(8, 3), help="Energía de la oferta, sin signo", readonly=True),
        'precio_79': fields.float("Precio(€)", digits=(8, 3)),
        'es_divisible_79': fields.boolean('Es divisible 79'),
        'es_retirable_79': fields.boolean('Es retirable 79'),
        'energia_80': fields.float("Energía(MWh)", digits=(8, 3), help="Energía de la oferta, sin signo", readonly=True),
        'precio_80': fields.float("Precio(€)", digits=(8, 3)),
        'es_divisible_80': fields.boolean('Es divisible 80'),
        'es_retirable_80': fields.boolean('Es retirable 80'),
        'energia_81': fields.float("Energía(MWh)", digits=(8, 3), help="Energía de la oferta, sin signo", readonly=True),
        'precio_81': fields.float("Precio(€)", digits=(8, 3)),
        'es_divisible_81': fields.boolean('Es divisible 81'),
        'es_retirable_81': fields.boolean('Es retirable 81'),
        'energia_82': fields.float("Energía(MWh)", digits=(8, 3), help="Energía de la oferta, sin signo", readonly=True),
        'precio_82': fields.float("Precio(€)", digits=(8, 3)),
        'es_divisible_82': fields.boolean('Es divisible 82'),
        'es_retirable_82': fields.boolean('Es retirable 82'),
        'energia_83': fields.float("Energía(MWh)", digits=(8, 3), help="Energía de la oferta, sin signo", readonly=True),
        'precio_83': fields.float("Precio(€)", digits=(8, 3)),
        'es_divisible_83': fields.boolean('Es divisible 83'),
        'es_retirable_83': fields.boolean('Es retirable 83'),
        'energia_84': fields.float("Energía(MWh)", digits=(8, 3), help="Energía de la oferta, sin signo", readonly=True),
        'precio_84': fields.float("Precio(€)", digits=(8, 3)),
        'es_divisible_84': fields.boolean('Es divisible 84'),
        'es_retirable_84': fields.boolean('Es retirable 84'),
        'energia_85': fields.float("Energía(MWh)", digits=(8, 3), help="Energía de la oferta, sin signo", readonly=True),
        'precio_85': fields.float("Precio(€)", digits=(8, 3)),
        'es_divisible_85': fields.boolean('Es divisible 85'),
        'es_retirable_85': fields.boolean('Es retirable 85'),
        'energia_86': fields.float("Energía(MWh)", digits=(8, 3), help="Energía de la oferta, sin signo", readonly=True),
        'precio_86': fields.float("Precio(€)", digits=(8, 3)),
        'es_divisible_86': fields.boolean('Es divisible 86'),
        'es_retirable_86': fields.boolean('Es retirable 86'),
        'energia_87': fields.float("Energía(MWh)", digits=(8, 3), help="Energía de la oferta, sin signo", readonly=True),
        'precio_87': fields.float("Precio(€)", digits=(8, 3)),
        'es_divisible_87': fields.boolean('Es divisible 87'),
        'es_retirable_87': fields.boolean('Es retirable 87'),
        'energia_88': fields.float("Energía(MWh)", digits=(8, 3), help="Energía de la oferta, sin signo", readonly=True),
        'precio_88': fields.float("Precio(€)", digits=(8, 3)),
        'es_divisible_88': fields.boolean('Es divisible 88'),
        'es_retirable_88': fields.boolean('Es retirable 88'),
        'energia_89': fields.float("Energía(MWh)", digits=(8, 3), help="Energía de la oferta, sin signo", readonly=True),
        'precio_89': fields.float("Precio(€)", digits=(8, 3)),
        'es_divisible_89': fields.boolean('Es divisible 89'),
        'es_retirable_89': fields.boolean('Es retirable 89'),
        'energia_90': fields.float("Energía(MWh)", digits=(8, 3), help="Energía de la oferta, sin signo", readonly=True),
        'precio_90': fields.float("Precio(€)", digits=(8, 3)),
        'es_divisible_90': fields.boolean('Es divisible 90'),
        'es_retirable_90': fields.boolean('Es retirable 90'),
        'energia_91': fields.float("Energía(MWh)", digits=(8, 3), help="Energía de la oferta, sin signo", readonly=True),
        'precio_91': fields.float("Precio(€)", digits=(8, 3)),
        'es_divisible_91': fields.boolean('Es divisible 91'),
        'es_retirable_91': fields.boolean('Es retirable 91'),
        'energia_92': fields.float("Energía(MWh)", digits=(8, 3), help="Energía de la oferta, sin signo", readonly=True),
        'precio_92': fields.float("Precio(€)", digits=(8, 3)),
        'es_divisible_92': fields.boolean('Es divisible 92'),
        'es_retirable_92': fields.boolean('Es retirable 92'),
        'energia_93': fields.float("Energía(MWh)", digits=(8, 3), help="Energía de la oferta, sin signo", readonly=True),
        'precio_93': fields.float("Precio(€)", digits=(8, 3)),
        'es_divisible_93': fields.boolean('Es divisible 93'),
        'es_retirable_93': fields.boolean('Es retirable 93'),
        'energia_94': fields.float("Energía(MWh)", digits=(8, 3), help="Energía de la oferta, sin signo", readonly=True),
        'precio_94': fields.float("Precio(€)", digits=(8, 3)),
        'es_divisible_94': fields.boolean('Es divisible 94'),
        'es_retirable_94': fields.boolean('Es retirable 94'),
        'energia_95': fields.float("Energía(MWh)", digits=(8, 3), help="Energía de la oferta, sin signo", readonly=True),
        'precio_95': fields.float("Precio(€)", digits=(8, 3)),
        'es_divisible_95': fields.boolean('Es divisible 95'),
        'es_retirable_95': fields.boolean('Es retirable 95'),
        'energia_96': fields.float("Energía(MWh)", digits=(8, 3), help="Energía de la oferta, sin signo", readonly=True),
        'precio_96': fields.float("Precio(€)", digits=(8, 3)),
        'es_divisible_96': fields.boolean('Es divisible 96'),
        'es_retirable_96': fields.boolean('Es retirable 96'),
        'energia_97': fields.float("Energía(MWh)", digits=(8, 3), help="Energía de la oferta, sin signo", readonly=True),
        'precio_97': fields.float("Precio(€)", digits=(8, 3)),
        'es_divisible_97': fields.boolean('Es divisible 97'),
        'es_retirable_97': fields.boolean('Es retirable 97'),
        'energia_98': fields.float("Energía(MWh)", digits=(8, 3), help="Energía de la oferta, sin signo", readonly=True),
        'precio_98': fields.float("Precio(€)", digits=(8, 3)),
        'es_divisible_98': fields.boolean('Es divisible 98'),
        'es_retirable_98': fields.boolean('Es retirable 98'),
        'energia_99': fields.float("Energía(MWh)", digits=(8, 3), help="Energía de la oferta, sin signo", readonly=True),
        'precio_99': fields.float("Precio(€)", digits=(8, 3)),
        'es_divisible_99': fields.boolean('Es divisible 99'),
        'es_retirable_99': fields.boolean('Es retirable 99'),
        'energia_100': fields.float("Energía(MWh)", digits=(8, 3), help="Energía de la oferta, sin signo",readonly=True),
        'precio_100': fields.float("Precio(€)", digits=(8, 3)),
        'es_divisible_100': fields.boolean('Es divisible 100'),
        'es_retirable_100': fields.boolean('Es retirable 100'),
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
        'bloc_creat_26': fields.boolean('Existe hora 26'),
        'bloc_creat_27': fields.boolean('Existe hora 27'),
        'bloc_creat_28': fields.boolean('Existe hora 28'),
        'bloc_creat_29': fields.boolean('Existe hora 29'),
        'bloc_creat_30': fields.boolean('Existe hora 30'),
        'bloc_creat_31': fields.boolean('Existe hora 31'),
        'bloc_creat_32': fields.boolean('Existe hora 32'),
        'bloc_creat_33': fields.boolean('Existe hora 33'),
        'bloc_creat_34': fields.boolean('Existe hora 34'),
        'bloc_creat_35': fields.boolean('Existe hora 35'),
        'bloc_creat_36': fields.boolean('Existe hora 36'),
        'bloc_creat_37': fields.boolean('Existe hora 37'),
        'bloc_creat_38': fields.boolean('Existe hora 38'),
        'bloc_creat_39': fields.boolean('Existe hora 39'),
        'bloc_creat_40': fields.boolean('Existe hora 40'),
        'bloc_creat_41': fields.boolean('Existe hora 41'),
        'bloc_creat_42': fields.boolean('Existe hora 42'),
        'bloc_creat_43': fields.boolean('Existe hora 43'),
        'bloc_creat_44': fields.boolean('Existe hora 44'),
        'bloc_creat_45': fields.boolean('Existe hora 45'),
        'bloc_creat_46': fields.boolean('Existe hora 46'),
        'bloc_creat_47': fields.boolean('Existe hora 47'),
        'bloc_creat_48': fields.boolean('Existe hora 48'),
        'bloc_creat_49': fields.boolean('Existe hora 49'),
        'bloc_creat_50': fields.boolean('Existe hora 50'),
        'bloc_creat_51': fields.boolean('Existe hora 51'),
        'bloc_creat_52': fields.boolean('Existe hora 52'),
        'bloc_creat_53': fields.boolean('Existe hora 53'),
        'bloc_creat_54': fields.boolean('Existe hora 54'),
        'bloc_creat_55': fields.boolean('Existe hora 55'),
        'bloc_creat_56': fields.boolean('Existe hora 56'),
        'bloc_creat_57': fields.boolean('Existe hora 57'),
        'bloc_creat_58': fields.boolean('Existe hora 58'),
        'bloc_creat_59': fields.boolean('Existe hora 59'),
        'bloc_creat_60': fields.boolean('Existe hora 60'),
        'bloc_creat_61': fields.boolean('Existe hora 61'),
        'bloc_creat_62': fields.boolean('Existe hora 62'),
        'bloc_creat_63': fields.boolean('Existe hora 63'),
        'bloc_creat_64': fields.boolean('Existe hora 64'),
        'bloc_creat_65': fields.boolean('Existe hora 65'),
        'bloc_creat_66': fields.boolean('Existe hora 66'),
        'bloc_creat_67': fields.boolean('Existe hora 67'),
        'bloc_creat_68': fields.boolean('Existe hora 68'),
        'bloc_creat_69': fields.boolean('Existe hora 69'),
        'bloc_creat_70': fields.boolean('Existe hora 70'),
        'bloc_creat_71': fields.boolean('Existe hora 71'),
        'bloc_creat_72': fields.boolean('Existe hora 72'),
        'bloc_creat_73': fields.boolean('Existe hora 73'),
        'bloc_creat_74': fields.boolean('Existe hora 74'),
        'bloc_creat_75': fields.boolean('Existe hora 75'),
        'bloc_creat_76': fields.boolean('Existe hora 76'),
        'bloc_creat_77': fields.boolean('Existe hora 77'),
        'bloc_creat_78': fields.boolean('Existe hora 78'),
        'bloc_creat_79': fields.boolean('Existe hora 79'),
        'bloc_creat_80': fields.boolean('Existe hora 80'),
        'bloc_creat_81': fields.boolean('Existe hora 81'),
        'bloc_creat_82': fields.boolean('Existe hora 82'),
        'bloc_creat_83': fields.boolean('Existe hora 83'),
        'bloc_creat_84': fields.boolean('Existe hora 84'),
        'bloc_creat_85': fields.boolean('Existe hora 85'),
        'bloc_creat_86': fields.boolean('Existe hora 86'),
        'bloc_creat_87': fields.boolean('Existe hora 87'),
        'bloc_creat_88': fields.boolean('Existe hora 88'),
        'bloc_creat_89': fields.boolean('Existe hora 89'),
        'bloc_creat_90': fields.boolean('Existe hora 90'),
        'bloc_creat_91': fields.boolean('Existe hora 91'),
        'bloc_creat_92': fields.boolean('Existe hora 92'),
        'bloc_creat_93': fields.boolean('Existe hora 93'),
        'bloc_creat_94': fields.boolean('Existe hora 94'),
        'bloc_creat_95': fields.boolean('Existe hora 95'),
        'bloc_creat_96': fields.boolean('Existe hora 96'),
        'bloc_creat_97': fields.boolean('Existe hora 97'),
        'bloc_creat_98': fields.boolean('Existe hora 98'),
        'bloc_creat_99': fields.boolean('Existe hora 99'),
        'bloc_creat_100': fields.boolean('Existe hora 100'),
        'qh_oferta': fields.boolean('Es cuartohoraria'),
    }

    _defaults = {
        'state': lambda *a: 'init',
        'qh_oferta': get_qh_oferta,
    }


WizardLlenarHorasOferta()
