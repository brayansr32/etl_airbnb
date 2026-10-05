# ETL Airbnb Bogotá

Proceso **ETL (Extracción, Transformación y Carga)** en Python sobre los datasets de Airbnb de
**Bogotá, Distrito Capital, Colombia** (Inside Airbnb), desarrollado para el *Taller evaluativo 2* de
Inteligencia de Negocios.

## Descripción y objetivo

Los datos de `Listings` (anuncios), `Reviews` (reseñas) y `Calendar` (disponibilidad diaria) están almacenados en una
base de datos **MongoDB local**. El proyecto:

1. **Extrae** las tres colecciones desde MongoDB a DataFrames de pandas (`Extraccion`).
2. **Explora** su estructura, calidad y distribución en un notebook de Jupyter (EDA).
3. **Transforma** los datos: limpieza de nulos y duplicados, normalización de precios, estandarización de fechas
   con variables derivadas, categorización de precios, tratamiento de campos anidados, entre otros (`Transformacion`).
4. **Carga** los datos limpios en una base analítica **SQLite** y los exporta a archivos **XLSX** (`Carga`).
5. Registra todo el proceso en **logs** (un archivo por ejecución).

**Objetivo:** dejar los datos listos para análisis, aplicando un proceso automatizado, trazable y documentado.

## Estructura del repositorio

```
etl_airbnb/
├── src/
│   ├── extraccion.py       # Clase Extraccion: conexión a MongoDB y extracción a DataFrames
│   ├── transformacion.py   # Clase Transformacion: limpieza y transformación
│   ├── carga.py            # Clase Carga: SQLite + XLSX + verificación
│   ├── logger_config.py    # Módulo centralizado de logs
│   └── main.py             # Ejecuta el ETL completo
├── notebooks/
│   └── exploracion_airbnb.ipynb   # Análisis exploratorio (EDA) con hallazgos
├── logs/                   # Un log por ejecución: log_YYYYMMDD_HHMMSS.txt
├── output/                 # Se genera al ejecutar: airbnb_analitica.db y archivos .xlsx
├── requirements.txt
└── README.md
```

## Requisitos previos

- **Python 3.10 o superior**
- **MongoDB Community Server** instalado y corriendo en `localhost:27017`
- Los datasets de Bogotá de Inside Airbnb: `listings.csv.gz`, `calendar.csv.gz` y `reviews.csv.gz`

## Instalación

### 1. Crear el entorno virtual

```bash
# Windows (PowerShell)
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# Linux / macOS
python3 -m venv .venv
source .venv/bin/activate
```

> Si PowerShell bloquea la activación, ejecuta primero: `Set-ExecutionPolicy -Scope Process RemoteSigned`

### 2. Instalar las dependencias

```bash
pip install -r requirements.txt
```

### 3. Preparar MongoDB

El proceso **solo lee desde MongoDB** (no desde los CSV). Antes de ejecutarlo hay que importar los
datasets a una base de datos llamada **`Airbnb`** con tres colecciones:

| Archivo fuente | Colección |
|---|---|
| `listings.csv.gz` | `Listings` |
| `reviews.csv.gz` | `Reviews` |
| `calendar.csv.gz` | `Calendar` |

> **PENDIENTE (completar por el equipo):** indicar aquí cómo se importaron los archivos
> (MongoDB Compass → *Add Data → Import File*, `mongoimport` o un script propio).

Validar que la carga quedó bien (cantidades esperadas con el dataset usado en este proyecto):

```bash
python -c "import pymongo; db = pymongo.MongoClient()['Airbnb']; [print(n, db[n].estimated_document_count()) for n in db.list_collection_names()]"
```

```
Listings 19187
Calendar 7003255
Reviews  527731
```

## Ejecución

Con el entorno virtual activado, desde la **raíz del proyecto**:

```bash
python src/main.py                  # ETL completo (~5 minutos con los datos completos)
python src/main.py --muestra 2000   # prueba rápida con 2000 registros por colección
```

Opciones: `--db` (nombre de la base, por defecto `Airbnb`), `--host` y `--puerto`.

Cada clase también puede ejecutarse por separado (`python src/extraccion.py`, `python src/transformacion.py`,
`python src/carga.py`) y usarse desde otro script:

```python
from extraccion import Extraccion
from transformacion import Transformacion
from carga import Carga

extractor = Extraccion(db_name="Airbnb")
extractor.conectar()
df_listings, df_reviews, df_calendar = extractor.extraer_todo()
extractor.cerrar()

resultados = Transformacion().ejecutar_transformacion(df_listings, df_reviews, df_calendar)
Carga().ejecutar_carga(resultados)
```

### Análisis exploratorio

```bash
jupyter notebook notebooks/exploracion_airbnb.ipynb
```

## Resultados generados

Al terminar, en `output/`:

| Archivo | Contenido |
|---|---|
| `airbnb_analitica.db` | Base SQLite con las tablas `Listings_Limpio`, `Reviews_Limpio`, `Calendar_Limpio` y `Calendar_Mensual` |
| `Listings_Transformado.xlsx` | Anuncios limpios |
| `Reviews_Transformado.xlsx` | Reseñas limpias |
| `Calendar_Mensual_Transformado.xlsx` | Resumen mensual del calendario por anuncio |

`Calendar_Limpio` tiene más de 7 millones de filas y no cabe en Excel, por eso en XLSX se exporta su resumen
mensual (días disponibles y ocupados y porcentaje de ocupación por anuncio y mes). Consulta de ejemplo:

```bash
sqlite3 output/airbnb_analitica.db "SELECT rango_precio, COUNT(*) FROM Listings_Limpio GROUP BY rango_precio;"
```

## Ejemplo de ejecución del proceso ETL

Extracto del log de una ejecución real (`logs/log_YYYYMMDD_HHMMSS.txt`):

```
2026-10-05 09:01:52 - INFO - [etl.main] === INICIO DEL PROCESO ETL AIRBNB BOGOTÁ ===
2026-10-05 09:01:52 - INFO - [etl.extraccion] Conexión exitosa a MongoDB (localhost:27017), base de datos 'Airbnb'.
2026-10-05 09:01:53 - INFO - [etl.extraccion] Extracción exitosa: 19187 registros y 78 columnas extraídos de la colección 'Listings'.
2026-10-05 09:02:47 - INFO - [etl.extraccion] Extracción exitosa: 7003255 registros y 5 columnas extraídos de la colección 'Calendar'.
2026-10-05 09:02:48 - WARNING - [etl.transformacion] [Listings] Columnas 100% vacías eliminadas: ['host_verifications']
2026-10-05 09:02:48 - INFO - [etl.transformacion] [Listings] Limpieza de nulos/duplicados: de 19187 a 18992 registros (duplicados: 0, filas vacías: 0, nulos en columnas críticas: 195).
2026-10-05 09:02:48 - INFO - [etl.transformacion] Atípicos en 'price': 1410 registros fuera de [-70,519.56, 410,865.94] (marcados en 'precio_atipico', no eliminados).
2026-10-05 09:02:48 - WARNING - [etl.transformacion] [Listings] 'maximum_nights': 6 valores por encima de 1125 limitados a 1125.
2026-10-05 09:02:48 - INFO - [etl.transformacion] Precios categorizados por cuartiles en 'rango_precio'. Cortes: [19181.11, 110000.0, 161460.0, 230346.38, 448176567.0]
2026-10-05 09:03:12 - INFO - [etl.transformacion] --- TRANSFORMACIÓN FINALIZADA: listings=18992, reviews=527731, calendar=7003255, calendar_mensual=249431 registros ---
2026-10-05 09:03:14 - INFO - [etl.carga] Carga verificada en SQLite: 18992 registros en la tabla 'Listings_Limpio' (coincide con el DataFrame de origen).
2026-10-05 09:06:48 - INFO - [etl.carga] Exportación exitosa: 'Reviews_Transformado.xlsx' generado (527731 registros, 527732 filas con encabezados, 62.2 MB).
2026-10-05 09:07:20 - INFO - [etl.carga] --- CARGA FINALIZADA CON ÉXITO. Base de datos: output/airbnb_analitica.db ---
2026-10-05 09:07:20 - INFO - [etl.main] === FIN DEL PROCESO ETL (OK) en 328.8 segundos ===
```

## Integrantes y responsabilidades

> **PENDIENTE (completar por el equipo):** reemplazar con los datos reales.

| Integrante | Responsabilidades |
|---|---|
| _Nombre 1_ | _p. ej. Extracción (`extraccion.py`) y carga de datos en MongoDB_ |
| _Nombre 2_ | _p. ej. Análisis exploratorio (notebook)_ |
| _Nombre 3_ | _p. ej. Transformación (`transformacion.py`)_ |
| _Nombre 4_ | _p. ej. Carga (`carga.py`), logs e informe final_ |

## Notas

- Las rutas se calculan desde la ubicación de los archivos, por lo que el proyecto funciona sin importar
  desde qué carpeta se ejecute.
- Los precios están en **pesos colombianos (COP)** por noche.
- Las carpetas `output/` y `logs/` se generan al ejecutar y no se versionan (ver `.gitignore`).

## Referencias

- Inside Airbnb. *Get the Data — Bogotá, Colombia*. <https://insideairbnb.com/get-the-data/>
- Documentación de [pandas](https://pandas.pydata.org/docs/), [PyMongo](https://pymongo.readthedocs.io/)
  y [SQLite](https://www.sqlite.org/docs.html).
