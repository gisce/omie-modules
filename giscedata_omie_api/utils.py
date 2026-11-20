# -*- coding: utf-8 -*-
from __future__ import absolute_import

_OMIE_DAILY_QH_DATE_START = '2025-10-01'
_OMIE_INDICATORS = [('pbc', 'Programa Base de Casación (PBC)'),
                    ('phfc', 'Programa Horario Final Continuo (PHFC)')]
_NUM_RONDA = [(str(x+1), str(x+1)) for x in range(24)]

AREA_UNIDAD_SELECTION = [
    ('1', 'España'),
    ('2', 'Portugal'),
    ('3', 'Europa - Interconex Francia'),
    ('4', 'Andorra'),
    ('5', 'Africa - Interconex Marruecos'),
]

TIPO_UNIDAD_SELECTION = [
    ('UO', 'Unidad Ofertante'),
    ('UF', 'Unidad Física'),
    ('RE', 'Régimen Especial'),
    ('CP', 'Unidad de Contratación a Plazo'),
    ('UP', 'Unidad de programación'),
]

TIPO_MERCADO = [
    ('MD', 'Mercado Diario'),
    ('MI', 'Mercado Intradiario'),
]

TIPO_NUM_SESION = [
    ('1', 'Sesión IDA1'),
    ('2', 'Sesión IDA2'),
    ('3', 'Sesión IDA3')
]

SI_NO = [
    ('S', 'Si'),
    ('N', 'No'),
]

CLASE_OFERTA = [
    ('C', 'Compra'),
    ('V', 'Venta'),
]

UNIDAD_ENERGIA = [
    ('MWh', 'MWh'),
    ('kWh', 'kWh'),
]

UNIDAD_POTENCIA = [
    ('MW', 'MW'),
    ('kW', 'kW'),
]

UNIDAD_MONETARIA = [
    ('cEURO', 'cEURO'),
    ('EURO', 'EURO'),
]

UNIDAD_PRECIOS = [
    ('cEURO/kWh', 'cEURO/kWh'),
    ('cEURO/MWh', 'cEURO/MWh'),
    ('EURO/MWh', 'EURO/MWh'),
]

UNIDAD_MEDIDA = [
    ('E', 'Energía'),
    ('P', 'Potencia'),
]

PERIODO_DIA = [
    ('1', '1'),
    ('2', '2'),
    ('3', '3'),
    ('4', '4'),
    ('5', '5'),
    ('6', '6'),
    ('7', '7'),
    ('8', '8'),
    ('9', '9'),
    ('10', '10'),
    ('11', '11'),
    ('12', '12'),
    ('13', '13'),
    ('14', '14'),
    ('15', '15'),
    ('16', '16'),
    ('17', '17'),
    ('18', '18'),
    ('19', '19'),
    ('20', '20'),
    ('21', '21'),
    ('22', '22'),
    ('23', '23'),
    ('24', '24'),
    ('25', '25'),
    ('26', '26'),
    ('27', '27'),
    ('28', '28'),
    ('29', '29'),
    ('30', '30'),
    ('31', '31'),
    ('32', '32'),
    ('33', '33'),
    ('34', '34'),
    ('35', '35'),
    ('36', '36'),
    ('37', '37'),
    ('38', '38'),
    ('39', '39'),
    ('40', '40'),
    ('41', '41'),
    ('42', '42'),
    ('43', '43'),
    ('44', '44'),
    ('45', '45'),
    ('46', '46'),
    ('47', '47'),
    ('48', '48'),
    ('49', '49'),
    ('50', '50'),
    ('51', '51'),
    ('52', '52'),
    ('53', '53'),
    ('54', '54'),
    ('55', '55'),
    ('56', '56'),
    ('57', '57'),
    ('58', '58'),
    ('59', '59'),
    ('60', '60'),
    ('61', '61'),
    ('62', '62'),
    ('63', '63'),
    ('64', '64'),
    ('65', '65'),
    ('66', '66'),
    ('67', '67'),
    ('68', '68'),
    ('69', '69'),
    ('70', '70'),
    ('71', '71'),
    ('72', '72'),
    ('73', '73'),
    ('74', '74'),
    ('75', '75'),
    ('76', '76'),
    ('77', '77'),
    ('78', '78'),
    ('79', '79'),
    ('80', '80'),
    ('81', '81'),
    ('82', '82'),
    ('83', '83'),
    ('84', '84'),
    ('85', '85'),
    ('86', '86'),
    ('87', '87'),
    ('88', '88'),
    ('89', '89'),
    ('90', '90'),
    ('91', '91'),
    ('92', '92'),
    ('93', '93'),
    ('94', '94'),
    ('95', '95'),
    ('96', '96'),
    ('97', '97'),
    ('98', '98'),
    ('99', '99'),
    ('100', '100'),
]

ESTADO_OFERTA = [
    ('no_enviada', 'No Enviada'),
    ('enviada', 'Enviada'),
    ('enviada_error', 'Enviada Con Errores'),
    ('casacion', 'Generada para descargar la casación')
]

TIPO_NECESIDAD = [
    ('10', '10: Adq. de distribuidor >10%'),
    ('20', '20: Adq. de distribuidor >10%'),
    ('30', '30: Venta de distribuidor < 10%'),
    ('40', '40: Venta de distribuidor > 10%'),
    ('50', '50: Adq. de comercializador'),
    ('60', '60: Adq. de consumidor Cualif.'),
    ('61', '61: Adq. de consumidor directo'),
    ('70', '70: Venta de comercializador'),
    ('80', '80: Venta de consumidor Cualif.'),
    ('81', '81: Venta de consumidor directo'),
    ('90', '90: Venta de unidad de bombeo'),
    ('101', '101: Compra por indisponibilidad'),
    ('102', '102: Compra por pruebas'),
    ('103', '103: Compra por infactibilidad'),
    ('111', '111: Venta por probabil. de vertido'),
    ('112', '112: Venta por pruebas'),
    ('113', '113: Venta por infactibilidad'),
    ('120', '120: Oferta de venta libre'),
    ('130', '130: Oferta de compra libre'),
    ('140', '140: Adq. CUR > 10%'),
    ('141', '141: Adq. CUR < 10%'),
    ('142', '142: Venta CUR > 10%'),
    ('143', '143: Venta CUR < 10%'),

]

def get_pbc_dict(params):
    """
    Prepares OMIE parameters for request 5223
    :param params: dict
    :return: dict
    """

    casacion_dict = {
        'CodConsulta': '5223',  # Programa Base de Casación (PBC) por unidad ofertante
        'Parametros': {
            '_value_1': [
                {
                    'Txt': {
                        'n': 'UOfertante',
                        'v': params['id_unidad']
                    }
                },
                {
                    'Num': None
                },
                {
                    'Fec': {
                        'n': 'FechaCasacion',
                        'v': params['fecha_ronda']
                    }
                },
                {
                    'Ses': None
                },
                {
                    'Txt': {
                        'n': 'UMedida',
                        'v': params['uni_medida']
                    }
                },
            ]
        }
    }

    return casacion_dict

def parse_pbc_reponse(res_casacion, magn):
    """
    Addapt format from OMIE 5223 reponse to model data to update
    :param res_casacion: dict
    :param magn: str in ('P', 'E')
    :return: list of dict
    """
    # Parse and addapt to list of dict
    res = []

    for regs in res_casacion.get('Fila', []):
        for reg in regs:
            data = regs[reg]
            period = False
            measure = False
            desc = False
            for d in data:
                for val in d.values():
                    if val:
                        if val['n'] == 'Periodo':
                            period = str(val['v'])
                        elif val['n'] == 'Energia' and magn == 'E':
                            measure = abs(float(val['v']))
                        elif val['n'] == 'Potencia' and magn == 'P':
                            measure = abs(float(val['v']))
                        elif val['n'] == 'Descripción':
                            desc = val['v']
                        else:
                            pass
            if period and measure and desc:
                res.append({'num': int(period), 'per': period, 'ctn': measure, 'desc': desc})

    return res


def get_pbf_dict(params):
    """
    Prepares OMIE parameters for request 5222
    :param params: dict
    :return: dict
    """

    casacion_dict = {
        'CodConsulta': '5222',  # Programa Diario Base de Funcionamiento (PBF) por unidad ofertante
        'Parametros': {
            '_value_1': [
                {
                    'Txt': {
                        'n': 'UOfertante',
                        'v': params['id_unidad']
                    }
                },
                {
                    'Num': None
                },
                {
                    'Fec': {
                        'n': 'Fecha',
                        'v': params['fecha_sesion']
                    }
                },
                {
                    'Ses': None
                },
                {
                    'Txt': {
                        'n': 'UMedida',
                        'v': params['uni_medida']
                    }
                },
            ]
        }
    }

    return casacion_dict


def parse_pbf_reponse(res_casacion, magn):
    """
    Addapt format from OMIE 5222 reponse to model data to update
    :param res_casacion: dict
    :param magn: str in ('P', 'E')
    :return: list of dict
    """
    # Parse and addapt to list of dict
    res = []

    for regs in res_casacion.get('Fila', []):
        for reg in regs:
            data = regs[reg]
            period = False
            measure = False
            desc = False
            for d in data:
                for val in d.values():
                    if val:
                        if val['n'] == 'Periodo':
                            period = str(val['v'])
                        elif val['n'] == 'EnergiaTotal' and magn == 'E':
                            measure = abs(float(val['v']))
                        elif val['n'] == 'PotenciaTotal' and magn == 'P':
                            measure = abs(float(val['v']))
                        elif val['n'] == 'Descripción':
                            desc = val['v']
                        else:
                            pass
            if period and measure and desc:
                res.append({'num': int(period), 'per': period, 'ctn': measure, 'desc': desc})

    return res


def get_phf_dict(params):
    """
    Prepares OMIE parameters for request 5608
    :param params: dict
    :return: dict
    """

    casacion_dict = {
        'CodConsulta': '5608',  # Programa Horario Final (PHF) por unidad ofertante
        'Parametros': {
            '_value_1': [
                {
                    'Txt': {
                        'n': 'UOfertante',
                        'v': params['id_unidad']
                    }
                },
                {
                    'Num': None
                },
                {
                    'Fec': {
                        'n': 'Fecha',
                        'v': params['fecha_sesion']
                    }
                },
                {
                    'Ses': {
                        'n': 'Sesion',
                        'v': params['num_sesion']
                    }
                },
                {
                    'Txt': {
                        'n': 'UMedida',
                        'v': params['uni_medida']
                    }
                },
            ]
        }
    }

    return casacion_dict


def parse_phf_reponse(res_casacion, magn):
    """
    Addapt format from OMIE 5608 reponse to model data to update
    :param res_casacion: dict
    :param magn: str in ('P', 'E')
    :return: tuple (list of dict, boolean)
    """
    # Parse and addapt to list of dict
    res = []
    is_qh = True

    for regs in res_casacion.get('Fila', []):
        for reg in regs:
            data = regs[reg]
            period = False
            measure = False
            desc = False
            for d in data:
                for val in d.values():
                    if val:
                        if val['n'] == 'Periodo':
                            period = str(val['v'])
                        elif val['n'] == 'Energia' and magn == 'E':
                            measure = abs(float(val['v']))
                        elif val['n'] == 'Potencia' and magn == 'P':
                            measure = abs(float(val['v']))
                        elif val['n'] == 'Descripción':
                            desc = val['v']
                            if 'Q' in desc and not is_qh:
                                is_qh = True
                        else:
                            pass
            if period and measure and desc:
                res.append({'num': int(period), 'per': period, 'ctn': measure, 'desc': desc})

    return res, is_qh

def get_phfc_dict(params):
    """
    Prepares OMIE parameters for request 4144
    :param params: dict
    :return: dict
    """

    casacion_dict = {
        'CodConsulta': '4144',  # Energías PHFC por Unidad
        'Parametros': {
            '_value_1': [
                {
                    'Txt': {
                        'n': 'Unidad',
                        'v': params['id_unidad']
                    }
                },
                {
                    'Fec': {
                        'n': 'FeRonda',
                        'v': params['fecha_ronda']
                    }
                },
                {
                    'Ses': {
                        'n': 'NuRonda',
                        'v': params['num_ronda']
                    }
                },
                {
                    'Txt': {
                        'n': 'UMedida',
                        'v': params['uni_medida']
                    }
                }
            ]
        }
    }

    return casacion_dict

def parse_phfc_reponse(res_casacion, magn):
    """
    Addapt format from OMIE 5608 reponse to model data to update
    :param res_casacion: dict
    :param magn: str in ('P', 'E')
    :return: list of dict
    """
    # Parse and adapt to list of dict
    res = []

    for regs in res_casacion.get('Fila', []):
        for reg in regs:
            data = regs[reg]
            period = False
            measure = False
            desc = False
            tipo_oferta = False
            for d in data:
                for val in d.values():
                    if val:
                        if val['n'] == 'Periodo':
                            period = str(val['v'])
                        elif val['n'] == 'TipoOferta':
                            tipo_oferta = val['v']
                        elif val['n'] == 'Energia' and magn == 'E':
                            measure = abs(float(val['v']))
                        elif val['n'] == 'Potencia' and magn == 'P':
                            measure = abs(float(val['v']))
                        elif val['n'] == 'Descripción':
                            desc = val['v']
                        else:
                            pass
            if period and measure and desc and tipo_oferta:
                res.append({'num': int(period), 'per': period, 'ctn': measure, 'desc': desc, 'tipo_oferta': tipo_oferta})

    return res


def convert_casation_to_qh(casation):
    """
    Converts casation to QH format
    :param casation: list of dict
    :return: list of dict
    """
    res = []

    # Convert each measure from hourly to quarter-hourly
    for d in casation:
        for period in range(4):
            num = (d.get('num') - 1) * 4 + (period + 1)
            per = str(num).zfill(2)
            desc = 'H{}Q{}'.format(d.get('num'), period+1)
            ctn = d.get('ctn', 0.0)
            vals = {'num': num,
                    'per': per,
                    'desc': desc,
                    'ctn': ctn}
            res.append(vals)

    return res
