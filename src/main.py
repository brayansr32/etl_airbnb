"""
Punto de entrada del proceso ETL completo: MongoDB -> pandas -> SQLite / XLSX.

Uso (desde la raíz del proyecto, con el entorno virtual activado):
    python src/main.py                      # ETL completo
    python src/main.py --muestra 5000       # prueba rápida con solo 5000 registros por colección
    python src/main.py --db Airbnb --host localhost --puerto 27017
"""
import argparse
import sys
import time

import logger_config
from carga import Carga
from extraccion import Extraccion
from logger_config import get_logger
from transformacion import Transformacion


def ejecutar_etl(db_name="Airbnb", host="localhost", puerto=27017, muestra=None):
    """
    Ejecuta las tres fases del ETL en orden.

    Devuelve:
        True si todo el proceso terminó bien; False si hubo algún error.
    """
    logger = get_logger("main")
    inicio = time.time()
    logger.info("=== INICIO DEL PROCESO ETL AIRBNB BOGOTÁ ===")
    extractor = Extraccion(db_name=db_name, host=host, port=puerto)

    try:
        # 1. Extracción
        extractor.conectar()
        df_listings, df_reviews, df_calendar = extractor.extraer_todo(limite=muestra)

        # 2. Transformación
        resultados = Transformacion().ejecutar_transformacion(df_listings, df_reviews, df_calendar)

        # 3. Carga
        estado = Carga().ejecutar_carga(resultados)
        exito = all(estado.values())
    except Exception as e:
        logger.error(f"El proceso ETL se detuvo por un error: {e}")
        return False
    finally:
        extractor.cerrar()

    duracion = time.time() - inicio
    logger.info(f"=== FIN DEL PROCESO ETL ({'OK' if exito else 'CON ERRORES'}) en {duracion:.1f} segundos ===")
    if logger_config.ruta_log_actual:
        logger.info(f"Log de esta ejecución: {logger_config.ruta_log_actual}")
    return exito


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Proceso ETL de los datasets de Airbnb Bogotá.")
    parser.add_argument("--db", default="Airbnb", help="Nombre de la base de datos en MongoDB (por defecto: Airbnb)")
    parser.add_argument("--host", default="localhost", help="Servidor de MongoDB (por defecto: localhost)")
    parser.add_argument("--puerto", type=int, default=27017, help="Puerto de MongoDB (por defecto: 27017)")
    parser.add_argument("--muestra", type=int, default=None,
                        help="Procesar solo N registros por colección (para pruebas rápidas)")
    argumentos = parser.parse_args()

    ok = ejecutar_etl(argumentos.db, argumentos.host, argumentos.puerto, argumentos.muestra)
    sys.exit(0 if ok else 1)
