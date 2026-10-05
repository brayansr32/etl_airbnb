import pymongo
import pandas as pd
from logger_config import get_logger

class Extraccion:
    def __init__(self, db_name="Airbnb", host="localhost", port=27017):
        self.db_name = db_name
        self.host = host
        self.port = port
        self.client = None
        self.db = None
        
        self.logger = get_logger(__name__)

    # Requisito 1: establecer conexión con la base de datos
    def conectar(self):
        try:
            self.client = pymongo.MongoClient(self.host, self.port)
            self.db = self.client[self.db_name]
            # Requisito 4: registrar en un log la conexión realizada
            self.logger.info(f"Conexión exitosa a la base de datos MongoDB local: {self.db_name}")
        except Exception as e:
            self.logger.error(f"Error al conectar a MongoDB: {e}")
            raise

    # Requisito 2 y 3: consultar cada colección y cargar en DataFrames
    def extraer_datos(self, nombre_coleccion):
        try:
            coleccion = self.db[nombre_coleccion]
            # Consultamos la colección (excluyendo el _id propio de Mongo)
            datos = list(coleccion.find({}, {"_id": 0}))
            
            # Cargamos los datos en un DataFrame de pandas
            df = pd.DataFrame(datos)
            
            # Requisito 4: registrar en log la cantidad de registros extraídos
            self.logger.info(f"Extracción exitosa: {len(df)} registros extraídos de la colección '{nombre_coleccion}'")
            return df
        except Exception as e:
            self.logger.error(f"Error al extraer la colección {nombre_coleccion}: {e}")
            return None


# --- PRUEBA DE LA CLASE ---
if __name__ == "__main__":
    # Instanciamos la clase
    extractor = Extraccion(db_name="Airbnb")
    
    # Establecemos conexión
    extractor.conectar()
    
    # Extraemos las 3 colecciones a DataFrames
    df_listings = extractor.extraer_datos("Listings")
    df_reviews = extractor.extraer_datos("Reviews")
    df_calendar = extractor.extraer_datos("Calendar")
