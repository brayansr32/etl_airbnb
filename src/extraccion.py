"""
Fase 1 del ETL: conexión a MongoDB y extracción de las colecciones a DataFrames.
"""
import pandas as pd
import pymongo
from pymongo.errors import PyMongoError

from logger_config import get_logger


class Extraccion:
    """
    Se conecta a la base de datos MongoDB local y extrae sus colecciones
    (Listings, Reviews y Calendar) como DataFrames de pandas.

    Cada acción importante (conexión, cantidad de registros extraídos, errores)
    queda registrada en el log de la ejecución.

    Ejemplo:
        extractor = Extraccion(db_name="Airbnb")
        extractor.conectar()
        df_listings = extractor.extraer_datos("Listings")
        extractor.cerrar()
    """

    # Cantidad de documentos que se leen de Mongo por bloque. Calendar tiene millones de
    # registros; construir el DataFrame por bloques evita tener todos los diccionarios
    # de Python en memoria a la vez.
    TAMANO_BLOQUE = 100_000

    def __init__(self, db_name="Airbnb", host="localhost", port=27017, timeout_ms=5000):
        """
        Parámetros:
            db_name: nombre de la base de datos en MongoDB.
            host: servidor de MongoDB.
            port: puerto de MongoDB.
            timeout_ms: tiempo máximo (ms) de espera para encontrar el servidor.
        """
        self.db_name = db_name
        self.host = host
        self.port = port
        self.timeout_ms = timeout_ms
        self.client = None
        self.db = None
        self.logger = get_logger(__name__)

    def conectar(self):
        """
        Establece la conexión con MongoDB y la valida con un 'ping'.

        MongoClient conecta de forma diferida: sin el ping, una base apagada solo
        fallaría en la primera consulta y el log diría "conexión exitosa" sin serlo.
        Lanza la excepción original si no se logra conectar.
        """
        try:
            self.client = pymongo.MongoClient(self.host, self.port, serverSelectionTimeoutMS=self.timeout_ms)
            self.client.admin.command("ping")
            self.db = self.client[self.db_name]
            self.logger.info(f"Conexión exitosa a MongoDB ({self.host}:{self.port}), base de datos '{self.db_name}'.")
        except PyMongoError as e:
            self.logger.error(f"No se pudo conectar a MongoDB en {self.host}:{self.port}: {e}")
            raise

    def listar_colecciones(self):
        """Devuelve los nombres de las colecciones de la base de datos."""
        self._verificar_conexion()
        colecciones = self.db.list_collection_names()
        self.logger.info(f"Colecciones disponibles en '{self.db_name}': {colecciones}")
        return colecciones

    def extraer_datos(self, nombre_coleccion, limite=None):
        """
        Consulta una colección completa y la carga en un DataFrame de pandas.

        Se excluye el campo '_id' propio de Mongo porque no aporta información de negocio.

        Parámetros:
            nombre_coleccion: nombre de la colección ('Listings', 'Reviews' o 'Calendar').
            limite: si se indica, solo se leen los primeros N documentos (útil para pruebas rápidas).

        Devuelve:
            DataFrame con los documentos. Lanza excepción si la colección no existe o la consulta falla.
        """
        self._verificar_conexion()
        try:
            if nombre_coleccion not in self.db.list_collection_names():
                raise ValueError(f"La colección '{nombre_coleccion}' no existe en la base '{self.db_name}'.")

            cursor = self.db[nombre_coleccion].find({}, {"_id": 0}, batch_size=self.TAMANO_BLOQUE)
            if limite:
                cursor = cursor.limit(int(limite))

            bloques, bloque_actual = [], []
            for documento in cursor:
                bloque_actual.append(documento)
                if len(bloque_actual) >= self.TAMANO_BLOQUE:
                    bloques.append(pd.DataFrame(bloque_actual))
                    bloque_actual = []
            if bloque_actual:
                bloques.append(pd.DataFrame(bloque_actual))

            df = pd.concat(bloques, ignore_index=True) if bloques else pd.DataFrame()

            self.logger.info(
                f"Extracción exitosa: {len(df)} registros y {df.shape[1]} columnas "
                f"extraídos de la colección '{nombre_coleccion}'."
            )
            if df.empty:
                self.logger.warning(f"La colección '{nombre_coleccion}' no contiene registros.")
            return df
        except Exception as e:
            self.logger.error(f"Error al extraer la colección '{nombre_coleccion}': {e}")
            raise

    def extraer_todo(self, limite=None):
        """
        Extrae las tres colecciones del taller.

        Devuelve:
            Tupla (df_listings, df_reviews, df_calendar).
        """
        df_listings = self.extraer_datos("Listings", limite)
        df_reviews = self.extraer_datos("Reviews", limite)
        df_calendar = self.extraer_datos("Calendar", limite)
        return df_listings, df_reviews, df_calendar

    def cerrar(self):
        """Cierra la conexión con MongoDB."""
        if self.client is not None:
            self.client.close()
            self.client = None
            self.db = None
            self.logger.info("Conexión a MongoDB cerrada.")

    def _verificar_conexion(self):
        """Evita consultar sin haber llamado antes a conectar()."""
        if self.db is None:
            raise RuntimeError("No hay conexión activa. Llama primero a Extraccion.conectar().")


if __name__ == "__main__":
    extractor = Extraccion(db_name="Airbnb")
    extractor.conectar()
    df_listings, df_reviews, df_calendar = extractor.extraer_todo()
    extractor.cerrar()
