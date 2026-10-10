import sqlite3
import pandas as pd
from logger_config import RAIZ_PROYECTO, get_logger


class Carga:
    """Clase para guardar los DataFrames limpios en SQLite y Excel."""

    def __init__(self, nombre_db="airbnb_analitica.db"):
        """Creamos una carpeta 'output' en la raíz del proyecto para guardar todo ahí"""
        self.carpeta_salida = RAIZ_PROYECTO / "output"
        self.carpeta_salida.mkdir(parents=True, exist_ok=True)
        self.ruta_db = self.carpeta_salida / nombre_db
        self.logger = get_logger(__name__)


    def cargar_sqlite(self, df, nombre_tabla):
        """Guarda el DataFrame en SQLite y cuenta las filas para verificar."""
        if df is None or df.empty:
            self.logger.warning(f"La tabla '{nombre_tabla}' no tiene datos para cargar.")
            return False

        conexion = None
        try:
            # Pasamos las fechas a texto para que SQLite no se confunda con las horas
            datos = df.copy()
            for col in datos.select_dtypes(include=["datetime", "datetimetz"]).columns:
                datos[col] = datos[col].dt.strftime("%Y-%m-%d")

            conexion = sqlite3.connect(self.ruta_db)
            
            # Guardamos por pedazos para no saturar la memoria
            datos.to_sql(
                nombre_tabla, 
                conexion, 
                if_exists="replace", 
                index=False, 
                chunksize=50000
            )

            # Verificamos que se haya cargado completo
            cursor = conexion.cursor()
            cursor.execute(f'SELECT COUNT(*) FROM "{nombre_tabla}"')
            conteo = cursor.fetchone()[0]

            if conteo == len(df):
                self.logger.info(f"Carga exitosa en SQLite: '{nombre_tabla}' con {conteo} registros.")
                return True
            else:
                self.logger.error(f"Faltan datos en '{nombre_tabla}'. Se esperaban {len(df)} pero hay {conteo}.")
                return False

        except Exception as e:
            self.logger.error(f"Error al cargar '{nombre_tabla}' en SQLite: {e}")
            return False
        finally:
            if conexion:
                conexion.close()


    def exportar_excel(self, df, nombre_archivo):
        """Exporta el DataFrame a un archivo .xlsx normal."""
        if df is None or df.empty:
            self.logger.warning(f"No hay datos para exportar a '{nombre_archivo}.xlsx'.")
            return False

        ruta = self.carpeta_salida / f"{nombre_archivo}.xlsx"
        try:
            # strings_to_urls=False porque Excel solo admite 65.530 hipervínculos por hoja y Listings trae
            # muchas URLs (fotos, perfil del anfitrión); así quedan como texto normal
            with pd.ExcelWriter(ruta, engine="xlsxwriter",
                                engine_kwargs={"options": {"strings_to_urls": False}}) as escritor:
                df.to_excel(escritor, index=False)

            if ruta.exists() and ruta.stat().st_size > 0:
                peso_mb = ruta.stat().st_size / (1024 * 1024)
                self.logger.info(f"Exportación exitosa: '{ruta.name}' guardado ({peso_mb:.1f} MB).")
                return True
            else:
                self.logger.error(f"El archivo '{ruta.name}' se creó pero parece estar vacío.")
                return False

        except Exception as e:
            self.logger.error(f"Error al exportar '{nombre_archivo}' a Excel: {e}")
            return False


    def ejecutar_carga(self, resultados):
        """Recibe el diccionario de la transformación y hace todas las cargas."""
        self.logger.info("INICIANDO FASE DE CARGA (SOLO 3 TABLAS)")

        # 1. Cargar estrictamente las 3 tablas a la base de datos SQLite
        self.logger.info("Insertando datos en SQLite...")
        tablas_sqlite = {
            "Listings_Limpio": resultados.get("listings"),
            "Reviews_Limpio": resultados.get("reviews"),
            "Calendar_Mensual": resultados.get("calendar_mensual"),
        }
        
        estado_sql = {}
        for nombre, df in tablas_sqlite.items():
            estado_sql[nombre] = self.cargar_sqlite(df, nombre)

        # 2. Exportar a Excel las mismas 3 tablas
        self.logger.info("Exportando datos a Excel (XLSX)...")
        tablas_excel = {
            "Listings_Transformado": resultados.get("listings"),
            "Reviews_Transformado": resultados.get("reviews"),
            "Calendar_Mensual_Transformado": resultados.get("calendar_mensual"),
        }
        
        for nombre, df in tablas_excel.items():
            self.exportar_excel(df, nombre)

        self.logger.info(f"CARGA FINALIZADA. Base de datos guardada en: {self.ruta_db.relative_to(RAIZ_PROYECTO)}")
        return estado_sql


if __name__ == "__main__":
    from extraccion import Extraccion
    from transformacion import Transformacion

    extractor = Extraccion(db_name="Airbnb")
    extractor.conectar()
    df_l, df_r, df_c = extractor.extraer_todo()
    extractor.cerrar()

    resultados = Transformacion().ejecutar_transformacion(df_l, df_r, df_c)
    Carga().ejecutar_carga(resultados)
