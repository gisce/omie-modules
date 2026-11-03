# -*- coding: utf-8 -*-
"""Evaluacion PURA de intervalos UTC para la futura consulta SIOM 8100.

Fase C, deliberadamente INERTE:
- No interpreta columnas ENCOL 8100 ni hace conversiones automaticas desde OMIE.
- No lee observaciones, ORM, configuracion ni servicios.
- No se integra en ejecutar_consulta() ni autoriza/deniega peticiones.
- Los intervalos recibidos han de estar normalizados *explicitamente* a UTC.
- El significado inclusivo/exclusivo del fin es obligatorio, no inferido.

Compatible con Python 2.7 y Python 3.x, sin dependencias de terceros.
"""
from __future__ import absolute_import

from datetime import datetime, timedelta
import re

try:
    string_types = (basestring,)
except NameError:
    string_types = (str,)

MAX_INTERVALOS = 5000

# Un valor de texto se interpreta como UTC YA NORMALIZADO. No se aceptan
# offsets en texto: el parser ENCOL futuro debera resolver la zona de OMIE.
_PATRON_UTC = re.compile(
    r'^\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z?$')


class IntervaloExclusionInvalido(ValueError):
    """La entrada no se puede evaluar de forma segura en UTC."""


def normalizar_instante_utc(valor):
    """Normaliza un datetime o texto UTC a datetime naive UTC.

    Los datetime aware pueden incorporar offsets: se convierten a UTC sin
    recurrir a la zona horaria del servidor. Datetime naive y textos SIN zona
    SOLO se admiten si el llamador garantiza que ya estan en UTC.

    Nunca invocar directamente con fechas locales o campos ENCOL sin validar.
    """
    if isinstance(valor, datetime):
        try:
            desplazamiento = valor.utcoffset() if valor.tzinfo is not None else None
            if desplazamiento is None:
                if valor.tzinfo is not None:
                    raise IntervaloExclusionInvalido('Timezone no resoluble')
                return valor
            if not isinstance(desplazamiento, timedelta):
                raise IntervaloExclusionInvalido('Offset temporal invalido')
            # Conversion matematica explicita: nunca usa el timezone del host.
            return valor.replace(tzinfo=None) - desplazamiento
        except (OverflowError, TypeError) as exc:
            raise IntervaloExclusionInvalido('Instante UTC fuera de rango: %s' % exc)
    if not isinstance(valor, string_types):
        raise IntervaloExclusionInvalido('Instante UTC debe ser datetime o texto UTC')
    if not _PATRON_UTC.match(valor):
        raise IntervaloExclusionInvalido('Formato UTC no reconocido: se exige ISO UTC')
    limpio = valor[:-1] if valor.endswith('Z') else valor
    limpio = limpio.replace('T', ' ')
    formato = '%Y-%m-%d %H:%M:%S.%f' if '.' in limpio else '%Y-%m-%d %H:%M:%S'
    try:
        return datetime.strptime(limpio, formato)
    except (ValueError, TypeError, OverflowError) as exc:
        raise IntervaloExclusionInvalido('Instante UTC incorrecto: %s' % exc)


def normalizar_intervalos_utc(intervalos):
    """Valida TODOS los intervalos sin omitir silenciosamente ninguno.

    Cada entrada es un dict con SOLO ``inicio_utc`` y ``fin_utc``. Es un
    formato INTERNO, no el supuesto formato ENCOL de OMIE.
    Devuelve tuplas (inicio, fin) ordenadas, nunca permisos de consulta.
    """
    if not isinstance(intervalos, (list, tuple)):
        raise IntervaloExclusionInvalido('Los intervalos deben ser lista o tupla')
    if len(intervalos) > MAX_INTERVALOS:
        raise IntervaloExclusionInvalido('Demasiados intervalos para evaluar')
    normalizados = []
    for indice, intervalo in enumerate(intervalos):
        if not isinstance(intervalo, dict) or set(intervalo) != set(('inicio_utc', 'fin_utc')):
            raise IntervaloExclusionInvalido(
                'Intervalo %s: se requieren inicio_utc y fin_utc exclusivamente' % indice)
        inicio = normalizar_instante_utc(intervalo['inicio_utc'])
        fin = normalizar_instante_utc(intervalo['fin_utc'])
        if inicio >= fin:
            raise IntervaloExclusionInvalido(
                'Intervalo %s: fin no posterior al inicio' % indice)
        normalizados.append((inicio, fin))
    return sorted(normalizados)


def consolidar_intervalos_utc(intervalos):
    """Une intervalos solapados o adyacentes; no infiere horario de OMIE.

    El argumento admite el formato dict interno de normalizar_intervalos_utc.
    Devolver intervalos disjuntos evita liberar prematuramente una ventana
    cuando otra ventana adyacente/solapada sigue activa.
    """
    normalizados = normalizar_intervalos_utc(intervalos)
    consolidados = []
    for inicio, fin in normalizados:
        if not consolidados or inicio > consolidados[-1][1]:
            consolidados.append((inicio, fin))
        else:
            anterior = consolidados[-1]
            if fin > anterior[1]:
                consolidados[-1] = (anterior[0], fin)
    return consolidados


def evaluar_ventanas_utc(intervalos, instante_utc, fin_inclusivo=None):
    """Evalua pertenencia temporal; NUNCA determina si un SOAP esta permitido.

    ``fin_inclusivo`` debe fijarse EXPLICITAMENTE en True/False cuando OMIE
    confirme la regla de frontera. La salida solo describe coincidencia en
    ventanas *normalizadas por el llamador*. Con cero intervalos, coincide=False
    NO significa que OMIE haya publicado ausencia de restricciones.
    """
    if type(fin_inclusivo) is not bool:
        raise IntervaloExclusionInvalido('Confirmar expresamente fin_inclusivo')
    ahora = normalizar_instante_utc(instante_utc)
    unificados = consolidar_intervalos_utc(intervalos)
    for inicio, fin in unificados:
        dentro = inicio <= ahora <= fin if fin_inclusivo else inicio <= ahora < fin
        if dentro:
            return {
                'coincide': True,
                'inicio_utc': inicio,
                'fin_utc': fin,
                'intervalos_consolidados': len(unificados),
                'solo_evaluacion': True,
            }
        if ahora < inicio:
            break
    return {
        'coincide': False,
        'inicio_utc': None,
        'fin_utc': None,
        'intervalos_consolidados': len(unificados),
        'solo_evaluacion': True,
    }
