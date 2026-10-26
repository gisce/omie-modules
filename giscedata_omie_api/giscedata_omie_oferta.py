# -*- coding: utf-8 -*-
from __future__ import absolute_import
from giscedata_omie_api.utils import (AREA_UNIDAD_SELECTION, TIPO_UNIDAD_SELECTION, TIPO_MERCADO, TIPO_NUM_SESION,
                                      SI_NO, CLASE_OFERTA, UNIDAD_ENERGIA, UNIDAD_POTENCIA, UNIDAD_MONETARIA,
                                      UNIDAD_PRECIOS, UNIDAD_MEDIDA, PERIODO_DIA, ESTADO_OFERTA, TIPO_NECESIDAD)
from osv import osv, fields
from omie import ClientOMIE
from datetime import datetime
from zeep import helpers
from tools.translate import _


class GiscedataOmieOferta(osv.osv):

    _name = 'giscedata.omie.oferta'
    _rec_name = 'id_oferta'
    _description = """Ofertas de OMIE"""

    _order = 'fecha_sesion desc, fecha_mensaje desc, id_unidad asc'

    def create(self, cursor, uid, vals, context=None):
        if context is None:
            context = {}

        hora_obj = self.pool.get('giscedata.omie.oferta.hora')

        oferta_id = super(osv.osv, self).create(cursor, uid, vals, context=context)
        write_vals = {
            'id_mensaje': oferta_id,
            'id_oferta': 'OF' + str(oferta_id)
        }

        self.write(cursor, uid, [oferta_id], write_vals, context=context)

        if not context.get('no_crear_horas', True):
            hora_ids = []
            rang = 26
            if vals.get('qh_oferta'):
                rang = 101
            for i in range(1, rang):
                create_vals = {
                    'num': i,
                    'div': 'N',
                    'ret': 'N',
                    'per': str(i),
                    'oferta_id': oferta_id,
                }
                hora_id = hora_obj.create(cursor, uid, create_vals, context=context)
                hora_ids.append(hora_id)

        return oferta_id

    def _get_origen_selection(self, cursor, uid, context=None):
        if context is None:
            context = {}
        return []

    _columns = {
        'id_mensaje': fields.char(
            "ID Mensaje", size=64,
            help=_("Código que identifica un elemento de forma única dentro del documento."), readonly=True
        ),
        'ver_mensaje': fields.integer(
            "Número Versión Mensaje", help=_("Número de versión de un mensaje"), required=False
        ),
        'fecha_mensaje': fields.date(
            "Fecha Mensaje",
            help=_("Fecha y hora de generación de los datos para el mensaje (no de envío del mensaje en sí)"),
            required=False, readonly=True
        ),
        'id_remitente': fields.char(
            "ID Remitente", size=16,
            help=_("Tipo que identifica un remitente, como código de agente, código EIC, etc"), required=True
        ),
        # Oferta
        'id_oferta': fields.char(
            "ID Oferta", size=16,
            help=_("Identificativo de la oferta dentro del fichero, "
                   "definido por quien  envía el fichero (único por mensaje)"), readonly=True
        ),
        # Unidad
        # v
        'id_unidad': fields.char(
            "ID Unidad", size=16, help=_("Código de unidad ofertante o física."), required=True
        ),
        'cod_min_unidad': fields.char(
            "Código del Ministerio", size=50, help=_("Código del Ministerio"), required=False
        ),
        'area_unidad': fields.selection(
            AREA_UNIDAD_SELECTION, "Área de Unidad",
            help=_("1: España, "
                   "2: Portugal, "
                   "3: Europa - Interconex Francia, "
                   "4: Andorra, "
                   "5: Africa - Interconex Marruecos"),
            required=True
        ),
        'tipo_unidad': fields.selection(
            TIPO_UNIDAD_SELECTION, "Tipo de Unidad",
            help=_("UO: Unidad Ofertante, UF: Unidad Física, RE: Régimen Especial, "
                 "CP: Unidad de Contratación a Plazo, UP: Unidad de programación"),
            required=True
        ),
        # Validez
        'tipo_mercado': fields.selection(
            TIPO_MERCADO, "Tipo de Mercado", help=_("MD: Mercado Diario, MI: Mercado Intradiario"), required=True
        ),
        'num_sesion': fields.selection(TIPO_NUM_SESION,"Sesión MI",
                                       help=_("""
                                            Indica el número de sesión de Mercado Intradiario Europeo (Intraday Auction)\n
                                            * IDA1: Abierto a las 14:00 del día D+1\n
                                            * IDA2: Abierto a las 21:00 del día D+1\n
                                            * IDA3: Abierto a las 09:00 del día D\n
                                            """)
                                       ),
        'valida': fields.boolean(
            'Valida', readonly=True,
            help=_("La oferta será valida si no ha sido sustituida y "
                   "se ha enviado procesado y aceptado por parte de OMIE.")
        ),
        'sustituida': fields.boolean(
            'Sustituida', readonly=True,
            help=_("La oferta será sustituida cuando se haya mandado una oferta con el "
                   "mismo código de oferta y una versión superior. Si la oferta no se "
                   "procesa o se acepta, por parte de OMIE, también será marcada como "
                   "sustituida.")
        ),
        # Sesion
        'fecha_sesion': fields.date(
            "Fecha Sesión", help=_("Fecha del día que queremos ofertar"), required=True
        ),
        'ind_defecto': fields.selection(
            SI_NO, "Oferta por Defecto",
            help=_("Indica si la Oferta es por Defecto o Normal. "
                 "('S' o 'Y' indican que la oferta es por defecto. 'N' indica que es normal"),
            required=True
        ),
        #'tipo_casacion' SIEMPRE VALE 1
        'clase_oferta': fields.selection(CLASE_OFERTA, "Clase de Oferta",
                                         help=_("C: Compra, V: Venta"), required=True),
        # CondTec
        #Gradiente
        'grad_parada': fields.float("Gradiente de Parada", digits=(6, 1), help=_("Gradiente de Parada")),
        'grad_arranque': fields.float("Gradiente de Arranque", digits=(6, 1), help=_("Gradiente de Arranque")),
        'grad_bajada': fields.float("Gradiente de Bajada", digits=(6, 1), help=_("Gradiente de Bajada")),
        'grad_subida': fields.float("Gradiente de Subida", digits=(6, 1), help=_("Gradiente de Subida")),
        'uni_energia': fields.selection(UNIDAD_ENERGIA, "Unidad de Energía", help="MWh/kWh"),
        'uni_potencia': fields.selection(UNIDAD_POTENCIA, "Unidad de Potencia", help="MW/kW"),
        'uni_monetaria': fields.selection(UNIDAD_MONETARIA, "Unidad Monetaria", help="cEURO/EURO"),
        'uni_precio': fields.selection(
            UNIDAD_PRECIOS, 'Unidad de Precio', help="cEURO/kWh, cEURO/MWh, EURO/MWh",
        ),
        'uni_medida': fields.selection(
            UNIDAD_MEDIDA, 'Unidad de Medida',
            help=_("Determina si la medida de la oferta es de Energía o de Potencia."),
        ),
        #'uni_gradiente' SIEMPRE VALE 'MW/Min'
        'comentario_oferta': fields.char(
            "Comentario de la Oferta", size=30, help=_("Comentario de la oferta"), required=False
        ),
        'state': fields.selection(
            ESTADO_OFERTA, 'Estado Envio',
            help="Enviada/No Enviada", readonly=True
        ),
        # RESPUESTA
        'id_mensaje_respuesta': fields.char(
            'Mensaje Petición', help=_("Identificación del mensaje (libre para el creador del mensaje)"), size=64,
            readonly=True),
        'fecha_mensaje_respuesta': fields.char(
            "Fecha Petición", size=32,
            help=_("Fecha y hora de generación de los datos para el mensaje (no de envío del mensaje en sí)"),
            readonly=True
        ),
        'id_remitente_respuesta': fields.char(
            "ID Remitente", size=16,
            help=_("Código del Agente que envía la respuesta (OMEL)"), readonly=True
        ),
        'id_remitente_origen': fields.char(
            'ID Remitente Origen', size=16,
            help=_("Código del Agente que envió el mensaje"), readonly=True
        ),
        # Respuesta
        'codigo_respuesta': fields.char(
            'Código Respuesta', size=16, help=_("Código de la respuesta"), readonly=True
        ),
        'texto_respuesta': fields.text(
            'Texto Respuesta', help=_("Textos descriptivos de la respuesta"), readonly=True
        ),
        # ResumenOfertas
        'num_ofertas_procesadas': fields.char(
            'Núm. Ofertas Procesadas', size=16, help=_("Número total de ofertas procesadas"), readonly=True
        ),
        'num_ofertas_correctas': fields.char(
            'Núm. Ofertas Correctas', size=16, help=_("Número total de ofertas correctas"), readonly=True
        ),
        'origen': fields.reference('Origen', selection=_get_origen_selection, size=128),
        'qh_oferta': fields.boolean('Oferta Cuarto-Horaria', readonly=True),
        'tipo_necesidad': fields.selection(TIPO_NECESIDAD, 'Tipo de necesidad', readonly=True)
    }

    _defaults = {
        'uni_energia': lambda *a: 'MWh',
        'uni_potencia': lambda *a: 'MW',
        'uni_monetaria': lambda *a: 'EURO',
        'uni_precio': lambda *a: 'EURO/MWh',
        'state': lambda *a: 'no_enviada',
        'ind_defecto': lambda *a: 'N',
        'grad_parada': lambda *a: 0.0,
        'grad_arranque': lambda *a: 0.0,
        'grad_bajada': lambda *a: 0.0,
        'grad_subida': lambda *a: 0.0,
        'valida': lambda *a: False,
        'sustituida': lambda *a: False,
        'tipo_mercado': lambda *a: 'MD',
        'uni_medida': lambda *a: 'P',
        'qh_oferta': lambda *a: False,
        'area_unidad': lambda *a: '1',
        'tipo_unidad': lambda *a: 'UO'
    }


GiscedataOmieOferta()


class GiscedataOmieOfertaHora(osv.osv):

    _name = 'giscedata.omie.oferta.hora'
    _rec_name = 'oferta_id'
    _description = """Representa una oferta por hora de un dia concreto."""

    _columns = {
        'num': fields.integer("Hora del Día"),
        'div': fields.selection(SI_NO, "Es divisible", required=True),
        'ret': fields.selection(SI_NO, "Es retirable", required=True),
        'per': fields.selection(
            PERIODO_DIA, "Periodo horario del día",
            help=_("Seleccionar el periodo del día para el que quiere hacer la oferta"), required=True),
        'desc': fields.char('Descripción', size=16, readonly=True),
        'ctn': fields.float("Energía de la Oferta", digits=(8, 3), help=("Energía de la oferta, sin signo")),
        'prc': fields.float("Precio de la Oferta", digits=(8, 3)),
        'oferta_id': fields.many2one('giscedata.omie.oferta', 'ID Oferta', ondelete='cascade'),
    }


GiscedataOmieOfertaHora()


class GiscedataOmieOfertaExtend(osv.osv):

    _name = 'giscedata.omie.oferta'
    _inherit = 'giscedata.omie.oferta'

    def copy_data(self, cursor, uid, id, default=None, context=None):
        if context is None:
            context = {}
        if default is None:
            default = {}

        default['hora_ids'] = [(5, 0, 0)]
        default['state'] = 'no_enviada'
        default['id_mensaje_respuesta'] = False
        default['fecha_mensaje_respuesta'] = False
        default['id_remitente_respuesta'] = False
        default['id_remitente_origen'] = False
        default['codigo_respuesta'] = False
        default['texto_respuesta'] = False
        default['num_ofertas_procesadas'] = False
        default['num_ofertas_correctas'] = False

        return super(GiscedataOmieOferta, self).copy_data(cursor, uid, id, default, context)

    def mensaje_oferta_md_dicc(self, cursor, uid, oferta_id, context=None):
        if context is None:
            context = {}

        oferta_obj = self.pool.get('giscedata.omie.oferta')
        hora_obj = self.pool.get('giscedata.omie.oferta.hora')

        oferta_vals = oferta_obj.read(cursor, uid, oferta_id, [], context=context)
        oferta_vals_filtered = self.delete_null_fields(cursor, uid, oferta_vals, context=context)

        list_horas = []
        for hora_id in oferta_vals_filtered.get('hora_ids', []):
            hora_vals = hora_obj.read(cursor, uid, hora_id, [], context=context)
            dicc_hora = {
                "num": 1,
                "Per": hora_vals.get('per'),
                "Ctn": hora_vals.get('ctn', 0.0),
                "Prc": hora_vals.get('prc', 0.0)
            }
            list_horas.append(dicc_hora)

        oferta_dicc = {
            'IdMensaje': oferta_vals_filtered.get('id_mensaje'),
            'VerMensaje': oferta_vals_filtered.get('ver_mensaje', 1),
            'FechaMensaje': datetime.today().strftime('%Y-%m-%dT%H:%M:%S'),
            'IdRemitente': oferta_vals_filtered.get('id_remitente'),
            'Oferta': {
                'IdOferta': oferta_vals_filtered.get('id_oferta'),
                'IdUnidad': {
                    "v": oferta_vals_filtered.get('id_unidad'),
                    "codMin": oferta_vals_filtered.get('cod_min_unidad', ""),
                    "area": oferta_vals_filtered.get('area_unidad'),
                    "tipo": oferta_vals_filtered.get('tipo_unidad'),
                },
                'Validez': {
                    'TipoMercado': oferta_vals_filtered.get('tipo_mercado'),
                    'Sesion': {
                        'fecha': oferta_vals_filtered.get('fecha_sesion')[:10],
                    },
                    'IndDefecto': oferta_vals_filtered.get('ind_defecto'),
                    'TipoCasacion': 1,  # Siempre vale 1
                },
                'ClaseOferta': oferta_vals_filtered.get('clase_oferta'),
                # 'UniEnergia': oferta_vals_filtered.get('uni_energia'),  # No permitido desde marzo de 2025
                'UniPotencia': oferta_vals_filtered.get('uni_potencia'),  # Remplaza UniEnergia desde marzo de 2025
                'UniMonetaria': oferta_vals_filtered.get('uni_monetaria'),
                'UniPrecio': oferta_vals_filtered.get('uni_precio'),
                # 'UniGradiente': 'MW/min',  # No permitido desde marzo de 2025
                'Comentario': oferta_vals_filtered.get('comentario_oferta', ""),
                'Detalle': {
                    'Dia': oferta_vals_filtered.get('fecha_sesion')[:10],
                    'Resolucion': 'PT15M',  # PT60M para horario, PT15M para cuartohorario
                    'Blq': list_horas
                }
            },
        }

        return oferta_dicc

    def mensaje_oferta_mi_dicc(self, cursor, uid, oferta_id, context=None):
        if context is None:
            context = {}

        oferta_obj = self.pool.get('giscedata.omie.oferta')
        hora_obj = self.pool.get('giscedata.omie.oferta.hora')

        oferta_vals = oferta_obj.read(cursor, uid, oferta_id, [], context=context)
        oferta_vals_filtered = self.delete_null_fields(cursor, uid, oferta_vals, context=context)

        list_horas = []
        for hora_id in oferta_vals_filtered.get('hora_ids', []):
            hora_vals = hora_obj.read(cursor, uid, hora_id, [], context=context)
            dicc_hora = {
                "num": 1,
                "Per": hora_vals.get('per'),
                "Ctn": hora_vals.get('ctn', 0.0),
                "Prc": hora_vals.get('prc', 0.0)
            }
            list_horas.append(dicc_hora)

        oferta_dicc = {
            'IdMensaje': oferta_vals_filtered.get('id_mensaje'),
            'VerMensaje': oferta_vals_filtered.get('ver_mensaje', 1),
            'FechaMensaje': datetime.today().strftime('%Y-%m-%dT%H:%M:%S'),
            'IdRemitente': oferta_vals_filtered.get('id_remitente'),
            'Oferta': {
                'IdOferta': oferta_vals_filtered.get('id_oferta'),
                'IdUnidad': {
                    "v": oferta_vals_filtered.get('id_unidad'),
                    "codMin": oferta_vals_filtered.get('cod_min_unidad', ""),
                    "area": oferta_vals_filtered.get('area_unidad'),
                    "tipo": oferta_vals_filtered.get('tipo_unidad'),
                },
                'NumOferta': 1,
                'TipoNecesidad': oferta_vals_filtered.get('tipo_necesidad'),
                'Validez': {
                    'TipoMercado': oferta_vals_filtered.get('tipo_mercado'),
                    'Sesion': {
                        'fecha': oferta_vals_filtered.get('fecha_sesion')[:10],
                        'num': oferta_vals_filtered.get('num_sesion')
                    }
                },
                'ClaseOferta': oferta_vals_filtered.get('clase_oferta'),
                # 'UniEnergia': oferta_vals_filtered.get('uni_energia'),  # No permitido desde marzo de 2025
                'UniPotencia': oferta_vals_filtered.get('uni_potencia'),  # Remplaza UniEnergia desde marzo de 2025
                'UniMonetaria': oferta_vals_filtered.get('uni_monetaria'),
                'UniPrecio': oferta_vals_filtered.get('uni_precio'),
                # 'UniGradiente': 'MW/min',  # No permitido desde marzo de 2025
                'Comentario': oferta_vals_filtered.get('comentario_oferta', ""),
                'Detalle': {
                    'Dia': oferta_vals_filtered.get('fecha_sesion')[:10],
                    'Resolucion': 'PT15M',  # PT60M para horario, PT15M para cuartohorario
                    'Blq': list_horas
                }
            },
        }

        return oferta_dicc

    def respuesta_oferta_dicc(self, cursor, uid, res_oferta_dicc, context=None):
        if context is None:
            context = {}

        texto_respuesta = ''
        list_texto_respuesta = res_oferta_dicc.get('RespuestaSerie', [])
        if list_texto_respuesta:
            list_texto_respuesta = list_texto_respuesta[0].get('Respuesta', [])
            if list_texto_respuesta:
                list_texto_respuesta = list_texto_respuesta[0].get('TextoRespuesta', [])
        for aux in list_texto_respuesta:
            texto_respuesta += aux + '\n'

        codigo_respuesta = res_oferta_dicc.get('Respuesta', [])
        if codigo_respuesta:
            list_texto_respuesta = codigo_respuesta[0].get('TextoRespuesta', [])
            for aux in list_texto_respuesta:
                texto_respuesta += aux + '\n'
            codigo_respuesta = codigo_respuesta[0].get('CodigoRespuesta', {}).get('v', '')
        else:
            codigo_respuesta = ''

        respuesta_dicc = {
            'id_mensaje_respuesta': res_oferta_dicc.get('IdMensaje', {}).get('v', False),
            'fecha_mensaje_respuesta': res_oferta_dicc.get('FechaMensaje', {}).get('v', False),
            'id_remitente_respuesta': res_oferta_dicc.get('IdRemitente', {}).get('v', False),
            'id_remitente_origen': res_oferta_dicc.get('IdRemitenteOrigen', {}).get('v', False),
            'codigo_respuesta': codigo_respuesta,
            'texto_respuesta': texto_respuesta,
            'num_ofertas_procesadas': str(res_oferta_dicc.get('ResumenOfertas', {}).get('NumOfertasProcesadas', {}).get('v', 0)),
            'num_ofertas_correctas': str(res_oferta_dicc.get('ResumenOfertas', {}).get('NumOfertasCorrectas', {}).get('v', 0)),
        }
        return respuesta_dicc


    def crear_respuesta_oferta(self, cursor, uid, oferta_id, respuesta_oferta_dicc, context=None):
        if context is None:
            context = {}

        respuesta_dicc = self.respuesta_oferta_dicc(cursor, uid, respuesta_oferta_dicc, context=context)
        return respuesta_dicc

    def delete_null_fields(self, cursor, uid, oferta_dicc, context=None):
        if context is None:
            context = {}
        res = {x: y for x, y in oferta_dicc.items() if y}
        return res

    def update_origen(self, cursor, uid, oferta_id, state, context=None):
        if context is None:
            context = {}

        return True

    def enviar_oferta(self, cursor, uid, ids, context=None):
        if context is None:
            context = {}

        oferta_obj = self.pool.get('giscedata.omie.oferta')
        servicio = self.pool.get('giscedata.omie.siom.service.execution')

        for oferta_id in ids:
            tipo_mercado = self.read(cursor, uid, oferta_id, ['tipo_mercado'])['tipo_mercado']
            if tipo_mercado == 'MD':
                oferta_dicc = oferta_obj.mensaje_oferta_md_dicc(cursor, uid, oferta_id, context=context)
            else:
                oferta_dicc = oferta_obj.mensaje_oferta_mi_dicc(cursor, uid, oferta_id, context=context)
            # Buscamos las ofertas enviadas anteriormente
            search_vals = [
                ('tipo_mercado', '=', oferta_dicc.get('Oferta').get('Validez').get('TipoMercado')),
                ('id_remitente', '=', oferta_dicc.get('IdRemitente')),
                ('fecha_sesion', '=', oferta_dicc.get('Oferta').get('Validez').get('Sesion').get('fecha')),
                ('id_unidad', '=', oferta_dicc.get('Oferta').get('IdUnidad').get('v')),
                ('valida', '=', True),
                ('sustituida', '=', False),
                ('state', '=', 'enviada'),
            ]
            oferta_ids = oferta_obj.search(cursor, uid, search_vals, context=context)
            if oferta_ids:
                # Cogemos la versión mas grande de las ofertas encontradas
                version_oferta = oferta_obj.read(cursor, uid, oferta_ids, ['ver_mensaje'], context=context)
                max_version = max(int(oferta['ver_mensaje']) for oferta in version_oferta)
                oferta_dicc['VerMensaje'] = max_version + 1

                # Incrementamos número de oferta de MI, para que no se sustituyan por error
                if tipo_mercado == 'MI':
                    oferta_dicc['Oferta']['NumOferta'] = len(oferta_ids) + 1

            client = ClientOMIE()

            try:
                # Carril unico MD/MI para todo el ERP, bloqueo transaccional
                # corto en PostgreSQL y registro durable previo a SOAP.

                if tipo_mercado == 'MD':
                    res_oferta_zeep = servicio.ejecutar_servicio(
                        cursor, uid, 'ServicioAltaOfertasMD',
                        lambda: client.ServicioAltaOfertasMD(MensajeOfertasMD=oferta_dicc),
                        oferta_id=oferta_id
                    )
                else:
                    res_oferta_zeep = servicio.ejecutar_servicio(
                        cursor, uid, 'ServicioAltaOfertasMI',
                        lambda: client.ServicioAltaOfertasMI(MensajeOfertasMI=oferta_dicc),
                        oferta_id=oferta_id
                    )

                res_oferta_dicc = helpers.serialize_object(res_oferta_zeep)

                respuesta_dicc = self.crear_respuesta_oferta(cursor, uid, oferta_id, res_oferta_dicc, context=context)

                if int(respuesta_dicc['num_ofertas_correctas']) == 0:
                    state = 'enviada_error'
                    valida = False
                    sustituida = True
                else:
                    state = 'enviada'
                    valida = True
                    sustituida = False

                # Añadir fecha_mensaje y cambiar estado en la oferta enviada
                write_vals = {
                    'fecha_mensaje': datetime.today().strftime('%Y-%m-%d'),
                    'state': state,
                    'valida': valida,
                    'sustituida': sustituida,
                }

                write_vals.update(respuesta_dicc)

                oferta_obj.write(cursor, uid, [oferta_id], write_vals, context=context)

                self.update_origen(cursor, uid, oferta_id, state, context=context)

                if oferta_ids and valida:
                    # Marcamos como no válidas y sustituidas las ofertas enviadas anteriormente
                    oferta_obj.write(cursor, uid, oferta_ids, {'sustituida': True}, context=context)

            except Exception as e:
                raise osv.except_osv('Error:', e)

    def _get_total_energia(self, cursor, uid, ids, field_name, arg, context=None):
        if context is None:
            context = {}

        if not isinstance(ids, (list, tuple)):
            ids = [ids]

        res = {}
        for oferta in ids:
            cursor.execute("SELECT SUM(ctn) FROM giscedata_omie_oferta_hora WHERE oferta_id = {}".format(oferta))
            energia = cursor.fetchone()[0] or 0.0
            res[oferta] = energia
        return res

    _columns = {
        # Blq
        'hora_ids': fields.one2many(
            'giscedata.omie.oferta.hora', 'oferta_id', "horas de Oferta", ondelete='cascade'
        ),
        'total_energia': fields.function(_get_total_energia, method=True, type="float", string="Medida total"),
    }


GiscedataOmieOfertaExtend()
