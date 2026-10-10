import pandas as pd
from logger_config import get_logger


class Transformacion:
    """Clase para limpiar los datos que trajimos de Mongo.
    Aquí quitamos los nulos, convertimos las fechas y arreglamos
    los precios basándonos en lo que vimos en el Notebook del EDA"""

    ETIQUETAS_PRECIO = ["Económico", "Medio", "Alto", "Lujo"]

    # Amenidades que vamos a convertir a columnas de 1 o 0
    AMENIDADES_CLAVE = {
        "tiene_wifi": "wifi",
        "tiene_cocina": "kitchen",
        "tiene_aire_acondicionado": "air conditioning",
        "tiene_estacionamiento": "parking",
        "tiene_lavadora": "washer",
        "tiene_piscina": "pool",
    }


    def __init__(self):
        """Inicia el transformador"""
        self.logger = get_logger(__name__)


    def limpiar_nulos_duplicados(self, df, columnas_criticas, subset_duplicados):
        """Elimina duplicados y filas con nulos en columnas importantes"""
        if df is None or df.empty:
            self.logger.warning("El DataFrame está vacío, no se puede limpiar")
            return df

        registros_antes = len(df)

        # Eliminar duplicados basándonos en columnas específicas (como el ID)
        df = df.drop_duplicates(subset=subset_duplicados)
        n_duplicados = registros_antes - len(df)
        
        # Eliminar filas vacías
        antes_vacios = len(df)
        df = df.dropna(how="all")
        n_filas_vacias = antes_vacios - len(df)

        # Eliminar si faltan datos en columnas críticas
        antes_criticos = len(df)
        df = df.dropna(subset=columnas_criticas)
        n_criticos = antes_criticos - len(df)

        self.logger.info(
            f"Se eliminaron {n_duplicados} duplicados, {n_filas_vacias} filas vacías, "
            f"y {n_criticos} con nulos críticos. Quedan {len(df)} registros"
        )
        return df


    def eliminar_columnas_vacias(self, df):
        """Borramos columnas que están 100% vacías porque no sirven para el análisis"""
        if df is None or df.empty:
            return df
        
        vacias = [col for col in df.columns if df[col].isna().all()]
        if vacias:
            df = df.drop(columns=vacias)
            self.logger.warning(f"Se eliminaron columnas vacías: {vacias}")
        return df


    def imputar_nulos(self, df, columnas_texto=None, columnas_mediana=None):
        """Rellenamos nulos con texto por defecto o con la mediana"""
        if df is None or df.empty:
            return df

        if columnas_texto:
            for col in columnas_texto:
                if col in df.columns:
                    df[col] = df[col].fillna("Sin información")
                    
        if columnas_mediana:
            for col in columnas_mediana:
                if col in df.columns:
                    df[col] = df[col].fillna(df[col].median())
                    
        self.logger.info("Se imputaron valores nulos en texto y números.")
        return df


    def normalizar_precios(self, df, columna):
        """Convierte los precios de texto (con $) a números"""
        if df is None or columna not in df.columns:
            return df
        try:
            # Quitamos el $ y las comas
            limpio = df[columna].astype(str).str.replace(r"[^\d.\-]", "", regex=True)
            df[columna] = pd.to_numeric(limpio, errors="coerce")
            self.logger.info(f"Precio '{columna}' convertido a número")
        except Exception as e:
            self.logger.error(f"Error arreglando el precio '{columna}': {e}")
        return df


    def filtrar_precios_validos(self, df, columna):
        """Descartamos precios en cero o negativos que pueden ser errores"""
        if df is None or columna not in df.columns:
            return df
        antes = len(df)
        df = df[df[columna].notna() & (df[columna] > 0)]
        descartados = antes - len(df)
        self.logger.warning(f"Se descartaron {descartados} registros por precio inválido")
        return df


    def marcar_atipicos(self, df, columna, nombre_columna, factor=1.5):
        """Marcamos los outliers usando la regla del rango intercuartílico"""
        if df is None or columna not in df.columns:
            return df
        serie = pd.to_numeric(df[columna], errors="coerce")
        q1, q3 = serie.quantile(0.25), serie.quantile(0.75)
        iqr = q3 - q1
        limite_inf, limite_sup = q1 - factor * iqr, q3 + factor * iqr
        
        df[nombre_columna] = ((serie < limite_inf) | (serie > limite_sup)).astype("int8")
        self.logger.info(f"Se marcaron atípicos en la columna '{columna}'.")
        return df


    def limitar_valores(self, df, columnas, maximo):
        """Le ponemos un tope a los valores porque algunos tienen el valor máximo de 32 bits"""
        if df is None:
            return df
        for col in columnas:
            if col in df.columns:
                df[col] = df[col].clip(upper=maximo)
                self.logger.warning(f"Los valores de '{col}' se limitaron a un máximo de {maximo}")
        return df


    def categorizar_precios(self, df, columna):
        """Agrupamos los precios en Económico, Medio, Alto y Lujo usando cuartiles"""
        if df is None or columna not in df.columns:
            return df
        try:
            df["rango_precio"] = pd.qcut(df[columna], q=4, labels=self.ETIQUETAS_PRECIO)
            df["rango_precio"] = df["rango_precio"].astype(str)
            self.logger.info(f"Precios categorizados en 'rango_precio'.")
        except Exception as e:
            self.logger.error(f"Error al categorizar '{columna}': {e}")
        return df


    def transformar_fechas(self, df, columna, derivar=True):
        """Pasamos la columna a formato fecha (YYYY-MM-DD) y le quitamos la hora"""
        if df is None or columna not in df.columns:
            return df
        try:
            # 1. Convertimos a fecha interna de Pandas temporalmente para poder hacer cálculos
            fechas_temp = pd.to_datetime(df[columna], errors="coerce")
            
            # 2. Sacamos el año, mes, etc. si se necesita
            if derivar:
                df["anio"] = fechas_temp.dt.year
                df["mes"] = fechas_temp.dt.month
                df["dia"] = fechas_temp.dt.day
                df["trimestre"] = fechas_temp.dt.quarter
                
            # 3. Guardamos la columna definitiva usando strftime para que quede solo como texto YYYY-MM-DD
            df[columna] = fechas_temp.dt.strftime('%Y-%m-%d')
            
            self.logger.info(f"Fechas de '{columna}' arregladas y sin horas")
        except Exception as e:
            self.logger.error(f"Error con las fechas de '{columna}': {e}")
        return df


    def expandir_amenidades(self, df, columna="amenities"):
        """Buscamos palabras clave en las amenidades para crear columnas de 1 o 0"""
        if df is None or columna not in df.columns:
            return df
        texto = df[columna].astype(str).str.lower()
        for nueva, buscada in self.AMENIDADES_CLAVE.items():
            df[nueva] = texto.str.contains(buscada, regex=False).astype("int8")
        self.logger.info("Amenidades separadas en columnas booleanas")
        return df


    def extraer_banos(self, df, columna="bathrooms_text", nueva="banos"):
        """Sacamos el número del texto de los baños (ej. '1.5 baths')"""
        if df is None or columna not in df.columns:
            return df
        texto = df[columna].astype(str).str.lower()
        numero = pd.to_numeric(texto.str.extract(r"(\d+(?:\.\d+)?)")[0], errors="coerce")
        # Si dice half-bath lo ponemos como 0.5
        medio_bano = texto.str.contains("half", regex=False) & numero.isna()
        df[nueva] = numero.mask(medio_bano, 0.5)
        self.logger.info(f"Columna de baños calculada.")
        return df


    def normalizar_booleanos(self, df, columnas):
        """Cambiamos t/f por 1/0"""
        if df is None:
            return df
        mapa = {"t": 1, "true": 1, "f": 0, "false": 0}
        for col in columnas:
            if col in df.columns:
                df[col] = df[col].astype(str).str.lower().map(mapa)
        self.logger.info("Columnas de t/f convertidas a 1 y 0")
        return df

    def estandarizar_texto(self, df, columnas, quitar_html=False):
        """Limpiamos un poco los textos de los comentarios y descripciones"""
        if df is None:
            return df
        for col in columnas:
            if col in df.columns:
                serie = df[col].astype(str)
                if quitar_html:
                    serie = serie.str.replace(r"<[^>]+>", " ", regex=True)
                df[col] = serie.str.replace(r"\s+", " ", regex=True).str.strip()
        self.logger.info("Textos limpiados.")
        return df


    def agrupar_calendario_mensual(self, df_calendar):
        """Resumimos el calendario por mes para que no sea tan pesado."""
        if df_calendar is None or df_calendar.empty or "available" not in df_calendar.columns:
            return pd.DataFrame()
        
        # Preparamos las operaciones básicas que sabemos que siempre están
        agregaciones = {
            "dias_totales": ("available", "size"),
            "dias_disponibles": ("available", "sum")
        }
        
        # Solo agregamos el cálculo del precio si la columna sobrevivió a la limpieza
        if "price" in df_calendar.columns:
            agregaciones["precio_promedio"] = ("price", "mean")
            
        resumen = df_calendar.groupby(["listing_id", "anio", "mes"], as_index=False).agg(**agregaciones)
        
        resumen["dias_ocupados"] = resumen["dias_totales"] - resumen["dias_disponibles"]
        resumen["porcentaje_ocupacion"] = (resumen["dias_ocupados"] / resumen["dias_totales"] * 100).round(2)
        
        if "precio_promedio" in resumen.columns:
            resumen["precio_promedio"] = resumen["precio_promedio"].round(2)
        
        self.logger.info("Calendario resumido por meses.")
        return resumen


    def ejecutar_transformacion(self, df_listings, df_reviews, df_calendar):
        """Llama a todas las transformaciones necesarias y devuelve un diccionario."""
        self.logger.info("--- INICIANDO TRANSFORMACIÓN ---")

        # LISTINGS
        self.logger.info("Transformando Listings...")
        listings = df_listings.copy()
        listings = self.eliminar_columnas_vacias(listings)
        listings = self.normalizar_precios(listings, "price")
        listings = self.limpiar_nulos_duplicados(listings, ["id", "price"], ["id"])
        listings = self.filtrar_precios_validos(listings, "price")
        listings = self.marcar_atipicos(listings, "price", "precio_atipico")
        listings = self.limitar_valores(listings, ["maximum_nights"], 1125)
        listings = self.categorizar_precios(listings, "price")
        listings = self.expandir_amenidades(listings, "amenities")

        # Convertimos las listas a texto plano para que SQLite y Excel no tengan problemas
        for col in ["amenities", "host_verifications"]:
            if col in listings.columns:
                listings[col] = listings[col].apply(
                    lambda x: ", ".join(x) if isinstance(x, list) else str(x)
                )

        # Eliminamos price_quote_raw porque es un diccionario anidado que da error en SQLite
        if "price_quote_raw" in listings.columns:
            listings = listings.drop(columns=["price_quote_raw"])

        listings = self.extraer_banos(listings, "bathrooms_text", "banos")
        listings = self.normalizar_booleanos(listings, ["host_is_superhost", "instant_bookable"])
        listings = self.transformar_fechas(listings, "host_since", derivar=False)
        listings = self.estandarizar_texto(listings, ["description"], quitar_html=True)
        listings = self.imputar_nulos(listings, columnas_mediana=["bedrooms", "beds", "banos"])

        # CALENDAR
        self.logger.info("Transformando Calendar...")
        calendar = df_calendar.copy()
        calendar = self.eliminar_columnas_vacias(calendar)
        calendar = self.normalizar_precios(calendar, "price")
        calendar = self.transformar_fechas(calendar, "date")
        calendar = self.limpiar_nulos_duplicados(calendar, ["listing_id", "date"], ["listing_id", "date"])
        calendar = self.normalizar_booleanos(calendar, ["available"])
        calendar_mensual = self.agrupar_calendario_mensual(calendar)

        # REVIEWS
        self.logger.info("Transformando Reviews...")
        reviews = df_reviews.copy()
        reviews = self.eliminar_columnas_vacias(reviews)
        reviews = self.transformar_fechas(reviews, "date")
        reviews = self.limpiar_nulos_duplicados(reviews, ["id", "listing_id", "date"], ["id"])
        reviews = self.estandarizar_texto(reviews, ["comments"], quitar_html=True)
        reviews = self.imputar_nulos(reviews, columnas_texto=["comments"])

        # Convertir todos los IDs inmensos a texto para SQLite/Excel
        if "id" in listings.columns: listings["id"] = listings["id"].astype(str)
        if "host_id" in listings.columns: listings["host_id"] = listings["host_id"].astype(str)
        
        if "listing_id" in calendar.columns: calendar["listing_id"] = calendar["listing_id"].astype(str)
        if "listing_id" in calendar_mensual.columns: calendar_mensual["listing_id"] = calendar_mensual["listing_id"].astype(str)
        
        if "id" in reviews.columns: reviews["id"] = reviews["id"].astype(str)
        if "listing_id" in reviews.columns: reviews["listing_id"] = reviews["listing_id"].astype(str)
        if "reviewer_id" in reviews.columns: reviews["reviewer_id"] = reviews["reviewer_id"].astype(str)

        self.logger.info("TRANSFORMACIÓN FINALIZADA")
        return {
            "listings": listings,
            "reviews": reviews,
            "calendar": calendar,
            "calendar_mensual": calendar_mensual,
        }

if __name__ == "__main__":
    from extraccion import Extraccion
    extractor = Extraccion(db_name="Airbnb")
    extractor.conectar()
    df_l, df_r, df_c = extractor.extraer_todo()
    extractor.cerrar()

    resultados = Transformacion().ejecutar_transformacion(df_l, df_r, df_c)
