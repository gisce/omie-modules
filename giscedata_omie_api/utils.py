# -*- coding: utf-8 -*-
from __future__ import absolute_import


def get_pbf_dict(params):
    """
    Prepares OMIE parameters for request 5222
    :param params: dict
    :return: dict
    """

    casacion_dict = {
        'CodConsulta': '5222',  # Energías PBF por unidad ofertante
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
        'CodConsulta': '5608',  # Energías PHF por unidad ofertante
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
                        'v': '24' # TODO: Passar hardcode a la funció que crida el dict
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

# def parse_phfc_reponse(res_casacion, magn):
#     """
#     Addapt format from OMIE 5608 reponse to model data to update
#     :param res_casacion: dict
#     :param magn: str in ('P', 'E')
#     :return: tuple (list of dict, boolean)
#     """
#     TODO: Mirar si es necessita parser i si no, borrar aquest tros de codi (Copiat de la 5608)
#     # Parse and adapt to list of dict
#     res = []
#     is_qh = True
#
#     for regs in res_casacion.get('Fila', []):
#         for reg in regs:
#             data = regs[reg]
#             period = False
#             measure = False
#             desc = False
#             for d in data:
#                 for val in d.values():
#                     if val:
#                         if val['n'] == 'Periodo':
#                             period = str(val['v'])
#                         elif val['n'] == 'Energia' and magn == 'E':
#                             measure = abs(float(val['v']))
#                         elif val['n'] == 'Potencia' and magn == 'P':
#                             measure = abs(float(val['v']))
#                         elif val['n'] == 'Descripción':
#                             desc = val['v']
#                             if 'Q' in desc and not is_qh:
#                                 is_qh = True
#                         else:
#                             pass
#             if period and measure and desc:
#                 res.append({'num': int(period), 'per': period, 'ctn': measure, 'desc': desc})
#
#     return res, is_qh


def convert_casation_to_qh(casation, uni_medida):
    """
    Converts casation to QH format, fixing energy if needed
    :param casation: list of dict
    :param uni_medida: str in ('E', 'P')
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
            # Energy is divided by 4, Power is kept as is
            if uni_medida == 'E':
                ctn = ctn / 4.0
            vals = {'num': num,
                    'per': per,
                    'desc': desc,
                    'ctn': ctn}
            res.append(vals)

    return res
