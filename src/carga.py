"""
Fase 3 del ETL: carga de los datos transformados en SQLite y exportación a XLSX.
"""
import re
import sqlite3
from pathlib import Path

import pandas as pd
from openpyxl import load_workbook

from logger_config import RAIZ_PROYECTO, get_logger


class Carga:
    """
    Inserta los DataFrames transformados en una base de datos analítica SQLite,
    verifica que los registros se hayan cargado y exporta los datos a archivos XLSX.

    Los archivos se generan en la carpeta 'output/' de la raíz del proyecto, sin importar
    desde dónde se ejecute el código.

    Ejemplo:
        cargador = Carga()
        cargador.ejecutar_carga(resultados)   # resultados = Transformacion().ejecutar_transformacion(...)
    """

    # Límite real de filas de una hoja de Excel (1 fila se usa para los encabezados)
    MAX_FILAS_EXCEL = 1_048_575
    # Límite de caracteres por celda en Excel
    MAX_CARACTERES_CELDA = 32_000
    # Filas por bloque al insertar en SQLite (evita construir una sola inserción gigante)
    TAMANO_BLOQUE_SQL = 50_000

    def __init__(self, nombre_db="airbnb_analitica.db", carpeta_salida=None):
        """
        Parámetros:
            nombre_db: nombre del archivo SQLite que se creará.
            carpeta_salida: carpeta donde se guardan la base de datos y los XLSX (por defecto <proyecto>/output).
        """
        self.carpeta_salida = Path(carpeta_salida) if carpeta_salida else RAIZ_PROYECTO / "output"
        self.carpeta_salida.mkdir(parents=True, exist_ok=True)
        self.ruta_db = self.carpeta_salida / nombre_db
        self.logger = get_logger(__name__)

    # ------------------------------------------------------------------
    # SQLite
    # ------------------------------------------------------------------
    def cargar_sqlite(self, df, nombre_tabla):
        """
        Inserta un DataFrame en una tabla SQLite (la reemplaza si ya existe) y verifica la carga.

        La verificación compara la cantidad de filas del DataFrame con el conteo real
        de la tabla (SELECT COUNT(*)).

        Devuelve:
            True si la carga fue correcta y verificada; False en caso contrario.
        """
        if df is None or df.empty:
            self.logger.warning(f"No hay datos para cargar en la tabla '{nombre_tabla}'.")
            return False

        self._validar_nombre_tabla(nombre_tabla)
        conexion = None
        try:
            datos = self._preparar_para_sql(df)
            conexion = sqlite3.connect(self.ruta_db)
            datos.to_sql(
                nombre_tabla, conexion, if_exists="replace", index=False, chunksize=self.TAMANO_BLOQUE_SQL
            )

            # Verificación: lo insertado debe coincidir con lo enviado
            cursor = conexion.cursor()
            cursor.execute(f'SELECT COUNT(*) FROM "{nombre_tabla}"')
            conteo = cursor.fetchone()[0]

            if conteo == len(df):
                self.logger.info(
                    f"Carga verificada en SQLite: {conteo} registros en la tabla '{nombre_tabla}' "
                    f"(coincide con el DataFrame de origen)."
                )
                return True
            self.logger.error(
                f"Carga INCOMPLETA en '{nombre_tabla}': se esperaban {len(df)} registros y hay {conteo}."
            )
            return False
        except Exception as e:
            self.logger.error(f"Error al cargar la tabla '{nombre_tabla}' en SQLite: {e}")
            return False
        finally:
            if conexion is not None:
                conexion.close()

    # ------------------------------------------------------------------
    # XLSX
    # ------------------------------------------------------------------
    def exportar_excel(self, df, nombre_archivo):
        """
        Exporta un DataFrame a un archivo .xlsx y verifica que el archivo se haya generado.

        Si el DataFrame supera el límite de filas de Excel, se reparte en varias hojas
        (Datos_1, Datos_2, ...) en lugar de truncar la información.

        Devuelve:
            Ruta del archivo generado, o None si falló.
        """
        if df is None or df.empty:
            self.logger.warning(f"No hay datos para exportar al archivo '{nombre_archivo}.xlsx'.")
            return None

        ruta = self.carpeta_salida / f"{nombre_archivo}.xlsx"
        try:
            datos = self._preparar_para_excel(df)
            n_hojas = (len(datos) - 1) // self.MAX_FILAS_EXCEL + 1
            if n_hojas > 1:
                self.logger.warning(
                    f"'{nombre_archivo}' tiene {len(datos)} filas y supera el límite de Excel; "
                    f"se repartirá en {n_hojas} hojas."
                )

            # strings_to_urls=False: las URLs (fotos, perfiles) se dejan como texto; Excel solo admite 65.530 hipervínculos por hoja
            with pd.ExcelWriter(ruta, engine="xlsxwriter", datetime_format="yyyy-mm-dd",
                                engine_kwargs={"options": {"strings_to_urls": False}}) as escritor:
                for i in range(n_hojas):
                    bloque = datos.iloc[i * self.MAX_FILAS_EXCEL:(i + 1) * self.MAX_FILAS_EXCEL]
                    nombre_hoja = "Datos" if n_hojas == 1 else f"Datos_{i + 1}"
                    bloque.to_excel(escritor, sheet_name=nombre_hoja, index=False)

            filas_excel = self._contar_filas_excel(ruta)
            self.logger.info(
                f"Exportación exitosa: '{ruta.name}' generado ({len(df)} registros, "
                f"{filas_excel} filas con encabezados, {ruta.stat().st_size / 1_048_576:.1f} MB)."
            )
            return ruta
        except Exception as e:
            self.logger.error(f"Error al exportar '{nombre_archivo}' a Excel: {e}")
            return None

    # ------------------------------------------------------------------
    # Orquestación
    # ------------------------------------------------------------------
    def ejecutar_carga(self, resultados):
        """
        Carga todos los resultados de la transformación.

        Parámetros:
            resultados: diccionario devuelto por Transformacion.ejecutar_transformacion()
                con las claves 'listings', 'reviews', 'calendar' y 'calendar_mensual'.

        Devuelve:
            Diccionario con el resultado (True/False) de cada carga a SQLite.
        """
        self.logger.info("--- INICIANDO PROCESO DE CARGA ---")

        tablas = {
            "Listings_Limpio": resultados.get("listings"),
            "Reviews_Limpio": resultados.get("reviews"),
            "Calendar_Limpio": resultados.get("calendar"),
            "Calendar_Mensual": resultados.get("calendar_mensual"),
        }
        estado = {nombre: self.cargar_sqlite(df, nombre) for nombre, df in tablas.items()}

        # Calendar_Limpio (un registro por anuncio y día) no cabe en Excel; se exporta su resumen mensual
        exportaciones = {
            "Listings_Transformado": resultados.get("listings"),
            "Reviews_Transformado": resultados.get("reviews"),
            "Calendar_Mensual_Transformado": resultados.get("calendar_mensual"),
        }
        for nombre, df in exportaciones.items():
            self.exportar_excel(df, nombre)

        fallidas = [nombre for nombre, ok in estado.items() if not ok]
        if fallidas:
            self.logger.error(f"--- CARGA FINALIZADA CON ERRORES en las tablas: {fallidas} ---")
        else:
            self.logger.info(f"--- CARGA FINALIZADA CON ÉXITO. Base de datos: {self.ruta_db} ---")
        return estado

    # ------------------------------------------------------------------
    # Auxiliares internos
    # ------------------------------------------------------------------
    @staticmethod
    def _validar_nombre_tabla(nombre):
        """El nombre de tabla va dentro de una sentencia SQL: solo se permiten letras, números y guion bajo."""
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", nombre):
            raise ValueError(f"Nombre de tabla no válido: '{nombre}'")

    @staticmethod
    def _preparar_para_sql(df):
        """
        Deja las fechas como texto 'YYYY-MM-DD' (SQLite no tiene tipo fecha) para que se
        guarden en formato estándar y no con hora (00:00:00).
        """
        datos = df.copy()
        for col in datos.select_dtypes(include=["datetime", "datetimetz"]).columns:
            datos[col] = datos[col].dt.strftime("%Y-%m-%d")
        return datos

    def _preparar_para_excel(self, df):
        """
        Quita caracteres de control (que Excel no admite y hacen fallar la exportación)
        y recorta textos que superen el límite de caracteres por celda.
        """
        datos = df.copy()
        caracteres_ilegales = r"[\x00-\x08\x0b\x0c\x0e-\x1f]"
        for col in datos.columns:
            if pd.api.types.is_object_dtype(datos[col]) or pd.api.types.is_string_dtype(datos[col]):
                serie = datos[col].astype("string")
                serie = serie.str.replace(caracteres_ilegales, "", regex=True).str.slice(0, self.MAX_CARACTERES_CELDA)
                datos[col] = serie.astype(object).where(serie.notna(), None)
        return datos

    @staticmethod
    def _contar_filas_excel(ruta):
        """Cuenta las filas (con encabezado) de todas las hojas del archivo, leyéndolo en modo ligero."""
        libro = load_workbook(ruta, read_only=True)
        try:
            return sum(hoja.max_row or 0 for hoja in libro.worksheets)
        finally:
            libro.close()


if __name__ == "__main__":
    from extraccion import Extraccion
    from transformacion import Transformacion

    extractor = Extraccion(db_name="Airbnb")
    extractor.conectar()
    df_l, df_r, df_c = extractor.extraer_todo()
    extractor.cerrar()

    resultados = Transformacion().ejecutar_transformacion(df_l, df_r, df_c)
    Carga().ejecutar_carga(resultados)
