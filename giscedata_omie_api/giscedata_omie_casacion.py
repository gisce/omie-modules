# -*- coding: utf-8 -*-
from __future__ import absolute_import
import os
from omie import ClientOMIE
from giscedata_omie_api.giscedata_omie_oferta import (
    PERIODO_DIA, TIPO_MERCADO, CLASE_OFERTA, TIPO_NUM_SESION, UNIDAD_MEDIDA)
from giscedata_omie_api.utils import get_pbf_dict, parse_pbf_reponse, get_phf_dict, parse_phf_reponse, get_phfc_dict, parse_phfc_reponse
from osv import osv, fields
from zeep import helpers
from tools.service_utils import WebServiceTracker
import logging

from tools.translate import _


class GiscedataOmieCasacion(osv.osv):

    _name = 'giscedata.omie.casacion'
    _description = 'Representa la casación de una oferta de OMIE.'

    def unlink(self, cursor, uid, ids, context=None):
        """
        Remove link between unlinked casations and existing offers
        :param cursor: OpenERP DB Cursor
        :param uid: OpenERP User ID
        :param ids: Active IDs
        :param context: OpenERP Current Context
        :return:
        """
        if context is None:
            context = {}

        oferta_obj = self.pool.get('giscedata.omie.oferta')

        # Set to False casation for related offers
        oferta_ids = oferta_obj.search(cursor, uid, [('casacion_id', 'in', ids)])
        oferta_obj.write(cursor, uid, oferta_ids, {'casacion_id': False, 'casacion_descargada': False})

        return super(GiscedataOmieCasacion, self).unlink(cursor, uid, ids, context=context)

    def get_casation_by_session(self, cursor, uid, params, context=None):
        """
        Retrieves casation through OMIE API and store data and associate to offers
        :param cursor: OpenERP DB Cursor
        :param uid: OpenERP User ID
        :param params: dict
        :param context: OpenERP Current Context
        :return: boolean
        """
        if context is None:
            context = {}

        oferta_obj = self.pool.get('giscedata.omie.oferta')
        hora_obj = self.pool.get('giscedata.omie.casacion.hora')

        with WebServiceTracker(
                uid=uid, obj='giscedata.omie.casacion', method='get_casation_by_session', logger_name='openerp.omie'
        ) as cron_wst:

            # Prepare API client
            cron_wst.log(logging.INFO,
                         msg="Obtenint casació des d'OMIE per la UOF {} i la data {}...".format(
                             params['id_unidad'], params['fecha_sesion']
                         ), status='Running'
            )
            client = ClientOMIE()

            # Get params dict for PBF request
            if params['num_sesion'] is False:
                casacion_dict = get_pbf_dict(params)
            else:
                casacion_dict = get_phf_dict(params)

            try:
                # Get casation for session throuhg OMIE API
                res_casacion_zeep = client.ServicioEjecucionConsultaEncolumnada(MensajeEjecucionConsulta=casacion_dict)

            except Exception as e:
                cron_wst.log(logging.ERROR, msg="No s'ha pogut obtenir la cassació des d'OMIE.", status='Failed')
                raise osv.except_osv('Error:', e)

            # Parse OMIE reponse
            cron_wst.log(logging.INFO, msg="Resposta obtinguda. Comprovant si hi ha errors...", status='Running')
            res_casacion_dict = helpers.serialize_object(res_casacion_zeep)

            # Check errors
            if res_casacion_dict.get('Respuesta', []):
                codigo_respuesta = res_casacion_dict['Respuesta'][0]['CodigoRespuesta']['v']
                if 'NO-DISPONIBLE' in codigo_respuesta:
                    cron_wst.log(logging.ERROR, msg="La cassació no es troba disponible.", status='Failed')
                    texto_respuesta = res_casacion_dict['Respuesta'][0]['TextoRespuesta'][0]
                    raise osv.except_osv('Error', texto_respuesta)

            # Parse OMIE reponse and check if is QH
            cron_wst.log(logging.INFO, msg="No hi ha hagut errors. Adaptant el format de la resposta...",
                         status='Running')

            if params['num_sesion'] is False:
                casation = parse_pbf_reponse(res_casacion_dict, params['uni_medida'])
            else:
                casation = parse_phf_reponse(res_casacion_dict, params['uni_medida'])

            # Preventive delete of casation with same date, type, session, class and measure
            search_params = [('id_unidad', '=', params['id_unidad']),
                             ('tipo_mercado', '=', params['tipo_mercado']),
                             ('num_sesion', '=', params['num_sesion']),
                             ('fecha_sesion', '=', params['fecha_sesion']),
                             ('clase_oferta', '=', params['clase_oferta']),
                             ('uni_medida', '=', params['uni_medida'])]
            casation_ids = self.search(cursor, uid, search_params, context=context)

            if casation_ids:
                cron_wst.log(logging.INFO, msg="Eliminant cassacions descarregades prèviament...", status='Running')
                self.unlink(cursor, uid, casation_ids)

            # Create casation data
            cron_wst.log(logging.INFO, msg="Creant cassació...", status='Running')
            casation_name = '{}_{}_{}'.format(params['id_unidad'], params['tipo_mercado'], params['fecha_sesion'])
            casation_vals = {
                'id_unidad': params['id_unidad'],
                'tipo_mercado': params['tipo_mercado'],
                'num_sesion': params['num_sesion'],
                'fecha_sesion': params['fecha_sesion'],
                'clase_oferta': params['clase_oferta'],
                'uni_medida': params['uni_medida'],
                'name': casation_name
            }
            casation_id = self.create(cursor, uid, casation_vals)

            # Associate casation data to offers for that season
            hores = []
            for period in casation:
                period_vals = {
                    'num': period['num'],
                    'per': period['per'],
                    'ctn': period['ctn'],
                    'desc': period['desc'],
                    'casacion_id': casation_id
                }

                hora_id = hora_obj.create(cursor, uid, period_vals)
                hores.append(hora_id)

            if casation_id:
                cron_wst.log(logging.INFO, msg="Associant cassació a les ofertes corresponents...", status='Running')
                oferta_ids = oferta_obj.search(cursor, uid, search_params, context=context)
                if oferta_ids:
                    vals = {
                        'casacion_descargada': True,
                        'casacion_id': casation_id
                    }
                    oferta_obj.write(cursor, uid, oferta_ids, vals)

                cron_wst.log(logging.INFO, msg="Cassació descarregada i associada a les ofertes.", status='Succeed')
                return True

            else:
                cron_wst.log(logging.ERROR, msg="No s'ha pogut descarregar i desar la cassació.", status='Failed')
                return False

    def _get_total_energia(self, cursor, uid, ids, field_name, arg, context=None):
        """

        :param cursor: OpenERP DB Cursor
        :param uid: OpenERP User ID
        :param ids: Active IDs
        :param field_name: not used
        :param arg: not used
        :param context: OpenERP Current Context
        :return: dict
        """
        if context is None:
            context = {}

        if not isinstance(ids, (list, tuple)):
            ids = [ids]

        res = {}
        for casacion in ids:
            cursor.execute("SELECT SUM(ctn) FROM giscedata_omie_casacion_hora WHERE casacion_id = {}".format(casacion))
            energia = cursor.fetchone()[0] or 0.0
            res[casacion] = energia
        return res

    _columns = {
        'name': fields.char('Descripción', size=32, required=True),
        'tipo_mercado': fields.selection(
            TIPO_MERCADO, "Tipo de Mercado", help="MD: Mercado Diario, MI: Mercado Intradiario",
            required=True, readonly=True
        ),
        'num_sesion': fields.selection(TIPO_NUM_SESION, "Sesión MI", readonly=True,
                                       help="""
                                            Indica el número de sesión de Mercado Intradiario Europeo (Intraday Auction)\n
                                            * IDA1: Abierto a las 14:00 del día D+1\n
                                            * IDA2: Abierto a las 21:00 del día D+1\n
                                            * IDA3: Abierto a las 09:00 del día D\n
                                            """),
        'fecha_sesion': fields.date("Fecha Sesión", help=_("Fecha del día a ofertar"),
                                    required=True, readonly=True),
        'clase_oferta': fields.selection(CLASE_OFERTA, "Clase de Oferta", help=_("C: Compra, V: Venta"),
                                         required=True, readonly=True),
        'hora_ids': fields.one2many('giscedata.omie.casacion.hora', 'casacion_id',
                                    "Horas de la casación", ondelete='cascade',
                                    readonly=True),
        'uni_medida': fields.selection(UNIDAD_MEDIDA, 'Unidad de Medida',
                                       readonly=True,
                                       help="Determina si la medida de la oferta es de Energía o de Potencia."),
        'id_unidad': fields.char("ID Unidad", size=16, help="Código de unidad ofertante o física.",
                                 required=True, readonly=True),
        'total_energia': fields.function(_get_total_energia, method=True, type="float", string="Medida total",
                                         readonly=True)
    }
    _order = "fecha_sesion desc"


GiscedataOmieCasacion()


class GiscedataOmieCasacionHora(osv.osv):

    _name = 'giscedata.omie.casacion.hora'
    _description = 'Representa una hora de la casación de una oferta de OMIE.'

    _columns = {
        'num': fields.integer('Hora del Día'),
        'per': fields.selection(PERIODO_DIA, 'Periodo horario del día', required=True, readonly=True,
                                help=_('Seleccionar el periodo del día para el que quiere hacer la oferta')),
        'ctn': fields.float('Medida de la Oferta', digits=(8, 3), readonly=True,
                            help=_('Medida de la oferta, sin signo')),
        'desc': fields.char('Descripción', size=16, readonly=True),
        'casacion_id': fields.many2one('giscedata.omie.casacion', 'Casación',
                                       readonly=True, ondelete='cascade'),
    }


GiscedataOmieCasacionHora()


class GiscedataOmieCasacionContinua(osv.osv):

    _name = 'giscedata.omie.casacion.continua'
    _description = 'Modelo de la consulta 4144 de OMIE.'

    def get_phfc_casation(self, cursor, uid, ids, context=None):
        """
        Retrieves casation through OMIE API and store data
        :param cursor: OpenERP DB Cursor
        :param uid: OpenERP User ID
        :param ids: List of oferta IDs
        :param context: OpenERP Current Context
        :return: boolean
        """
        if context is None:
            context = {}

        read_params = [
            'fecha_ronda', 'num_ronda', 'id_unidad',
            'uni_medida', 'periodo', 'descripcion', 'medida_total'
        ]

        sessions = {}
        for id in ids:
            data = self.read(cursor, uid, id, read_params, context=context)
            if not data:
                continue

            key = (
                data['id_unidad'],
                data['fecha_ronda'],
                data['num_ronda'],
                data['uni_medida'],
                data['periodo'],
                data['descripcion'],
                data['medida_total']
            )

            if key not in sessions:
                sessions[key] = data

        for session in sessions.values():
            params = {
                'id_unidad': session['id_unidad'][0] if isinstance(session['id_unidad'], tuple) else session['id_unidad'],
                'fecha_ronda': session['fecha_ronda'],
                'num_ronda': session['num_ronda'],
                'uni_medida': session['uni_medida'],
                'periodo': session['periodo'],
                'descripcion': session['descripcion'],
                'medida_total': session['medida_total']
            }
            self.get_phfc_casation_from_params(cursor, uid, params, context=context)


    def get_phfc_casation_from_params(self, cursor, uid, params, context=None):
        """
        Aïlla la lògica de recuperació de cassació donat un dict de paràmetres.
        """
        if context is None:
            context = {}

        # TODO: Treure les rutes del CRT/KEY i deixar la crida sense paràmetres
        client = ClientOMIE(crt_path='/home/jtrull/Documentos/somre.crt', crt_key='/home/jtrull/Documentos/somre.key')

        casacion_dict = get_phfc_dict(params)

        with WebServiceTracker(
                uid=uid, obj='giscedata.omie.casacion.continua',
                method='get_phfc_casation_from_params',
                logger_name='openerp.omie'
        ) as cron_wst:

            cron_wst.log(logging.INFO,
                         msg="Obtenint casació contínua (Sessió 24) des d'OMIE per la UOF {} i la data {}...".format(
                             params['id_unidad'], params['fecha_ronda']
                         ), status='Running')

            try:
                res = client.ServicioEjecucionConsultaEncolumnada(
                    MensajeEjecucionConsulta=casacion_dict)
                print(res)
            except Exception as e:
                cron_wst.log(logging.ERROR, msg="No s'ha pogut obtenir la cassació.", status='Failed')
                raise osv.except_osv('Error:', e)

            res_dict = helpers.serialize_object(res)

            if res_dict.get('Respuesta', []):
                codi = res_dict['Respuesta'][0]['CodigoRespuesta']['v']
                if 'NO-DISPONIBLE' in codi:
                    msg = res_dict['Respuesta'][0]['TextoRespuesta'][0]
                    cron_wst.log(logging.ERROR, msg="Cassació no disponible.", status='Failed')
                    raise osv.except_osv('Error', msg)

            # Eliminar cassacions anteriors
            casation_ids = self.search(cursor, uid, [
                ('id_unidad', '=', params['id_unidad']),
                ('fecha_ronda', '=', params['fecha_ronda']),
                ('num_ronda', '=', params['num_ronda']),
                ('periodo', '=', params['periodo']),
                ('descripcion', '=', params['descripcion']),
                ('uni_medida', '=', params['uni_medida']),
                ('medida_total', '=', params['medida_total']),
            ], context=context)

            if casation_ids:
                self.unlink(cursor, uid, casation_ids)

            cas_vals = {
                'id_unidad': params['id_unidad'],
                'fecha_ronda': params['fecha_ronda'],
                'num_ronda': params['num_ronda'],
                'periodo': params['periodo'],
                'descripcion': params['descripcion'],
                'uni_medida': params['uni_medida'],
                'medida_total': params['medida_total']
            }

            return self.create(cursor, uid, cas_vals, context=context)

    _columns = {
        'id_unidad': fields.char("ID Unidad", size=16, required=True, readonly=True),
        'fecha_ronda': fields.date("Fecha Ronda", size=16, required=True, readonly=True),
        'num_ronda': fields.integer("Número de Ronda", size=16, required=True, readonly=True),
        'periodo': fields.integer("Periodo horario del día", size=16, readonly=True),
        'descripcion': fields.char("Descripción periodo", size=16, readonly=True),
        'uni_medida': fields.selection(UNIDAD_MEDIDA, 'Unidad de Medida', size=16, required=True, readonly=True),
        'medida_total': fields.float('Medida total', size=16, readonly=True)
    }
    _order = "fecha_sesion desc"


GiscedataOmieCasacionContinua()


class GiscedataOmieOfertaExtend(osv.osv):

    _name = 'giscedata.omie.oferta'
    _inherit = 'giscedata.omie.oferta'

    def get_casation(self, cursor, uid, ids, context=None):
        """

        :param cursor: OpenERP DB Cursor
        :param uid: OpenERP User ID
        :param ids: Active IDs
        :param context: OpenERP Current Context
        :return:
        """
        if context is None:
            context = {}

        casation_obj = self.pool.get('giscedata.omie.casacion')

        read_params = ['fecha_sesion', 'clase_oferta', 'tipo_mercado', 'num_sesion',
                       'id_oferta', 'id_unidad', 'cod_min_unidad', 'area_unidad', 'tipo_unidad', 'uni_medida',
                       'state', 'qh_oferta', 'sustituida']

        sessions = {}
        for oferta_id in ids:
            oferta_data = self.read(cursor, uid, oferta_id, read_params, context=context)

            # Skip not published or replaced offers
            if oferta_data.get('state', 'no_enviada') not in ('enviada', 'casacion') or oferta_data.get('sustituida', False):
                continue

            key = (oferta_data['fecha_sesion'],
                   oferta_data['tipo_mercado'],
                   oferta_data['num_sesion'],
                   oferta_data['clase_oferta'],
                   oferta_data['uni_medida'])
            if key not in sessions:
                sessions.update({key: oferta_data})

        # Get casation for each session only once
        for key in sessions:
            casation_obj.get_casation_by_session(cursor, uid, sessions[key], context=context)

    _columns = {
        # Cassation
        'casacion_descargada': fields.boolean('Casación descargada', readonly=True),
        'casacion_id': fields.many2one('giscedata.omie.casacion', 'Casación en OMIE', readonly=True),
    }

    _defaults = {
        'casacion_descargada': lambda *a: False
    }

GiscedataOmieOfertaExtend()
