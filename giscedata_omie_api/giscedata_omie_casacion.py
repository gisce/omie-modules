# -*- coding: utf-8 -*-
from __future__ import absolute_import
from giscedata_omie_api.giscedata_omie_oferta import (
    PERIODO_DIA, TIPO_MERCADO, CLASE_OFERTA, TIPO_NUM_SESION, UNIDAD_MEDIDA)
from giscedata_omie_api.utils import (get_pbf_dict, parse_pbf_reponse, get_phf_dict, parse_phf_reponse,
                                      convert_casation_to_qh)
from omie import ClientOMIE
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

        vals = {'casacion_id': False, 'casacion_descargada': False}

        # Set to False casation for related offers
        for casacion_id in ids:
            oferta_ids = oferta_obj.search(cursor, uid, [('casacion_id', '=', casacion_id)])
            oferta_obj.write(cursor, uid, oferta_ids, vals)

            return super(GiscedataOmieCasacion, self).unlink(cursor, uid, [casacion_id], context=context)

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
            casacion_dict = get_pbf_dict(params)

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

            casation, is_qh = parse_pbf_reponse(res_casacion_dict, params['uni_medida'])

            # Addapt to QH if needed
            if not is_qh:
                cron_wst.log(logging.INFO, msg="Adaptant la cassació a format quart-horari...", status='Running')
                casation = convert_casation_to_qh(casation, params['uni_medida'])

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
            if oferta_data.get('state', 'no_enviada') in ('enviada', 'casacion') or oferta_data.get('sustituida', False):
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
