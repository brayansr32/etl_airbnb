import time
import logger_config
from extraccion import Extraccion
from transformacion import Transformacion
from carga import Carga
from logger_config import get_logger


def ejecutar_etl():
    """Función principal que ejecuta el proceso ETL completo"""
    logger = get_logger("main")
    inicio = time.time()
    logger.info("Inicio del proceso ETL Airbnb Bogotá")
    
    # Instanciamos el extractor apuntando a nuestra base de datos local
    extractor = Extraccion(db_name="Airbnb")

    try:
        # Extracción
        extractor.conectar()
        df_listings, df_reviews, df_calendar = extractor.extraer_todo()

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
        logger.info(f"Revisa el detalle en el log: {logger_config.ruta_log_actual}")


if __name__ == "__main__":
    ejecutar_etl()
