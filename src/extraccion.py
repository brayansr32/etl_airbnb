import pandas as pd
import pymongo
from pymongo.errors import PyMongoError
from logger_config import get_logger


class Extraccion:
    """Clase para conectarse a MongoDB local y extraer las colecciones
    Listings, Reviews y Calendar como DataFrames"""
    TAMANO_BLOQUE = 100_000 # Se leen los registros en lotes de 100000 debido a la cantidad de registros

    def __init__(self, db_name = "Airbnb", host = "localhost", port = 27017, timeout_ms = 5000):
        # Inicializamos las credenciales por defecto para la BD local
        self.db_name = db_name
        self.host = host
        self.port = port
        self.timeout_ms = timeout_ms
        self.client = None
        self.db = None
        self.logger = get_logger(__name__)


    def conectar(self):
        """Establece la conexión con MongoDB"""
        try:
            self.client = pymongo.MongoClient(
                self.host,
                self.port,
                serverSelectionTimeoutMS=self.timeout_ms
            )
            self.db = self.client[self.db_name]
            self.logger.info(f"Conexión a MongoDB ({self.host}:{self.port}), base de datos '{self.db_name}'.")
        except PyMongoError as e:
            self.logger.error(f"Error conectando a MongoDB: {e}")
            raise


    def listar_colecciones(self):
        """Lista las colecciones disponibles en la base de datos"""
        colecciones = self.db.list_collection_names()
        self.logger.info(f"Colecciones disponibles: {colecciones}")
        return colecciones


    def extraer_datos(self, nombre_coleccion, limite=None):
        """Consulta una colección completa y la pasa a un DataFrame.
        Excluimos el '_id' porque no se usa para el análisis"""
        try:
            if nombre_coleccion not in self.db.list_collection_names():
                raise ValueError(f"La colección '{nombre_coleccion}' no existe.")

            cursor = self.db[nombre_coleccion].find({}, {"_id": 0}, batch_size=self.TAMANO_BLOQUE)
            if limite:
                cursor = cursor.limit(int(limite))

            bloques = []
            bloque_actual = []
            for documento in cursor:
                bloque_actual.append(documento)
                if len(bloque_actual) >= self.TAMANO_BLOQUE:
                    bloques.append(pd.DataFrame(bloque_actual))
                    bloque_actual = []

            # Agregar lo que quedó pendiente en el último bloque
            if bloque_actual:
                bloques.append(pd.DataFrame(bloque_actual))

            # Concatenar todos los bloques en un solo DataFrame
            if bloques:
                df = pd.concat(bloques, ignore_index=True)
            else:
                df = pd.DataFrame()

            # Informar la cantidad de registros extraídos
            self.logger.info(f"Se extrajeron {len(df)} registros de la colección '{nombre_coleccion}'.")
            
            # Alertar si la colección está vacía
            if df.empty:
                self.logger.warning(f"La colección '{nombre_coleccion}' está vacía.")
            
            return df # DataFrame con los datos extraídos
        except Exception as e:
            self.logger.error(f"Fallo al extraer '{nombre_coleccion}': {e}")
            raise


    def extraer_todo(self, limite=None):
        """Extrae las tres colecciones Listings, Reviews y Calendar"""
        df_listings = self.extraer_datos("Listings", limite)
        df_reviews = self.extraer_datos("Reviews", limite)
        df_calendar = self.extraer_datos("Calendar", limite)
        return df_listings, df_reviews, df_calendar


    def cerrar(self):
        """Cierra la conexión con MongoDB"""
        if self.client is not None:
            self.client.close()
            self.client = None
            self.db = None
            self.logger.info("Conexión a MongoDB cerrada.")


# Ejecución del script
if __name__ == "__main__":
    extractor = Extraccion(db_name="Airbnb")
    extractor.conectar()
    df_listings, df_reviews, df_calendar = extractor.extraer_todo()
    extractor.cerrar()
