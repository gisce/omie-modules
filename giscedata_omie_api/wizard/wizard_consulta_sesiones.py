# -*- coding: utf-8 -*-
from __future__ import absolute_import
from giscedata_omie_api.giscedata_omie_oferta import SI_NO
from osv import osv, fields
from omie import ClientOMIE
from zeep import helpers
from tools.translate import _


class WizardConsultaSesiones(osv.osv_memory):

    _name = 'wizard.consulta.sesiones'
    _description = _("""Este servicio permite consultar la fecha y hora oficial del Mercado""")

    def consulta_sesiones(self, cursor, uid, ids, context=None):
        if context is None:
            context = {}

        control = self.pool.get('giscedata.omie.siom.service.execution')

        wiz_id = ids[0]
        ctx = context.copy()
        ctx.update({'prefetch': False})
        wiz_brw = self.simple_browse(cursor, uid, wiz_id, context=ctx)

        client = ClientOMIE()

        result = control.ejecutar_servicio(
            cursor, uid, 'ServicioConsultaMercados', lambda: client.ServicioConsultaMercados()
        )

        res_serialized = helpers.serialize_object(result)

        res = self.crear_sesion(cursor, uid, wiz_id, res_serialized, context=context)

        if res:
            wiz_brw.write({'state': 'end'})
        else:
            wiz_brw.write({'state': 'error'})

    def crear_sesion(self, cursor, uid, wiz_id, sesion_dicc, context=None):
        if context is None:
            context = {}

        create_vals = {}
        men_dicc = sesion_dicc.get('Men')
        if men_dicc:
            create_vals.update(
                {
                    'num_mensajes': men_dicc.get('num', False),
                    'fecha_ult_mensaje': men_dicc.get('fUlt').strftime("%Y-%m-%d") if men_dicc.get('fUlt') else False
                }
            )
        md_dicc = sesion_dicc.get('MD')
        if md_dicc:
            rec_md_dicc = md_dicc.get('Rec')
            if rec_md_dicc:
                create_vals.update(
                    {
                        'md_recl': True,
                        'md_recl_abiertas': 'S' if rec_md_dicc.get('a', False) else 'N',
                        'md_per_casacion_abierto': 'S' if rec_md_dicc.get('pCas', False) else 'N',
                        'md_per_recl_abierto': 'S' if rec_md_dicc.get('pOfe', False) else 'N',
                        'md_fecha_cierre_recl': rec_md_dicc.get('fhC').strftime("%Y-%m-%d %H:%M:%s")[:19] if rec_md_dicc.get('fhC') else False,
                        'md_num_sesion_recl': rec_md_dicc.get('nC', False),
                    }
                )
            ses_md_dicc = md_dicc.get('Ses')
            if ses_md_dicc:
                act_md = ses_md_dicc.get('Act')
                if act_md:
                    create_vals.update(
                        {
                            'md_ses_act': True,
                            'md_fecha_sesion_act': act_md.get('f').strftime("%Y-%m-%d") if act_md.get('f') else False,
                            'md_numero_casacion': act_md.get('n', False),
                            'md_fecha_cierre_act': act_md.get('fhC').strftime("%Y-%m-%d %H:%M:%s")[:19] if act_md.get('fhC') else False,
                        }
                    )
                ult_md = ses_md_dicc.get('Ult')
                if ult_md:
                    create_vals.update(
                        {
                            'md_ses_ult': True,
                            'md_fecha_ult_sesion_casada': ult_md.get('f').strftime("%Y-%m-%d") if ult_md.get('f') else False,
                        }
                    )
        mi_dicc = sesion_dicc.get('MI')
        if mi_dicc:
            rec_mi_dicc = mi_dicc.get('Rec')
            if rec_mi_dicc:
                create_vals.update(
                    {
                        'mi_recl': True,
                        'mi_recl_abiertas': 'S' if rec_mi_dicc.get('a', False) else 'N',
                        'mi_per_casacion_abierto': 'S' if rec_mi_dicc.get('pCas', False) else 'N',
                        'mi_per_recl_abierto': 'S' if rec_mi_dicc.get('pOfe', False) else 'N',
                        'mi_fecha_cierre_recl': rec_mi_dicc.get('fhC').strftime("%Y-%m-%d %H:%M:%s")[:19] if rec_mi_dicc.get('fhC') else False,
                        'mi_num_sesion_recl': rec_mi_dicc.get('nC', False),
                    }
                )
            ses_mi_dicc = mi_dicc.get('Ses')
            if ses_mi_dicc:
                act_mi = ses_mi_dicc.get('Act')
                if act_mi:
                    create_vals.update(
                        {
                            'mi_ses_act': True,
                            'mi_fecha_sesion_act': act_mi.get('f').strftime("%Y-%m-%d") if act_mi.get('f') else False,
                            'mi_numero_casacion': act_mi.get('n', False),
                            'mi_fecha_apertura_act': act_mi.get('fhAp').strftime("%Y-%m-%d")if act_mi.get('fhAp') else False,
                            'mi_hora_cierre_act': act_mi.get('hCi', False),
                        }
                    )
                ini_mi = ses_mi_dicc.get('Ini')
                if ini_mi:
                    create_vals.update(
                        {
                            'mi_ses_ini': True,
                            'mi_fecha_sesion_ini': ini_mi.get('f').strftime("%Y-%m-%d %H:%M:%s")[:19] if ini_mi.get('f') else False,
                            'mi_hora_inicio_ini': ini_mi.get('h', False),
                            'mi_hora_efectiva_ini': ini_mi.get('hEf', False),
                        }
                    )
                fin_mi = ses_mi_dicc.get('Fin')
                if fin_mi:
                    create_vals.update(
                        {
                            'mi_ses_fin': True,
                            'mi_fecha_sesion_fin': fin_mi.get('f').strftime("%Y-%m-%d %H:%M:%s")[:19] if fin_mi.get('f') else False,
                            'mi_hora_inicio_fin': fin_mi.get('h', False),
                            'mi_hora_efectiva_fin': fin_mi.get('hEf', False),
                        }
                    )
                ult_mi = ses_mi_dicc.get('Ult')
                if ult_mi:
                    create_vals.update(
                        {
                            'mi_ses_ult': True,
                            'mi_fecha_sesion_ult': ult_mi.get('f').strftime("%Y-%m-%d") if ult_mi.get('f') else False,
                            'mi_num_sesion_ult': ult_mi.get('n', False),
                        }
                    )

        self.write(cursor, uid, [wiz_id], create_vals, context=context)

        return True

    _columns = {
        'state': fields.selection([('init', 'init'), ('end', 'end'), ('error', 'error')], 'Estat'),
        'sesion_id': fields.many2one('giscedata.omie.sesion', 'Sesión'),
        'num_mensajes': fields.char('Número de mensajes', size=32),
        'fecha_ult_mensaje': fields.char('Fecha último mensaje', size=32),
        # MD
        # Info Reclamaciones MD
        'md_recl': fields.selection(SI_NO, 'Reclamaciones'),
        'md_recl_abiertas': fields.selection(SI_NO, 'Reclamaciones abiertas '),
        'md_per_casacion_abierto': fields.selection(SI_NO, 'Periodo de casación abierto '),
        'md_per_recl_abierto': fields.selection(SI_NO, 'Periodo de reclamaciones abierto '),
        'md_fecha_cierre_recl': fields.char('Fecha y hora de cierre del periodo de reclamaciones', size=32),
        'md_num_sesion_recl': fields.char('Número de sesión de periodo de reclamaciones', size=32),
        # Info Sesiones MD
        # Act
        'md_ses_act': fields.selection(SI_NO, 'Sesión Actual'),
        'md_fecha_sesion_act': fields.char('Fecha de la sesión actual', size=32),
        'md_numero_casacion': fields.char('Número de casación', size=32),
        'md_fecha_cierre_act': fields.char('Fecha y hora de cierre de la sesión actual', size=32),
        # Ult
        'md_ses_ult': fields.selection(SI_NO, 'Última Sesión'),
        'md_fecha_ult_sesion_casada': fields.char('Fecha de la última sesión casada', size=32),
        # MI
        # Info Reclamaciones MI
        'mi_recl': fields.selection(SI_NO, 'Reclamaciones'),
        'mi_recl_abiertas': fields.selection(SI_NO, 'Reclamaciones abiertas'),
        'mi_per_casacion_abierto': fields.selection(SI_NO, 'Periodo de casación abierto'),
        'mi_per_recl_abierto': fields.selection(SI_NO, 'Periodo de reclamaciones abierto'),
        'mi_fecha_cierre_recl': fields.char('Fecha y hora de cierre del periodo de reclamaciones', size=32),
        'mi_num_sesion_recl': fields.char('Número de sesión de periodo de reclamaciones', size=32),
        # Info Sesiones MI
        # Act
        'mi_ses_act': fields.selection(SI_NO, 'Sesión Actual'),
        'mi_fecha_sesion_act': fields.char('Fecha de la sesión actual', size=32),
        'mi_numero_casacion': fields.char('Número de sesión', size=32),
        'mi_fecha_apertura_act': fields.char('Fecha de apertura de la sesión actual', size=32),
        'mi_hora_cierre_act': fields.char('Hora de cierre de la sesión actual', size=16),
        # Ini
        'mi_ses_ini': fields.selection(SI_NO, 'Sesión Inicial'),
        'mi_fecha_sesion_ini': fields.char('Fecha y hora de inicio del horizonte de la sesión', size=32),
        'mi_hora_inicio_ini': fields.char('Hora de inicio del horizonte de la sesión', size=32),
        'mi_hora_efectiva_ini': fields.char('Hora efectiva de inicio del horizonte de la sesión', size=32),
        # Fin
        'mi_ses_fin': fields.selection(SI_NO, 'Sesión Final'),
        'mi_fecha_sesion_fin': fields.char('Fecha y hora de fin del horizonte de la sesión', size=32),
        'mi_hora_inicio_fin': fields.char('Hora de fin del horizonte de la sesión', size=32),
        'mi_hora_efectiva_fin': fields.char('Hora efectiva de fin del horizonte de la sesión', size=32),
        # Ult
        'mi_ses_ult': fields.selection(SI_NO, 'Última Sesión'),
        'mi_fecha_sesion_ult': fields.char('Fecha de la última sesión casada', size=32),
        'mi_num_sesion_ult': fields.char('Número de última sesión casada', size=32),
    }

    _defaults = {
        'state': lambda *a: 'init',
    }


WizardConsultaSesiones()
