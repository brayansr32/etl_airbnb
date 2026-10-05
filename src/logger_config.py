"""
Módulo centralizado de logs para todo el proceso ETL.

Genera UN archivo por ejecución (logs/log_YYYYMMDD_HHMMSS.txt) y además muestra
los mensajes por consola. Todos los módulos (extraccion, transformacion, carga,
main) comparten el mismo archivo porque cuelgan del mismo logger raíz "etl".

Las rutas se calculan a partir de la ubicación de este archivo, por lo que el
proyecto funciona sin importar desde qué carpeta se ejecute.
"""
import logging
from datetime import datetime
from pathlib import Path

# Raíz del proyecto (carpeta que contiene src/, notebooks/, logs/, ...)
RAIZ_PROYECTO = Path(__file__).resolve().parent.parent
CARPETA_LOGS = RAIZ_PROYECTO / "logs"

_NOMBRE_LOGGER_RAIZ = "etl"
_FORMATO = "%(asctime)s - %(levelname)s - [%(name)s] %(message)s"
_FORMATO_FECHA = "%Y-%m-%d %H:%M:%S"

# Ruta del archivo de log de la ejecución actual (se fija la primera vez que se pide un logger)
ruta_log_actual = None


def _configurar_logger_raiz():
    """Crea los handlers (archivo + consola) una sola vez por ejecución."""
    global ruta_log_actual
    logger_raiz = logging.getLogger(_NOMBRE_LOGGER_RAIZ)
    if logger_raiz.handlers:
        return logger_raiz

    CARPETA_LOGS.mkdir(parents=True, exist_ok=True)
    # Se incluyen los segundos para que dos ejecuciones en el mismo minuto no compartan archivo
    ruta_log_actual = CARPETA_LOGS / f"log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"

    formato = logging.Formatter(_FORMATO, datefmt=_FORMATO_FECHA)
    handler_archivo = logging.FileHandler(ruta_log_actual, encoding="utf-8")
    handler_archivo.setFormatter(formato)
    handler_consola = logging.StreamHandler()
    handler_consola.setFormatter(formato)

    logger_raiz.setLevel(logging.INFO)
    logger_raiz.addHandler(handler_archivo)
    logger_raiz.addHandler(handler_consola)
    # Evita que los mensajes se dupliquen si el entorno (p. ej. Jupyter) ya configuró el logger raíz de Python
    logger_raiz.propagate = False
    return logger_raiz


def get_logger(nombre):
    """
    Devuelve un logger hijo del logger central del ETL.

    Parámetros:
        nombre: normalmente __name__ del módulo que lo solicita.
    """
    _configurar_logger_raiz()
    return logging.getLogger(f"{_NOMBRE_LOGGER_RAIZ}.{nombre}")
