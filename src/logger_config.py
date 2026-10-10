"""
Configuración de logs para el proceso ETL.
Crea un archivo de texto por cada vez que se corre el programa en la carpeta logs.
"""
import logging
from datetime import datetime
from pathlib import Path


# Buscamos la carpeta raíz para guardar los logs allí
RAIZ_PROYECTO = Path(__file__).resolve().parent.parent
CARPETA_LOGS = RAIZ_PROYECTO / "logs"

_NOMBRE_LOGGER_RAIZ = "etl"
_FORMATO = "%(asctime)s - %(levelname)s [%(name)s] %(message)s"
_FORMATO_FECHA = "%Y-%m-%d %H:%M:%S"

ruta_log_actual = None

def _configurar_logger_raiz():
    global ruta_log_actual
    logger_raiz = logging.getLogger(_NOMBRE_LOGGER_RAIZ)
    
    # Si el logger ya tiene configuración, no la repetimos
    if logger_raiz.handlers:
        return logger_raiz

    CARPETA_LOGS.mkdir(parents=True, exist_ok=True)
    
    # Nombramos el archivo con la fecha y hora de la ejecución
    fecha_hora = datetime.now().strftime('%Y%m%d_%H%M%S')
    ruta_log_actual = CARPETA_LOGS / f"log_{fecha_hora}.txt"

    formato = logging.Formatter(_FORMATO, datefmt=_FORMATO_FECHA)
    
    handler_archivo = logging.FileHandler(ruta_log_actual, encoding="utf-8")
    handler_archivo.setFormatter(formato)
    
    handler_consola = logging.StreamHandler()
    handler_consola.setFormatter(formato)

    logger_raiz.setLevel(logging.INFO)
    logger_raiz.addHandler(handler_archivo)
    logger_raiz.addHandler(handler_consola)
    
    return logger_raiz

def get_logger(nombre):
    """Devuelve un logger hijo con el nombre del archivo actual."""
    _configurar_logger_raiz()
    return logging.getLogger(f"{_NOMBRE_LOGGER_RAIZ}.{nombre}")
