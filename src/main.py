import argparse
import time
import logger_config
from extraccion import Extraccion
from transformacion import Transformacion
from carga import Carga
from logger_config import get_logger


def ejecutar_etl(muestra=None):
    """Función principal que ejecuta el proceso ETL completo.
    Si se pasa 'muestra', solo se extraen esos registros de cada colección (sirve para probar rápido)"""
    logger = get_logger("main")
    inicio = time.time()
    logger.info("Inicio del proceso ETL Airbnb Bogotá")
    
    # Instanciamos el extractor apuntando a nuestra base de datos local
    extractor = Extraccion(db_name="Airbnb")

    try:
        # Extracción
        extractor.conectar()
        df_listings, df_reviews, df_calendar = extractor.extraer_todo(limite=muestra)

        # Transformación
        transformador = Transformacion()
        resultados = transformador.ejecutar_transformacion(df_listings, df_reviews, df_calendar)

        # Carga
        cargador = Carga()
        cargador.ejecutar_carga(resultados)

    except Exception as e:
        logger.error(f"El proceso ETL falló por un error: {e}")
    finally:
        extractor.cerrar()

    duracion = time.time() - inicio
    logger.info(f"Fin del proceso. Duración: {duracion:.1f} segundos")
    
    if logger_config.ruta_log_actual:
        logger.info(f"Revisa el detalle en el log: {logger_config.ruta_log_actual.relative_to(logger_config.RAIZ_PROYECTO)}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ETL de Airbnb Bogotá")
    parser.add_argument("--muestra", type=int, default=None,
                        help="cantidad de registros por colección para una prueba rápida")
    args = parser.parse_args()
    ejecutar_etl(args.muestra)
