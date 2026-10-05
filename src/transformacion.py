"""
Fase 2 del ETL: limpieza y transformación de los DataFrames extraídos de MongoDB.
"""
import ast
import json

import numpy as np
import pandas as pd

from logger_config import get_logger


class Transformacion:
    """
    Limpia y transforma los DataFrames de Listings, Reviews y Calendar para dejarlos
    listos para la carga en SQLite / XLSX.

    Cada método documenta QUÉ hace y POR QUÉ (la justificación proviene del análisis
    exploratorio del notebook exploracion_airbnb.ipynb) y registra en el log los
    registros antes/después, las advertencias y los errores.
    """

    ETIQUETAS_PRECIO = ["Económico", "Medio", "Alto", "Lujo"]

    # Amenidades clave que se expanden a columnas booleanas (1 = la tiene, 0 = no).
    # Clave: nombre de la nueva columna. Valor: texto a buscar en la lista de amenities.
    AMENIDADES_CLAVE = {
        "tiene_wifi": "wifi",
        "tiene_cocina": "kitchen",
        "tiene_aire_acondicionado": "air conditioning",
        "tiene_estacionamiento": "parking",
        "tiene_lavadora": "washer",
        "tiene_piscina": "pool",
    }

    def __init__(self):
        self.logger = get_logger(__name__)

    # ------------------------------------------------------------------
    # 1. Limpieza de nulos y duplicados
    # ------------------------------------------------------------------
    def limpiar_nulos_duplicados(self, df, nombre_df, columnas_criticas=None, subset_duplicados=None):
        """
        Elimina duplicados y filas con nulos en columnas críticas.

        Por qué: los duplicados distorsionan conteos y promedios; y una fila sin los
        campos críticos (p. ej. precio o fecha) no sirve para el análisis.

        Parámetros:
            df: DataFrame a limpiar.
            nombre_df: nombre usado en los mensajes del log.
            columnas_criticas: columnas que NO pueden ser nulas (se descartan las filas con nulos en ellas).
            subset_duplicados: columnas que identifican un registro único (p. ej. ['id']).
                Si es None se comparan todas las columnas.
        """
        if df is None or df.empty:
            self.logger.warning(f"[{nombre_df}] El DataFrame está vacío o es nulo; no hay nada que limpiar.")
            return df

        registros_antes = len(df)

        # Duplicados
        duplicados = self._marcar_duplicados(df, subset_duplicados)
        n_duplicados = int(duplicados.sum())
        df = df.loc[~duplicados]

        # Filas completamente nulas
        n_antes_nulos = len(df)
        df = df.dropna(how="all")
        n_filas_vacias = n_antes_nulos - len(df)

        # Nulos en columnas críticas (solo las que existen en el DataFrame)
        n_criticos = 0
        if columnas_criticas:
            cols_validas = [c for c in columnas_criticas if c in df.columns]
            faltantes = set(columnas_criticas) - set(cols_validas)
            if faltantes:
                self.logger.warning(f"[{nombre_df}] Columnas críticas inexistentes (se ignoran): {sorted(faltantes)}")
            if cols_validas:
                n_antes_criticos = len(df)
                df = df.dropna(subset=cols_validas)
                n_criticos = n_antes_criticos - len(df)

        self.logger.info(
            f"[{nombre_df}] Limpieza de nulos/duplicados: de {registros_antes} a {len(df)} registros "
            f"(duplicados: {n_duplicados}, filas vacías: {n_filas_vacias}, nulos en columnas críticas: {n_criticos})."
        )
        return df

    def eliminar_columnas_vacias(self, df, nombre_df):
        """
        Elimina las columnas que están 100% vacías.

        Por qué: una columna sin ningún dato no aporta información y solo ocupa espacio
        en la base de datos y en el Excel. Una columna de texto cuyo único valor es 'None'
        (como host_verifications en este dataset) también se considera vacía.
        """
        if df is None or df.empty:
            return df
        textos_vacios = {"None", "none", "nan", ""}
        vacias = []
        for col in df.columns:
            serie = df[col]
            if serie.isna().all():
                vacias.append(col)
            elif self._es_columna_texto(serie) and (serie.isna() | serie.isin(textos_vacios)).all():
                vacias.append(col)
        if vacias:
            df = df.drop(columns=vacias)
            self.logger.warning(f"[{nombre_df}] Columnas 100% vacías eliminadas: {vacias}")
        return df

    def imputar_nulos(self, df, nombre_df, columnas_texto=None, texto_defecto="Sin información",
                      columnas_mediana=None):
        """
        Rellena nulos con un valor razonable en lugar de descartar el registro.

        - Texto: se usa 'Sin información' para que las consultas y gráficas no pierdan filas.
        - Numéricas (p. ej. habitaciones, camas, baños): se usa la mediana, que es robusta a
          valores extremos. Las columnas review_scores_* NO se imputan: un nulo significa
          'sin reseñas', que es información real y no un dato perdido.

        Parámetros:
            columnas_texto: columnas de texto a rellenar. Si es None se usan todas las de tipo texto.
            columnas_mediana: columnas numéricas a rellenar con la mediana.
        """
        if df is None or df.empty:
            return df

        if columnas_texto is None:
            columnas_texto = [c for c in df.columns if self._es_columna_texto(df[c])]
        columnas_texto = [c for c in columnas_texto if c in df.columns]
        total_texto = 0
        for col in columnas_texto:
            nulos = int(df[col].isna().sum())
            if nulos:
                df[col] = df[col].fillna(texto_defecto)
                total_texto += nulos

        total_mediana = 0
        for col in (columnas_mediana or []):
            if col in df.columns:
                nulos = int(df[col].isna().sum())
                if nulos and df[col].notna().any():
                    df[col] = df[col].fillna(df[col].median())
                    total_mediana += nulos

        self.logger.info(
            f"[{nombre_df}] Imputación de nulos: {total_texto} valores de texto -> '{texto_defecto}', "
            f"{total_mediana} valores numéricos -> mediana."
        )
        return df

    # ------------------------------------------------------------------
    # 2. Precios
    # ------------------------------------------------------------------
    def normalizar_precios(self, df, columna):
        """
        Convierte precios como '$1,234.56' a número (1234.56).

        Por qué: el símbolo '$' y el separador de miles ',' convierten la columna en texto
        e impiden calcular promedios, rangos y comparaciones.
        Los valores que no se puedan convertir quedan como NaN (se informa cuántos).
        """
        if df is None or columna not in df.columns:
            return df
        try:
            antes_nulos = int(df[columna].isna().sum())
            limpio = df[columna].astype(str).str.replace(r"[^\d.\-]", "", regex=True)
            df[columna] = pd.to_numeric(limpio.replace("", np.nan), errors="coerce")
            nuevos_nulos = int(df[columna].isna().sum()) - antes_nulos
            if nuevos_nulos > 0:
                self.logger.warning(
                    f"Columna '{columna}': {nuevos_nulos} valores no se pudieron convertir a número y quedaron como nulos."
                )
            self.logger.info(f"Columna de precio '{columna}' normalizada a numérico correctamente.")
        except Exception as e:
            self.logger.error(f"Error al normalizar la columna '{columna}': {e}")
        return df

    def filtrar_precios_validos(self, df, columna, nombre_df):
        """
        Descarta registros con precio nulo o menor/igual a cero.

        Por qué: un precio de 0 (o negativo) es un error de captura; dejarlo sesgaría
        los promedios y la categorización por rangos.
        """
        if df is None or columna not in df.columns:
            return df
        antes = len(df)
        df = df[df[columna].notna() & (df[columna] > 0)]
        descartados = antes - len(df)
        if descartados:
            self.logger.warning(f"[{nombre_df}] {descartados} registros descartados por precio nulo o <= 0 en '{columna}'.")
        else:
            self.logger.info(f"[{nombre_df}] Todos los precios de '{columna}' son válidos (> 0).")
        return df

    def marcar_atipicos(self, df, columna, nombre_columna=None, factor=1.5):
        """
        Marca (sin eliminar) los valores atípicos de una columna con la regla del rango intercuartílico (IQR).

        Un valor es atípico si está fuera de [Q1 - factor*IQR, Q3 + factor*IQR].
        Por qué se marca y no se elimina: un precio muy alto puede ser real (propiedad de lujo);
        con la bandera el analista decide si lo excluye.
        """
        if df is None or columna not in df.columns:
            return df
        nombre_columna = nombre_columna or f"{columna}_atipico"
        serie = pd.to_numeric(df[columna], errors="coerce")
        q1, q3 = serie.quantile(0.25), serie.quantile(0.75)
        iqr = q3 - q1
        limite_inf, limite_sup = q1 - factor * iqr, q3 + factor * iqr
        df[nombre_columna] = ((serie < limite_inf) | (serie > limite_sup)).astype("int8")
        self.logger.info(
            f"Atípicos en '{columna}': {int(df[nombre_columna].sum())} registros fuera de "
            f"[{limite_inf:,.2f}, {limite_sup:,.2f}] (marcados en '{nombre_columna}', no eliminados)."
        )
        return df

    def limitar_valores(self, df, columnas, maximo, nombre_df):
        """
        Limita a un máximo los valores de las columnas indicadas.

        Por qué: en 'maximum_nights' (y columnas derivadas) aparece el valor 2.147.483.647
        (el mayor entero de 32 bits), que es un valor centinela de "sin límite" y no una cantidad real
        de noches; deformaría promedios y gráficas. Airbnb permite reservar como máximo 1125 noches,
        así que ese es el tope razonable.
        """
        if df is None:
            return df
        for col in columnas:
            if col in df.columns:
                excede = int((df[col] > maximo).sum())
                if excede:
                    df[col] = df[col].clip(upper=maximo)
                    self.logger.warning(f"[{nombre_df}] '{col}': {excede} valores por encima de {maximo} limitados a {maximo}.")
        return df

    def marcar_estadias_largas(self, df, columna="minimum_nights", umbral=28):
        """
        Crea 'estadia_larga' (1 = exige {umbral} noches o más).

        Por qué: el EDA muestra que las noches mínimas son bimodales: la mayoría de anuncios pide 1-3
        noches y un grupo grande pide 28-30 (alquiler mensual). No son errores, sino un segmento distinto
        del mercado; la bandera permite analizarlos por separado.
        """
        if df is None or columna not in df.columns:
            return df
        df["estadia_larga"] = (df[columna] >= umbral).astype("int8")
        self.logger.info(f"Bandera 'estadia_larga' creada: {int(df['estadia_larga'].sum())} anuncios con {columna} >= {umbral}.")
        return df

    def categorizar_precios(self, df, columna, rangos=None):
        """
        Crea la columna 'rango_precio' con las categorías Económico, Medio, Alto y Lujo.

        Por qué: agrupar el precio en categorías facilita comparar segmentos del mercado.

        Parámetros:
            rangos: lista de 5 límites [min, c1, c2, c3, max] para usar cortes fijos.
                Si es None se usan los CUARTILES del propio precio (25 % de las propiedades por categoría),
                lo que no depende de la moneda ni del nivel de precios de la ciudad.
        """
        if df is None or columna not in df.columns:
            return df
        try:
            if rangos is None:
                df["rango_precio"] = pd.qcut(df[columna], q=4, labels=self.ETIQUETAS_PRECIO, duplicates="raise")
                cortes = df[columna].quantile([0, 0.25, 0.5, 0.75, 1]).round(2).tolist()
                self.logger.info(f"Precios categorizados por cuartiles en 'rango_precio'. Cortes: {cortes}")
            else:
                df["rango_precio"] = pd.cut(df[columna], bins=rangos, labels=self.ETIQUETAS_PRECIO, include_lowest=True)
                self.logger.info(f"Precios categorizados con cortes fijos {rangos} en 'rango_precio'.")
            # Se guarda como texto: SQLite y Excel no manejan el tipo 'category' de pandas
            df["rango_precio"] = df["rango_precio"].astype(object)
        except Exception as e:
            self.logger.error(f"Error al categorizar precios de '{columna}': {e}")
        return df

    # ------------------------------------------------------------------
    # 3. Fechas
    # ------------------------------------------------------------------
    def transformar_fechas(self, df, columna, derivar=True):
        """
        Convierte una columna a fecha estándar (YYYY-MM-DD, sin hora) y deriva variables de tiempo.

        Por qué: las fechas pueden llegar como texto o con hora; un formato único permite
        ordenar, filtrar y agrupar por periodos. Las variables derivadas (anio, mes, dia,
        trimestre, dia_semana) permiten análisis por temporada sin tener que volver a convertir.
        Las fechas inválidas quedan como nulas (NaT) y se informa cuántas.

        Parámetros:
            derivar: si es False solo estandariza la fecha (para columnas como host_since).
        """
        if df is None or columna not in df.columns:
            return df
        try:
            nulos_antes = int(df[columna].isna().sum())
            df[columna] = pd.to_datetime(df[columna], errors="coerce").dt.normalize()
            invalidas = int(df[columna].isna().sum()) - nulos_antes
            if invalidas > 0:
                self.logger.warning(f"Columna '{columna}': {invalidas} fechas inválidas quedaron como nulas.")

            if derivar:
                df["anio"] = df[columna].dt.year
                df["mes"] = df[columna].dt.month
                df["dia"] = df[columna].dt.day
                df["trimestre"] = df[columna].dt.quarter
                df["dia_semana"] = df[columna].dt.dayofweek  # 0 = lunes ... 6 = domingo
            self.logger.info(
                f"Fechas de '{columna}' estandarizadas a YYYY-MM-DD"
                f"{' y variables derivadas generadas (anio, mes, dia, trimestre, dia_semana)' if derivar else ''}."
            )
        except Exception as e:
            self.logger.error(f"Error al transformar fechas en '{columna}': {e}")
        return df

    # ------------------------------------------------------------------
    # 4. Campos anidados, booleanos, porcentajes y texto
    # ------------------------------------------------------------------
    def desanidar_campos(self, df, columna):
        """
        Convierte un campo anidado (lista) en texto legible separado por comas y crea
        'cantidad_<columna>' con el número de elementos.

        Por qué: columnas como 'amenities' y 'host_verifications' llegan como listas de Python
        (o como texto JSON). SQLite y Excel no pueden guardar listas; un texto separado por comas
        sí, y el conteo permite analizar qué tan equipada está una propiedad.
        """
        if df is None or columna not in df.columns:
            return df
        try:
            listas = df[columna].map(self._a_lista)
            df[f"cantidad_{columna}"] = listas.map(len).astype("int32")
            df[columna] = listas.map(lambda items: ", ".join(items) if items else np.nan)
            self.logger.info(f"Campo anidado '{columna}' desanidado a texto y columna 'cantidad_{columna}' creada.")
        except Exception as e:
            self.logger.error(f"Error al desanidar '{columna}': {e}")
        return df

    def desanidar_diccionario(self, df, columna, extracciones):
        """
        Extrae campos concretos de una columna con diccionarios anidados y elimina la columna original.

        Por qué: 'price_quote_raw' es un JSON anidado (con listas de líneas de precio) que no se puede
        guardar en SQLite ni en Excel. Su información útil ya existe en columnas planas
        (price_quote_total_price, price_quote_price_per_night); solo se rescata la moneda.

        Parámetros:
            extracciones: {nueva_columna: ['clave1', 'clave2', ...]} con la ruta de claves a seguir.
                Ejemplo: {'moneda': ['quote', 'currency']}
        """
        if df is None or columna not in df.columns:
            return df
        try:
            def extraer(valor, ruta):
                for clave in ruta:
                    if not isinstance(valor, dict):
                        return None
                    valor = valor.get(clave)
                return valor

            for nueva, ruta in extracciones.items():
                df[nueva] = df[columna].map(lambda v, r=ruta: extraer(v, r))
            df = df.drop(columns=[columna])
            self.logger.info(f"Campo anidado '{columna}' desanidado: columnas creadas {list(extracciones)}; original eliminada.")
        except Exception as e:
            self.logger.error(f"Error al desanidar el diccionario '{columna}': {e}")
        return df

    def extraer_banos(self, df, columna="bathrooms_text", nueva="banos"):
        """
        Convierte textos como '2.5 baths' o 'Half-bath' en un número de baños (2.5 / 0.5).

        Por qué: el dataset no trae una columna numérica de baños, solo el texto; el número
        permite promedios y comparaciones. 'Half-bath' no contiene dígitos y equivale a 0.5.
        """
        if df is None or columna not in df.columns:
            return df
        try:
            texto = df[columna].astype(str).str.lower()
            numero = pd.to_numeric(texto.str.extract(r"(\d+(?:\.\d+)?)")[0], errors="coerce")
            medio_bano = texto.str.contains("half", regex=False) & numero.isna()
            df[nueva] = numero.mask(medio_bano, 0.5)
            self.logger.info(f"Columna '{nueva}' (numérica) derivada de '{columna}'.")
        except Exception as e:
            self.logger.error(f"Error al extraer baños de '{columna}': {e}")
        return df

    def expandir_amenidades(self, df, columna="amenities"):
        """
        Crea columnas booleanas (1/0) para las amenidades más relevantes
        (wifi, cocina, aire acondicionado, estacionamiento, lavadora, piscina).

        Por qué: permite filtrar y comparar propiedades por una amenidad concreta sin tener
        que buscar texto dentro de la lista completa.
        Debe ejecutarse DESPUÉS de desanidar_campos (trabaja sobre el texto).
        """
        if df is None or columna not in df.columns:
            return df
        try:
            texto = df[columna].astype(str).str.lower()
            for nueva, buscada in self.AMENIDADES_CLAVE.items():
                df[nueva] = texto.str.contains(buscada, regex=False).astype("int8")
            self.logger.info(f"Amenidades clave expandidas a columnas: {list(self.AMENIDADES_CLAVE)}.")
        except Exception as e:
            self.logger.error(f"Error al expandir amenidades de '{columna}': {e}")
        return df

    def normalizar_booleanos(self, df, columnas):
        """
        Convierte valores 't'/'f' (o true/false) en 1/0.

        Por qué: Airbnb usa 't'/'f' como texto; como entero 1/0 se puede sumar y promediar
        directamente (p. ej. porcentaje de superhosts). Los nulos se conservan.
        """
        if df is None:
            return df
        mapa = {"t": 1, "true": 1, "1": 1, "f": 0, "false": 0, "0": 0}
        convertidas = []
        for col in columnas:
            if col in df.columns:
                df[col] = df[col].astype(str).str.strip().str.lower().map(mapa).astype("Int8")
                convertidas.append(col)
        if convertidas:
            self.logger.info(f"Columnas t/f convertidas a 1/0: {convertidas}")
        return df

    def normalizar_porcentajes(self, df, columnas):
        """
        Convierte porcentajes en texto ('95%') a número (95.0).

        Por qué: con el símbolo '%' la columna es texto y no se puede promediar.
        """
        if df is None:
            return df
        convertidas = []
        for col in columnas:
            if col in df.columns:
                limpio = df[col].astype(str).str.replace("%", "", regex=False).str.strip()
                df[col] = pd.to_numeric(limpio, errors="coerce")
                convertidas.append(col)
        if convertidas:
            self.logger.info(f"Porcentajes convertidos a numérico: {convertidas}")
        return df

    def estandarizar_texto(self, df, columnas, quitar_html=False):
        """
        Estandariza texto: quita espacios sobrantes y saltos de línea; opcionalmente quita etiquetas HTML.

        Por qué: los comentarios de las reseñas contienen etiquetas como '<br/>' y espacios dobles
        que ensucian el texto y dañan la lectura en Excel.
        """
        if df is None:
            return df
        procesadas = []
        for col in columnas:
            if col in df.columns:
                serie = df[col].astype("string")
                if quitar_html:
                    serie = serie.str.replace(r"<[^>]+>", " ", regex=True)
                df[col] = serie.str.replace(r"\s+", " ", regex=True).str.strip().astype(object)
                procesadas.append(col)
        if procesadas:
            self.logger.info(f"Texto estandarizado en columnas: {procesadas}")
        return df

    # ------------------------------------------------------------------
    # 5. Agregaciones
    # ------------------------------------------------------------------
    def agrupar_calendario_mensual(self, df_calendar):
        """
        Resume el calendario por anuncio y mes.

        Por qué: Calendar tiene un registro por anuncio y por día (millones de filas, no cabe en Excel).
        El resumen mensual conserva lo analíticamente útil: días disponibles/ocupados, porcentaje de
        ocupación y precio promedio.

        Devuelve:
            DataFrame con una fila por (listing_id, anio, mes).
        """
        if df_calendar is None or df_calendar.empty or "available" not in df_calendar.columns:
            self.logger.warning("No se puede agrupar el calendario: faltan datos o la columna 'available'.")
            return pd.DataFrame()
        try:
            agregaciones = {
                "dias_totales": ("available", "size"),
                "dias_disponibles": ("available", "sum"),
            }
            if "price" in df_calendar.columns:
                agregaciones["precio_promedio"] = ("price", "mean")
            resumen = df_calendar.groupby(["listing_id", "anio", "mes"], as_index=False).agg(**agregaciones)
            resumen["dias_ocupados"] = resumen["dias_totales"] - resumen["dias_disponibles"]
            resumen["porcentaje_ocupacion"] = (resumen["dias_ocupados"] / resumen["dias_totales"] * 100).round(2)
            if "precio_promedio" in resumen.columns:
                resumen["precio_promedio"] = resumen["precio_promedio"].round(2)
            self.logger.info(f"Calendario agrupado por anuncio y mes: {len(resumen)} registros resumen.")
            return resumen
        except Exception as e:
            self.logger.error(f"Error al agrupar el calendario por mes: {e}")
            return pd.DataFrame()

    # ------------------------------------------------------------------
    # 6. Orquestación
    # ------------------------------------------------------------------
    def transformar_listings(self, df):
        """Pipeline de transformación de la colección Listings."""
        self.logger.info("Transformando LISTINGS...")
        df = df.copy()
        df = self.eliminar_columnas_vacias(df, "Listings")
        # El precio se normaliza ANTES de limpiar: así los precios con formato inválido también se descartan
        df = self.normalizar_precios(df, "price")
        df = self.limpiar_nulos_duplicados(df, "Listings", columnas_criticas=["id", "price"], subset_duplicados=["id"])
        df = self.filtrar_precios_validos(df, "price", "Listings")
        df = self.marcar_atipicos(df, "price", "precio_atipico")
        df = self.marcar_atipicos(df, "minimum_nights", "minimo_noches_atipico")
        df = self.marcar_estadias_largas(df, "minimum_nights")
        df = self.limitar_valores(
            df, ["maximum_nights", "minimum_maximum_nights", "maximum_maximum_nights", "maximum_nights_avg_ntm"],
            maximo=1125, nombre_df="Listings"
        )
        df = self.categorizar_precios(df, "price")

        # Campos anidados: listas (amenities, host_verifications) y diccionario (price_quote_raw)
        for col in ["amenities", "host_verifications"]:
            df = self.desanidar_campos(df, col)
        df = self.expandir_amenidades(df, "amenities")
        df = self.desanidar_diccionario(df, "price_quote_raw", {"moneda": ["quote", "currency"]})
        df = self.extraer_banos(df, "bathrooms_text", "banos")

        df = self.normalizar_booleanos(
            df, ["host_is_superhost", "host_has_profile_pic", "host_identity_verified",
                 "instant_bookable", "has_availability"]
        )
        df = self.normalizar_porcentajes(df, ["host_response_rate", "host_acceptance_rate"])
        for col in ["host_since", "first_review", "last_review", "last_scraped", "calendar_last_scraped",
                    "price_quote_checkin_date", "price_quote_checkout_date"]:
            df = self.transformar_fechas(df, col, derivar=False)
        df = self.estandarizar_texto(df, ["name", "neighbourhood_cleansed", "property_type", "room_type"])
        df = self.estandarizar_texto(df, ["description", "neighborhood_overview", "host_about"], quitar_html=True)

        df = self.imputar_nulos(df, "Listings", columnas_mediana=["bedrooms", "beds", "bathrooms", "banos"])
        return df

    def transformar_calendar(self, df):
        """Pipeline de transformación de la colección Calendar."""
        self.logger.info("Transformando CALENDAR...")
        df = df.copy()
        df = self.eliminar_columnas_vacias(df, "Calendar")
        for col in ["price", "adjusted_price"]:
            df = self.normalizar_precios(df, col)
        df = self.transformar_fechas(df, "date")
        df = self.limpiar_nulos_duplicados(
            df, "Calendar", columnas_criticas=["listing_id", "date"], subset_duplicados=["listing_id", "date"]
        )
        df = self.normalizar_booleanos(df, ["available"])
        df = self.limitar_valores(df, ["maximum_nights"], maximo=1125, nombre_df="Calendar")
        return df

    def transformar_reviews(self, df):
        """Pipeline de transformación de la colección Reviews."""
        self.logger.info("Transformando REVIEWS...")
        df = df.copy()
        df = self.eliminar_columnas_vacias(df, "Reviews")
        df = self.transformar_fechas(df, "date")
        df = self.limpiar_nulos_duplicados(
            df, "Reviews", columnas_criticas=["id", "listing_id", "date"], subset_duplicados=["id"]
        )
        df = self.estandarizar_texto(df, ["comments", "reviewer_name"], quitar_html=True)
        df = self.imputar_nulos(df, "Reviews", columnas_texto=["comments", "reviewer_name"],
                                texto_defecto="Sin comentario")
        return df

    def ejecutar_transformacion(self, df_listings, df_reviews, df_calendar):
        """
        Orquesta todas las transformaciones.

        Devuelve:
            Diccionario con los DataFrames limpios listos para la carga:
            'listings', 'reviews', 'calendar' y 'calendar_mensual' (resumen por anuncio y mes).
        """
        self.logger.info("--- INICIANDO PROCESO DE TRANSFORMACIÓN ---")
        listings = self.transformar_listings(df_listings)
        calendar = self.transformar_calendar(df_calendar)
        reviews = self.transformar_reviews(df_reviews)
        calendar_mensual = self.agrupar_calendario_mensual(calendar)
        self.logger.info(
            f"--- TRANSFORMACIÓN FINALIZADA: listings={len(listings)}, reviews={len(reviews)}, "
            f"calendar={len(calendar)}, calendar_mensual={len(calendar_mensual)} registros ---"
        )
        return {
            "listings": listings,
            "reviews": reviews,
            "calendar": calendar,
            "calendar_mensual": calendar_mensual,
        }

    # ------------------------------------------------------------------
    # Auxiliares internos
    # ------------------------------------------------------------------
    @staticmethod
    def _es_columna_texto(serie):
        """True si la columna es de texto (y no contiene listas ni diccionarios)."""
        if not (pd.api.types.is_object_dtype(serie) or pd.api.types.is_string_dtype(serie)):
            return False
        muestra = serie.dropna().head(200)
        return not muestra.map(lambda v: isinstance(v, (list, dict, set, tuple, np.ndarray))).any()

    def _marcar_duplicados(self, df, subset):
        """
        Devuelve una serie booleana con True en las filas duplicadas.

        Las columnas con listas o diccionarios no son 'hasheables', así que si pandas falla
        se comparan convirtiéndolas temporalmente a texto.
        """
        try:
            return df.duplicated(subset=subset)
        except TypeError:
            columnas = subset or list(df.columns)
            temporal = df[columnas].astype(str)
            return temporal.duplicated()

    @staticmethod
    def _a_lista(valor):
        """
        Convierte un valor anidado a lista de textos limpios.

        Acepta listas/arrays de Python y también texto que represente una lista
        (JSON '["a","b"]' o formato Python "['a', 'b']").
        """
        if valor is None or (isinstance(valor, float) and np.isnan(valor)):
            return []
        if isinstance(valor, (list, tuple, set, np.ndarray)):
            elementos = list(valor)
        elif isinstance(valor, str):
            texto = valor.strip()
            if texto.startswith("["):
                try:
                    elementos = json.loads(texto)
                except ValueError:
                    try:
                        elementos = ast.literal_eval(texto)
                    except (ValueError, SyntaxError):
                        elementos = [texto.strip("[]")]
            elif texto in ("", "None", "nan"):
                elementos = []
            else:
                elementos = [texto]
        else:
            elementos = [valor]
        return [str(e).strip() for e in elementos if e is not None and str(e).strip()]


if __name__ == "__main__":
    from extraccion import Extraccion

    extractor = Extraccion(db_name="Airbnb")
    extractor.conectar()
    df_l, df_r, df_c = extractor.extraer_todo()
    extractor.cerrar()

    resultados = Transformacion().ejecutar_transformacion(df_l, df_r, df_c)
