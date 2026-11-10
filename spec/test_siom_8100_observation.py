# -*- coding: utf-8 -*-
"""Fase B 8100: pruebas sin ERP ni OMIE, Python 2.7 / 3.x."""
from __future__ import absolute_import

from datetime import datetime
from decimal import Decimal
import hashlib
import importlib
import json
import os
from datetime import time
import sys
import types
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
APP = os.path.join(ROOT, 'giscedata_omie_api')


class FakeFields(object):
    def __getattr__(self, name):
        return lambda *a, **k: (name, a, k)


class FakePool(object):
    def __init__(self, model):
        self.model = model
    def get(self, name):
        if name == 'giscedata.omie.siom.query.execution':
            return self.model
        raise AssertionError(name)


def respuesta(filas=None, codigo=8100, mensajes=None):
    return {'CodConsulta': {'v': codigo},
            'Fila': [] if filas is None else filas,
            'Respuesta': [] if mensajes is None else mensajes}


def fila():
    return {'_value_1': [
        {'Num': {'n': 'ConsultaAfectada', 'v': 5222}},
        {'Txt': {'n': 'CampoDesconocido', 'v': 'valor no interpretado'}},
    ]}


class FaseB8100Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        nombres = ('giscedata_omie_api', 'osv', 'tools', 'tools.translate',
                   'zeep', 'zeep.helpers',
                   'giscedata_omie_api.giscedata_omie_siom_exclusion_diagnostic',
                   'giscedata_omie_api.giscedata_omie_siom_exclusion_rules',
                   'giscedata_omie_api.giscedata_omie_siom_exclusion_observation_parser',
                   'giscedata_omie_api.giscedata_omie_siom_exclusion_observation',
                   'giscedata_omie_api.giscedata_omie_siom_query_execution',
                   'giscedata_omie_api.wizard',
                   'giscedata_omie_api.wizard.wizard_siom_exclusion_observation')
        cls.originales = dict((k, sys.modules.get(k)) for k in nombres)
        pkg = types.ModuleType('giscedata_omie_api')
        pkg.__path__ = [APP]
        sys.modules['giscedata_omie_api'] = pkg
        wizard_pkg = types.ModuleType('giscedata_omie_api.wizard')
        wizard_pkg.__path__ = [os.path.join(APP, 'wizard')]
        sys.modules[wizard_pkg.__name__] = wizard_pkg
        osv = types.ModuleType('osv')
        osv.osv = type('FakeOSV', (), {'osv': type('Base', (), {}),
                                     'osv_memory': type('Memory', (), {}),
                                     'except_osv': Exception})
        osv.fields = FakeFields()
        sys.modules['osv'] = osv
        tools = types.ModuleType('tools')
        tools.__path__ = []
        trans = types.ModuleType('tools.translate')
        trans._ = lambda s: s
        tools.translate = trans
        sys.modules['tools'] = tools
        sys.modules[trans.__name__] = trans
        zeep = types.ModuleType('zeep')
        helpers = types.ModuleType('zeep.helpers')
        helpers.serialize_object = lambda x: x
        zeep.helpers = helpers
        sys.modules['zeep'] = zeep
        sys.modules[helpers.__name__] = helpers
        cls.rules = importlib.import_module(
            'giscedata_omie_api.giscedata_omie_siom_exclusion_rules')
        cls.parser = importlib.import_module(
            'giscedata_omie_api.giscedata_omie_siom_exclusion_observation_parser')
        cls.observation = importlib.import_module(
            'giscedata_omie_api.giscedata_omie_siom_exclusion_observation')
        cls.execution = importlib.import_module(
            'giscedata_omie_api.giscedata_omie_siom_query_execution')
        cls.wizard = importlib.import_module(
            'giscedata_omie_api.wizard.wizard_siom_exclusion_observation')

    @classmethod
    def tearDownClass(cls):
        for name, old in cls.originales.items():
            if old is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = old

    def setUp(self):
        self.record = self.observation.GiscedataOmieSiomExclusionObservation()
        self.created = []
        self.record.create = lambda cr, uid, vals, context=None: self._insert(vals)

    def _insert(self, vals):
        self.created.append(vals.copy())
        return len(self.created)

    def _mock_controller(self, value):
        class Control(object):
            def __init__(self, v):
                self.value = v
                self.calls = []
            def _consultar_datos_8100(self, cr, uid, context=None, client=None):
                self.calls.append(uid)
                return self.value
        control = Control(value)
        self.record.pool = FakePool(control)
        return control

    def test_vacia_registra_observacion_y_no_reglas(self):
        control = self._mock_controller(respuesta())
        x = self.record.registrar_observacion_8100(None, 1)
        self.assertEqual(control.calls, [1])
        self.assertEqual(x['estado'], 'vacia')
        self.assertEqual(x['total_filas'], 0)
        self.assertFalse(x['reglas_activadas'])
        self.assertEqual(self.created[0]['respuesta_json'] and
                         json.loads(self.created[0]['respuesta_json'])['Fila'], [])

    def test_varias_consultas_vacias_no_borran_historial(self):
        self._mock_controller(respuesta([fila()]))
        self.record.registrar_observacion_8100(None, 1)
        self._mock_controller(respuesta())
        self.record.registrar_observacion_8100(None, 1)
        self.assertEqual([x['estado'] for x in self.created], ['con_datos', 'vacia'])
        self.assertEqual(len(self.created), 2)

    def test_datos_guardan_evidencia_y_no_inventan_horarios(self):
        self._mock_controller(respuesta([fila()]))
        resultado = self.record.registrar_observacion_8100(None, 1)
        self.assertEqual(resultado['total_filas'], 1)
        registro = self.created[0]
        self.assertIn('CampoDesconocido', json.loads(registro['columnas_json']))
        self.assertIn('CampoDesconocido', registro['respuesta_json'])
        self.assertNotIn('inicio_utc', registro)
        self.assertNotIn('bloquear', registro)
        hash_actual = hashlib.sha256(registro['respuesta_json'].encode('utf-8')).hexdigest()
        self.assertEqual(hash_actual, registro['huella_sha256'])

    def test_fallo_de_formato_no_crea_observacion(self):
        self._mock_controller(respuesta([fila()], codigo=8101))
        with self.assertRaises(self.parser.Formato8100NoReconocido):
            self.record.registrar_observacion_8100(None, 1)
        self.assertEqual(self.created, [])

    def test_error_omie_no_se_persiste_como_vacia(self):
        self._mock_controller(respuesta([], mensajes=[{'Codigo': 'ERROR'}]))
        with self.assertRaises(self.parser.Formato8100NoReconocido):
            self.record.registrar_observacion_8100(None, 1)
        self.assertEqual(self.created, [])

    def test_rpc_denegado_no_llama_controlador(self):
        control = self._mock_controller(respuesta())
        with self.assertRaises(Exception):
            self.record.registrar_observacion_8100(None, 2)
        self.assertEqual(control.calls, [])

    def test_decimal_y_fecha_pueden_guardarse_sin_inferencias(self):
        r = respuesta([{'_value_1': [
            {'Feh': {'n': 'FechaNoInterpretada', 'v': datetime(2026, 10, 28, 7, 0)}},
            {'Num': {'n': 'Cantidad', 'v': Decimal('1.5')}}]}])
        obs = self.parser.preparar_observacion_8100(r)
        self.assertIn('2026-10-28T07:00:00', obs['respuesta_json'])
        self.assertIn('1.5', obs['respuesta_json'])

    def test_limite_tamano_rechaza_sin_truncar(self):
        with self.assertRaises(self.parser.Formato8100NoReconocido):
            self.parser.preparar_observacion_8100(respuesta([fila()]), max_bytes=30)

    def test_rechaza_flotantes_no_finitos(self):
        with self.assertRaises(self.parser.Formato8100NoReconocido):
            self.parser.preparar_observacion_8100(
                respuesta([{'Num': {'n': 'Desconocido', 'v': float('nan')}}]))

    def test_limite_filas_es_estricto(self):
        with self.assertRaises(self.parser.Formato8100NoReconocido):
            self.parser.preparar_observacion_8100(
                respuesta([{}] * (self.parser.MAX_FILAS + 1)))

    def test_llamada_8100_usa_controlador_sin_reintentos(self):
        obj = self.execution.GiscedataOmieSiomQueryExecution()
        calls = []
        def ejecutar(cr, uid, codigo, llamada, **kwargs):
            calls.append((codigo, kwargs['reintentos'],
                          kwargs['sincronizacion_inicial']))
            return llamada()
        obj.ejecutar_consulta = ejecutar
        class Client(object):
            def ServicioEjecucionConsultaEncolumnada(self, **kwargs):
                calls.append(kwargs['MensajeEjecucionConsulta']['CodConsulta'])
                return respuesta()
        self.assertEqual(obj._consultar_datos_8100(None, 1, client=Client())['Fila'], [])
        self.assertEqual(calls, [(8100, 0, False), '8100'])

    def test_diagnostico_se_mantiene_sin_persistencia(self):
        obj = self.execution.GiscedataOmieSiomQueryExecution()
        obj._consultar_datos_8100 = lambda *a, **kw: respuesta([fila()])
        result = obj.diagnosticar_8100(None, 1)
        self.assertEqual(result['total_filas'], 1)
        self.assertTrue(result['solo_diagnostico'])

    def test_acceso_wizard_denegado_antes_de_elevacion(self):
        wizard = self.wizard.WizardSiomExclusionObservation()
        wizard._puede_consultar = lambda *a, **kw: False
        wizard.simple_browse = lambda *a, **kw: self.fail('no se debe leer wizard')
        with self.assertRaises(Exception):
            wizard.consultar_desde_omie(None, 9, [12])

    def test_acceso_wizard_admin_con_resultado_vacio(self):
        wizard = self.wizard.WizardSiomExclusionObservation()
        wizard._puede_consultar = lambda *a, **kw: True
        wizard.simple_browse = lambda *a, **kw: type('W', (), {'state': 'init'})()
        escritos = []
        wizard.write = lambda *a, **kw: escritos.append(a[3])
        class Model(object):
            def registrar_observacion_8100(self, cr, uid, context=None):
                if uid != 1: raise AssertionError('No se elevo')
                return {'observacion_id': 7, 'estado': 'vacia',
                        'total_filas': 0, 'huella_sha256': 'f' * 64}
        class Pool(object):
            def get(self, key):
                if key != 'giscedata.omie.siom.exclusion.observation':
                    raise AssertionError(key)
                return Model()
        wizard.pool = Pool()
        self.assertTrue(wizard.consultar_desde_omie(None, 9, [12]))
        self.assertIn('NO implica ausencia', escritos[0]['info'])

    def test_fila_con_formato_invalido_no_se_guarda(self):
        self._mock_controller(respuesta(filas={'Num': 1}))
        with self.assertRaises(self.parser.Formato8100NoReconocido):
            self.record.registrar_observacion_8100(None, 1)
        self.assertEqual(self.created, [])


    def _fila_real(self, codigo=3004, inicio='10:00:00', fin='10:15:00',
                   acceso='AMBAS'):
        # Contrato exacto observado en la respuesta real de pruebas7.
        return {'_value_1': [
            {'Fec': None, 'Feh': None, 'Hor': None,
             'Num': {'n': 'CdConsult', 'v': str(codigo)}, 'Txt': None},
            {'Fec': None, 'Feh': None,
             'Hor': {'n': 'HoraIni', 'v': inicio},
             'Num': None, 'Txt': {'n': 'Titulo', 'v': 'Consulta real'}},
            {'Fec': None, 'Feh': None,
             'Hor': {'n': 'HoraFin', 'v': fin}, 'Num': None, 'Txt': None},
            {'Txt': {'n': 'TipoAcceso', 'v': acceso}},
        ]}

    def test_parser_8100_real_y_extremos(self):
        intervalos = self.rules.parsear_intervalos_8100(
            respuesta([self._fila_real()]))
        self.assertEqual(intervalos[0]['consulta'], 3004)
        self.assertEqual(intervalos[0]['tipo_acceso'], 'AMBAS')
        self.assertIsNone(self.rules.consulta_excluida(intervalos, 3004, '09:59:59'))
        self.assertIsNotNone(self.rules.consulta_excluida(intervalos, 3004, '10:00:00'))
        self.assertIsNotNone(self.rules.consulta_excluida(intervalos, 3004, time(10, 14, 59)))
        self.assertIsNotNone(self.rules.consulta_excluida(intervalos, 3004, '10:15:00'))
        self.assertIsNone(self.rules.consulta_excluida(intervalos, 3004, '10:15:01'))
        self.assertIsNone(self.rules.consulta_excluida(intervalos, 5222, '10:05:00'))

    def test_reloj_postgresql_con_microsegundos_y_limites_exactos(self):
        intervalos = self.rules.parsear_intervalos_8100(
            respuesta([self._fila_real()]))
        # HoraFin incluida: se bloquea tambien el segundo 10:15:00 completo.
        self.assertIsNone(self.rules.consulta_excluida(
            intervalos, 3004, time(9, 59, 59, 999999)))
        self.assertIsNotNone(self.rules.consulta_excluida(
            intervalos, 3004, time(10, 0, 0, 1)))
        self.assertIsNotNone(self.rules.consulta_excluida(
            intervalos, 3004, time(10, 14, 59, 999999)))
        self.assertIsNotNone(self.rules.consulta_excluida(
            intervalos, 3004, time(10, 15, 0, 1)))
        self.assertIsNotNone(self.rules.consulta_excluida(
            intervalos, 3004, time(10, 15, 0, 999999)))
        self.assertIsNone(self.rules.consulta_excluida(
            intervalos, 3004, time(10, 15, 1, 0)))
        # El contrato de la respuesta OMIE no se relaja.
        with self.assertRaises(self.rules.Formato8100NoReconocido):
            self.rules.parsear_intervalos_8100(respuesta([
                self._fila_real(inicio=time(10, 0, 0, 1))]))

    def test_reloj_postgresql_texto_con_microsegundos(self):
        intervalos = self.rules.parsear_intervalos_8100(
            respuesta([self._fila_real()]))
        # OpenERP 5/psycopg2 puede devolver una cadena, no datetime.time.
        for reloj, bloqueada in (
                ('09:59:59.999999', False),
                ('10:00:00.000001', True),
                ('10:07:00.1', True),
                ('10:15:00.999999', True),
                ('10:15:01.000001', False),
                ('15:43:48.763526', False)):
            self.assertEqual(bool(self.rules.consulta_excluida(
                intervalos, 3004, reloj)), bloqueada, reloj)
        # No admitir fracciones en la respuesta horaria de OMIE.
        with self.assertRaises(self.rules.Formato8100NoReconocido):
            self.rules.parsear_intervalos_8100(respuesta([
                self._fila_real(inicio='10:00:00.123456')]))
        with self.assertRaises(self.rules.Formato8100NoReconocido):
            self.rules.consulta_excluida(intervalos, 3004,
                                        '10:07:00.1234567')

    def test_controlador_8100_con_hora_textual_de_postgresql(self):
        obj = self.execution.GiscedataOmieSiomQueryExecution()
        self._configurar_control_8100(obj)
        fecha = datetime(2026, 11, 3, 10, 0)
        with self.assertRaises(self.execution.ConsultaExcluidaOMIE):
            obj._comprobar_exclusion_8100(
                self._fake_db_exclusion(fecha=fecha,
                                        hora='10:15:00.763526'),
                3004, fecha)
        self.assertIsNone(obj._comprobar_exclusion_8100(
            self._fake_db_exclusion(fecha=fecha, hora='15:43:48.763526'),
            3004, fecha))

    def test_parser_8100_ventana_que_cruza_medianoche(self):
        intervalos = self.rules.parsear_intervalos_8100(
            respuesta([self._fila_real(inicio='23:55:00', fin='00:05:00')]))
        self.assertTrue(self.rules.consulta_excluida(intervalos, 3004, '23:59:59'))
        self.assertTrue(self.rules.consulta_excluida(intervalos, 3004, '00:00:00'))
        self.assertTrue(self.rules.consulta_excluida(intervalos, 3004, '00:05:00'))
        self.assertFalse(self.rules.consulta_excluida(intervalos, 3004, '00:05:01'))

    def test_parser_8100_rechaza_columna_duplicada_o_acceso_desconocido(self):
        r = self._fila_real()
        r['_value_1'].append({'Txt': {'n': 'Titulo', 'v': 'duplicado'}})
        with self.assertRaises(self.rules.Formato8100NoReconocido):
            self.rules.parsear_intervalos_8100(respuesta([r]))
        with self.assertRaises(self.rules.Formato8100NoReconocido):
            self.rules.parsear_intervalos_8100(
                respuesta([self._fila_real(acceso='AGENTE')]))

    def test_tipo_acceso_web_ws_ambas_ignora_web_en_robot(self):
        filas = [self._fila_real(inicio='10:00:00', fin='10:15:00', acceso='WEB'),
                 self._fila_real(inicio='12:00:00', fin='12:15:00', acceso='WS'),
                 self._fila_real(inicio='14:00:00', fin='14:15:00', acceso='Webservice'),
                 self._fila_real(inicio='16:00:00', fin='16:15:00', acceso='AMBAS')]
        intervalos = self.rules.parsear_intervalos_8100(respuesta(filas))
        self.assertEqual([i['tipo_acceso'] for i in intervalos],
                         ['WEB', 'WS', 'WS', 'AMBAS'])
        self.assertIsNone(self.rules.consulta_excluida(
            intervalos, 3004, '10:07:00'))
        for hora in ('12:07:00', '14:07:00', '16:07:00'):
            self.assertIsNotNone(self.rules.consulta_excluida(
                intervalos, 3004, hora))

    def test_solo_web_no_bloquea_ni_contamina_otras_consultas(self):
        intervalos = self.rules.parsear_intervalos_8100(respuesta([
            self._fila_real(codigo=3004, acceso='WEB'),
            self._fila_real(codigo=4111, acceso='AMBAS')]))
        self.assertIsNone(self.rules.consulta_excluida(
            intervalos, 3004, '10:07:00'))
        self.assertIsNotNone(self.rules.consulta_excluida(
            intervalos, 4111, '10:07:00'))

    def test_observacion_real_guarda_intervalos_normalizados(self):
        self._mock_controller(respuesta([self._fila_real()]))
        result = self.record.registrar_observacion_8100(None, 1)
        self.assertFalse(result['reglas_activadas'])
        self.assertEqual(self.created[0]['interpretacion'], 'valida')
        self.assertEqual(json.loads(self.created[0]['intervalos_json'])[0]['inicio'],
                         '10:00:00')

    def test_observacion_desconocida_sigue_solo_diagnostico(self):
        self._mock_controller(respuesta([fila()]))
        self.record.registrar_observacion_8100(None, 1)
        self.assertEqual(self.created[0]['interpretacion'], 'no_interpretable')
        self.assertFalse(self.created[0]['intervalos_json'])

    def _fake_db_exclusion(self, estado='valida', viejo=None,
                           fecha=None, hora=None):
        registro = self.parser.preparar_observacion_8100(
            respuesta([self._fila_real()]))
        fecha = fecha or datetime(2026, 11, 3, 10, 0)
        hora = hora or time(10, 7, 0, 345678)
        class DB(object):
            def __init__(self):
                self.sql = []
                self.result = None
            def execute(self, statement, params=()):
                sql = ' '.join(statement.lower().split())
                self.sql.append((sql, params))
                if 'where interpretacion = ' in sql:
                    self.result = (('valida', registro['intervalos_json'], fecha),) if viejo else ()
                elif 'select interpretacion, intervalos_json' in sql:
                    self.result = ((estado, registro['intervalos_json'], fecha),)
                elif '::time' in sql:
                    self.result = ((hora,),)
                else:
                    raise AssertionError('SQL inesperado ' + sql)
            def fetchone(self):
                row = self.result[0] if self.result else None
                self.result = ()
                return row
        return DB()

    def _configurar_control_8100(self, obj, valores=None):
        class Config(object):
            def __init__(self, vals):
                self.valores = vals
                self.consultas = []
            def get(self, cr, uid, key, default=None):
                self.consultas.append((cr, uid, key))
                return self.valores.get(key, default)
        class Pool(object):
            def __init__(self, config):
                self.config = config
            def get(self, name):
                assert name == 'res.config'
                return self.config
        config = Config(dict({'siom_8100_apply': '1',
                              'siom_8100_timezone': 'UTC+01:00',
                              'siom_8100_max_age_seconds': '3600'}, **(valores or {})))
        obj.pool = Pool(config)
        return config

    def test_bloqueo_8100_opt_in_y_sin_soap(self):
        obj = self.execution.GiscedataOmieSiomQueryExecution()
        config = self._configurar_control_8100(obj)
        db = self._fake_db_exclusion()
        with self.assertRaises(self.execution.ConsultaExcluidaOMIE):
            obj._comprobar_exclusion_8100(db, 3004, datetime(2026, 11, 3, 10, 7))
        self.assertTrue(config.consultas)
        self.assertTrue(all(consulta[0] is db and consulta[1] == 1
                            for consulta in config.consultas))
        self.assertIsNone(obj._comprobar_exclusion_8100(
            self._fake_db_exclusion(), 5222, datetime(2026, 11, 3, 10, 7)))

    def test_res_config_desactivado_y_cambios_en_caliente(self):
        obj = self.execution.GiscedataOmieSiomQueryExecution()
        config = self._configurar_control_8100(obj, {'siom_8100_apply': '0'})
        db = self._fake_db_exclusion()
        self.assertIsNone(obj._comprobar_exclusion_8100(
            db, 3004, datetime(2026, 11, 3, 10, 7)))
        self.assertEqual(db.sql, [])
        config.valores['siom_8100_apply'] = '1'
        with self.assertRaises(self.execution.ConsultaExcluidaOMIE):
            obj._comprobar_exclusion_8100(
                db, 3004, datetime(2026, 11, 3, 10, 7))
        config.valores['siom_8100_apply'] = '0'
        self.assertIsNone(obj._comprobar_exclusion_8100(
            db, 3004, datetime(2026, 11, 3, 10, 7)))
        config.valores['siom_8100_apply'] = 'YES'
        with self.assertRaises(self.execution.SinConfiguracionExclusion8100):
            obj._comprobar_exclusion_8100(
                db, 3004, datetime(2026, 11, 3, 10, 7))

    def test_desfase_fijo_utc_mas_uno_no_depende_del_horario_verano(self):
        obj = self.execution.GiscedataOmieSiomQueryExecution()
        config = self._configurar_control_8100(obj)
        for instante in (datetime(2026, 1, 7, 9, 7),
                         datetime(2026, 7, 7, 9, 7)):
            db = self._fake_db_exclusion(fecha=instante)
            with self.assertRaises(self.execution.ConsultaExcluidaOMIE):
                obj._comprobar_exclusion_8100(db, 3004, instante)
            expr, parametros = [x for x in db.sql if '::time' in x[0]][0]
            self.assertIn("interval '1 minute'", expr)
            self.assertEqual(parametros, (instante, 60))
        config.valores['siom_8100_timezone'] = 'CEST+1'
        with self.assertRaises(self.execution.SinConfiguracionExclusion8100):
            obj._comprobar_exclusion_8100(
                self._fake_db_exclusion(), 3004,
                datetime(2026, 11, 3, 10, 7))

    def test_controlador_8100_incluye_segundo_final(self):
        obj = self.execution.GiscedataOmieSiomQueryExecution()
        self._configurar_control_8100(obj)
        fecha = datetime(2026, 11, 3, 10, 0)
        with self.assertRaises(self.execution.ConsultaExcluidaOMIE):
            obj._comprobar_exclusion_8100(
                self._fake_db_exclusion(fecha=fecha,
                                        hora=time(10, 15, 0, 999999)),
                3004, fecha)
        self.assertIsNone(obj._comprobar_exclusion_8100(
            self._fake_db_exclusion(fecha=fecha, hora=time(10, 15, 1)),
            3004, fecha))

    def test_bloqueo_8100_vacio_reutiliza_anterior_y_config_invalida(self):
        obj = self.execution.GiscedataOmieSiomQueryExecution()
        config = self._configurar_control_8100(obj)
        config.valores['siom_8100_timezone'] = ''
        with self.assertRaises(self.execution.SinConfiguracionExclusion8100):
            obj._comprobar_exclusion_8100(
                self._fake_db_exclusion(), 3004, datetime(2026, 11, 3, 10, 7))
        config.valores['siom_8100_timezone'] = 'UTC+01:00'
        with self.assertRaises(self.execution.ConsultaExcluidaOMIE):
            obj._comprobar_exclusion_8100(
                self._fake_db_exclusion('vacia', viejo=True), 3004,
                datetime(2026, 11, 3, 10, 7))
        with self.assertRaises(self.execution.SinConfiguracionExclusion8100):
            obj._comprobar_exclusion_8100(
                self._fake_db_exclusion(), 3004,
                datetime(2026, 11, 3, 12, 7))  # snapshot caducado
        config.valores['siom_8100_max_age_seconds'] = 'invalido'
        with self.assertRaises(self.execution.SinConfiguracionExclusion8100):
            obj._comprobar_exclusion_8100(
                self._fake_db_exclusion(), 3004,
                datetime(2026, 11, 3, 10, 7))

    def test_8100_refresco_no_necesita_snapshot_aun_con_control_activo(self):
        obj = self.execution.GiscedataOmieSiomQueryExecution()
        self._configurar_control_8100(obj)
        db = self._fake_db_exclusion()
        self.assertIsNone(obj._comprobar_exclusion_8100(
            db, 8100, datetime(2026, 11, 3, 10, 7)))
        self.assertEqual(db.sql, [])


if __name__ == '__main__':
    unittest.main()
