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
python src/main.py                  # ETL completo (~3 minutos con los datos completos)
python src/main.py --muestra 2000   # prueba rápida con 2000 registros por colección
```

> Ejecutar con `--muestra` sobrescribe los archivos de `output/

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
| `airbnb_analitica.db` | Base SQLite con las tablas `Listings_Limpio`, `Reviews_Limpio` y `Calendar_Mensual` |
| `Listings_Transformado.xlsx` | Anuncios limpios |
| `Reviews_Transformado.xlsx` | Reseñas limpias |
| `Calendar_Mensual_Transformado.xlsx` | Resumen mensual del calendario por anuncio |

`Calendar` tiene más de 7 millones de filas (un registro por anuncio y día) y no cabe en Excel, por eso en la base
y en XLSX se guarda su resumen mensual (días disponibles y ocupados y porcentaje de ocupación por anuncio y mes).
Consulta de ejemplo:

```bash
sqlite3 output/airbnb_analitica.db "SELECT rango_precio, COUNT(*) FROM Listings_Limpio GROUP BY rango_precio;"
```

## Ejemplo de ejecución del proceso ETL

Extracto del log de una ejecución real (`logs/log_YYYYMMDD_HHMMSS.txt`):

```
2026-10-10 08:42:02 - INFO [etl.main] Inicio del proceso ETL Airbnb Bogotá
2026-10-10 08:42:02 - INFO [etl.extraccion] Conexión a MongoDB (localhost:27017), base de datos 'Airbnb'.
2026-10-10 08:42:04 - INFO [etl.extraccion] Se extrajeron 19187 registros de la colección 'Listings'.
2026-10-10 08:42:40 - INFO [etl.extraccion] Se extrajeron 7003255 registros de la colección 'Calendar'.
2026-10-10 08:42:41 - WARNING [etl.transformacion] Se eliminaron columnas vacías: ['host_verifications']
2026-10-10 08:42:41 - INFO [etl.transformacion] Registros antes de limpiar: 19187, después: 18992. Se eliminaron 0 duplicados, 0 filas vacías y 195 con nulos críticos
2026-10-10 08:42:41 - INFO [etl.transformacion] Se marcaron 1410 atípicos en 'price' (fuera de -70,520 a 410,866). No se eliminan, solo se marcan.
2026-10-10 08:42:41 - WARNING [etl.transformacion] Los valores de 'maximum_nights' se limitaron a un máximo de 1125
2026-10-10 08:42:41 - INFO [etl.transformacion] Precios categorizados en 'rango_precio'.
2026-10-10 08:43:02 - INFO [etl.transformacion] TRANSFORMACIÓN FINALIZADA
2026-10-10 08:43:03 - INFO [etl.carga] Carga exitosa en SQLite: 'Listings_Limpio' con 18992 registros.
2026-10-10 08:43:05 - INFO [etl.carga] Carga exitosa en SQLite: 'Reviews_Limpio' con 527731 registros.
2026-10-10 08:43:06 - INFO [etl.carga] Carga exitosa en SQLite: 'Calendar_Mensual' con 249431 registros.
2026-10-10 08:44:47 - INFO [etl.carga] Exportación exitosa: 'Reviews_Transformado.xlsx' guardado (63.7 MB).
2026-10-10 08:45:17 - INFO [etl.carga] CARGA FINALIZADA. Base de datos guardada en: output\airbnb_analitica.db
2026-10-10 08:45:17 - INFO [etl.main] Fin del proceso. Duración: 194.3 segundos
```

## Integrantes y responsabilidades

El grupo está conformado por Julián Clavijo Restrepo, Evelyn Muñetones Alvarez, Christian Camilo Pereira Berte y
Brayan Antonio Sanabria Ramirez. Christian, Julián y Brayan se encargaron de los procesos de extracción, transformación y
carga, y del notebook de exploración. Evelyn se encargó del informe y de las validaciones.

## Notas

- Las rutas se calculan desde la ubicación de los archivos, por lo que el proyecto funciona sin importar
  desde qué carpeta se ejecute.
- Los precios están en **pesos colombianos (COP)** por noche.
- Las carpetas `output/` y `logs/` se generan al ejecutar y no se versionan (ver `.gitignore`).

## Referencias

- Inside Airbnb. *Get the Data — Bogotá, Colombia*. <https://insideairbnb.com/get-the-data/>
- Documentación de [pandas](https://pandas.pydata.org/docs/), [PyMongo](https://pymongo.readthedocs.io/)
  y [SQLite](https://www.sqlite.org/docs.html).
