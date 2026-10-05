import pandas as pd
import sqlite3
from logger_config import get_logger

class Carga:
    """Clase para insertar datos transformados en SQLite y exportarlos a XLSX."""
    def __init__(self, db_name="airbnb_analitica.db"):
        self.db_path = f"../{db_name}"
        self.logger = get_logger(__name__)

    def cargar_sqlite(self, df, nombre_tabla):
        """Inserta el DataFrame en la base de datos SQLite y verifica la carga."""
        try:
            conexion = sqlite3.connect(self.db_path)
            # Insertar los datos en SQLite
            df.to_sql(nombre_tabla, conexion, if_exists='replace', index=False)
            
            # Verificar que los registros se hayan cargado correctamente
            cursor = conexion.cursor()
            cursor.execute(f"SELECT COUNT(*) FROM {nombre_tabla}")
            conteo = cursor.fetchone()[0]
            
            self.logger.info(f"Carga exitosa en SQLite: {conteo} registros insertados en la tabla '{nombre_tabla}'.")
            conexion.close()
        except Exception as e:
            self.logger.error(f"Error al cargar la tabla {nombre_tabla} en SQLite: {e}")

    def exportar_excel(self, df, nombre_archivo):
        """Exporta el DataFrame a un archivo Excel (.xlsx)."""
        ruta = f"../{nombre_archivo}.xlsx"
        try:
            # Excel tiene un límite de ~1 millón de filas. Protegemos el código si el DataFrame es más grande.
            if len(df) > 1000000:
                self.logger.warning(f"El DataFrame {nombre_archivo} supera el límite de Excel. Exportando los primeros 500,000 registros.")
                df.head(500000).to_excel(ruta, index=False)
            else:
                df.to_excel(ruta, index=False)
            self.logger.info(f"Exportación exitosa: archivo '{ruta}' generado correctamente.")
        except Exception as e:
            self.logger.error(f"Error al exportar {nombre_archivo} a Excel: {e}")

    def ejecutar_carga(self, df_listings, df_reviews, df_calendar):
        """Orquesta la ejecución de la carga y exportación."""
        self.logger.info("--- INICIANDO PROCESO DE CARGA ---")
        
        # 1. Cargar a la base de datos analítica SQLite
        self.cargar_sqlite(df_listings, "Listings_Limpio")
        self.cargar_sqlite(df_reviews, "Reviews_Limpio")
        self.cargar_sqlite(df_calendar, "Calendar_Limpio")
        
        # 2. Exportar a XLSX (Exportaremos Listings y Reviews. Calendar se trunca por el límite de Excel)
        self.exportar_excel(df_listings, "Listings_Transformado")
        self.exportar_excel(df_reviews, "Reviews_Transformado")
        
        self.logger.info("--- PROCESO DE CARGA FINALIZADO CON ÉXITO ---") 


# --- Bloque de prueba de todo el flujo ETL ---
if __name__ == "__main__":
    from extraccion import Extraccion
    from transformacion import Transformacion
    
    # 1. Extracción
    extractor = Extraccion(db_name="Airbnb")
    extractor.conectar()
    df_l = extractor.extraer_datos("Listings")
    df_r = extractor.extraer_datos("Reviews")
    df_c = extractor.extraer_datos("Calendar")
    
    # 2. Transformación
    transformador = Transformacion()
    df_l_limpio, df_r_limpio, df_c_limpio = transformador.ejecutar_transformacion(df_l, df_r, df_c)
    
    # 3. Carga
    cargador = Carga()
    cargador.ejecutar_carga(df_l_limpio, df_r_limpio, df_c_limpio)
