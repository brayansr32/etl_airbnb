import pandas as pd
import logging
import os
from datetime import datetime

class Transformacion:
    """
    Clase encargada de limpiar y transformar los DataFrames extraídos.
    """
    def __init__(self):
        self.configurar_logs()

    def configurar_logs(self):
        """Configura el sistema de logs para registrar las transformaciones."""
        os.makedirs("../logs", exist_ok=True)
        log_filename = f"../logs/log_{datetime.now().strftime('%Y%m%d_%H%M')}.txt"
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[logging.FileHandler(log_filename), logging.StreamHandler()]
        )
        self.logger = logging.getLogger(__name__)

    def limpiar_nulos_duplicados(self, df, nombre_df):
        """Elimina duplicados y valores completamente nulos."""
        if df is None or df.empty:
            self.logger.warning(f"El DataFrame {nombre_df} está vacío o es nulo.")
            return df
            
        registros_antes = len(df)
        
        # Eliminar duplicados convirtiendo a string temporalmente para evitar errores con listas
        df = df.loc[~df.astype(str).duplicated()]
        
        # Eliminar filas donde todas las columnas sean nulas
        df = df.dropna(how='all')
        
        registros_despues = len(df)
        self.logger.info(f"[{nombre_df}] Limpieza finalizada: de {registros_antes} a {registros_despues} registros.")
        return df

    def normalizar_precios(self, df, columna):
        """Elimina símbolos como $ y , y convierte el precio a numérico."""
        if columna in df.columns:
            try:
                # Se eliminan caracteres no numéricos excepto el punto decimal
                df[columna] = df[columna].astype(str).str.replace(r'[\$,]', '', regex=True)
                df[columna] = pd.to_numeric(df[columna], errors='coerce')
                self.logger.info(f"Columna de precio '{columna}' normalizada correctamente.")
            except Exception as e:
                self.logger.error(f"Error al normalizar '{columna}': {e}")
        return df

    def transformar_fechas(self, df, columna):
        """Convierte fechas a YYYY-MM-DD y deriva año, mes, día y trimestre."""
        if columna in df.columns:
            try:
                df[columna] = pd.to_datetime(df[columna], errors='coerce').dt.date
                df[columna] = pd.to_datetime(df[columna]) # Asegurar formato datetime
                
                # Derivación de variables
                df['año'] = df[columna].dt.year
                df['mes'] = df[columna].dt.month
                df['día'] = df[columna].dt.day
                df['trimestre'] = df[columna].dt.quarter
                self.logger.info(f"Fechas transformadas y variables derivadas generadas para '{columna}'.")
            except Exception as e:
                self.logger.error(f"Error al transformar fechas en '{columna}': {e}")
        return df

    def categorizar_precios(self, df, columna):
        """Categoriza los precios en rangos: Económico, Medio, Alto, Lujo."""
        if columna in df.columns:
            try:
                rangos = [0, 50, 150, 300, float('inf')]
                etiquetas = ['Económico', 'Medio', 'Alto', 'Lujo']
                df['rango_precio'] = pd.cut(df[columna], bins=rangos, labels=etiquetas)
                self.logger.info("Precios categorizados en la columna 'rango_precio'.")
            except Exception as e:
                self.logger.error(f"Error al categorizar precios: {e}")
        return df

    def desanidar_campos(self, df, columna):
        """Limpia caracteres especiales (corchetes, comillas) de campos anidados."""
        if columna in df.columns:
            try:
                df[columna] = df[columna].astype(str).str.replace(r'[\[\]"\{\}]', '', regex=True)
                self.logger.info(f"Campo anidado '{columna}' limpiado exitosamente.")
            except Exception as e:
                self.logger.error(f"Error al desanidar '{columna}': {e}")
        return df

    def ejecutar_transformacion(self, df_listings, df_reviews, df_calendar):
        """Orquesta la ejecución de todas las transformaciones."""
        self.logger.info("--- INICIANDO PROCESO DE TRANSFORMACIÓN ---")
        
        # Transformaciones para LISTINGS
        self.logger.info("Transformando LISTINGS...")
        df_listings = self.limpiar_nulos_duplicados(df_listings, "Listings")
        df_listings = self.normalizar_precios(df_listings, 'price')
        df_listings = self.categorizar_precios(df_listings, 'price') 
        df_listings = self.desanidar_campos(df_listings, 'amenities')

        # Transformaciones para CALENDAR
        self.logger.info("Transformando CALENDAR...")
        df_calendar = self.limpiar_nulos_duplicados(df_calendar, "Calendar")
        df_calendar = self.normalizar_precios(df_calendar, 'price')
        df_calendar = self.transformar_fechas(df_calendar, 'date')

        # Transformaciones para REVIEWS
        self.logger.info("Transformando REVIEWS...")
        df_reviews = self.limpiar_nulos_duplicados(df_reviews, "Reviews")
        df_reviews = self.transformar_fechas(df_reviews, 'date')
        
        self.logger.info("--- TRANSFORMACIÓN FINALIZADA CON ÉXITO ---")
        return df_listings, df_reviews, df_calendar

# --- Bloque de prueba ---
if __name__ == "__main__":
    from extraccion import Extraccion
    
    # 1. Extraer datos (usando tu clase del Paso 1)
    extractor = Extraccion(db_name="Airbnb")
    extractor.conectar()
    df_list = extractor.extraer_datos("Listings")
    df_rev = extractor.extraer_datos("Reviews")
    df_cal = extractor.extraer_datos("Calendar")
    
    # 2. Transformar datos
    transformador = Transformacion()
    df_list_limpio, df_rev_limpio, df_cal_limpio = transformador.ejecutar_transformacion(df_list, df_rev, df_cal)
