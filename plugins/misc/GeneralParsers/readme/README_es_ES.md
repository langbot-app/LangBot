# GeneralParsers

Complemento oficial de análisis (parser) de LangBot que extrae texto estructurado de archivos para los complementos de KnowledgeEngine (por ejemplo, LangRAG).

## Formatos compatibles

| Formato | Tipo MIME | Analizador |
|---------|-----------|------------|
| PDF | `application/pdf` | Extracción basada en PyMuPDF sensible al diseño con tablas, marcadores de página y mejora de visión opcional |
| DOCX | `application/vnd.openxmlformats-officedocument.wordprocessingml.document` | Extracción con python-docx con análisis de párrafos/tablas y reconocimiento de imágenes incrustadas opcional |
| Markdown | `text/markdown` | Convierte a HTML, luego extracción estructurada (encabezados, listas, bloques de código, tablas) |
| HTML | `text/html` | Extracción con BeautifulSoup (elimina automáticamente script/style) |
| TXT | `text/plain` | Detección automática de codificación (chardet) |
| Imágenes | `image/png`, `image/jpeg`, `image/webp`, `image/gif`, `image/bmp`, `image/tiff` | Reconocimiento directo basado en visión cuando se configura un modelo de visión |

## Arquitectura

```
┌──────────────────────────────────────────────┐
│  KnowledgeEngine Plugin (p. ej. LangRAG)     │
│  Chunk → Embedding → Store → Retrieve        │
└──────────────────┬───────────────────────────┘
                   │ invoke_parser (RPC)
┌──────────────────▼───────────────────────────┐
│          GeneralParsers                      │
│                                              │
│  File bytes → Format detection → Parse       │
│                                              │
│  ParseResult:                                │
│    ├── text: Texto completo extraído         │
│    ├── sections: Secciones divididas por     │
│    │   encabezados                           │
│    │   └── TextSection(contenido, encabezado, │
│    │                   nivel)                │
│    └── metadata: nombre de archivo, tipo MIME,│
│                   etc.                       │
└──────────────────────────────────────────────┘
```

## Características

- **Soporte de modelo de visión opcional** - Configure un LLM con capacidad de visión para realizar OCR en páginas de PDF escaneadas, reconocer imágenes incrustadas en PDF/DOCX y analizar cargas directas de imágenes.
- **Análisis de PDF mejorado** - La extracción basada en PyMuPDF preserva los límites de página, combina las tablas en la salida y emite metadatos de documentos más ricos.
- **Manejo de PDF escaneados** - Detecta páginas probablemente escaneadas y utiliza el modelo de visión para OCR cuando está configurado.
- **Reconocimiento de imágenes en varios formatos** - Las imágenes incrustadas en PDF/DOCX y las cargas directas de imágenes pueden convertirse en texto de reconocimiento en línea para la recuperación posterior.
- **Filtrado de encabezado/pie de página** - Los encabezados y pies de página repetidos se detectan y eliminan de la salida del PDF.
- **Reconocimiento de estructura de sección** - Detecta encabezados de estilo Markdown (`# ~ ######`) y divide la salida en secciones niveladas.
- **Tabla a Markdown** - Las tablas en PDF/HTML/Markdown se convierten al formato de tabla de Markdown.
- **Análisis asíncrono** - El análisis de archivos se ejecuta en un grupo de subprocesos para evitar bloquear el bucle de eventos.
- **Detección automática de codificación** - Utiliza chardet para la detección de codificación, admite GBK, UTF-8, etc.
- **Respaldo de formato** - Los formatos no compatibles se intentan analizar automáticamente como texto plano.

## Configuración

El complemento expone un elemento de configuración opcional:

- `vision_llm_model_uuid`: un LLM con capacidad de visión utilizado para OCR de páginas escaneadas, reconocimiento de imágenes incrustadas en PDF/DOCX y análisis directo de imágenes.

Si esta opción se deja vacía, GeneralParsers seguirá funcionando normalmente, pero la comprensión de imágenes se basará en marcadores de posición y el análisis de PDF utilizará solo la extracción de texto/diseño.

## Uso

1. Instale este complemento en LangBot.
2. Opcionalmente, configure un modelo de visión si desea OCR para archivos PDF escaneados, reconocimiento de imágenes DOCX/PDF o análisis directo de imágenes.
3. Al cargar archivos a una base de conocimiento, seleccione GeneralParsers como el analizador.
4. Los resultados del análisis se pasan automáticamente al complemento KnowledgeEngine para su posterior procesamiento.

## Estructura de salida

GeneralParsers devuelve un `ParseResult` estructurado que contiene:

- `text`: el texto completo extraído.
- `sections`: secciones de texto con conocimiento de los encabezados para estrategias de fragmentación que prefieren la estructura.
- `metadata`: metadatos del documento como nombre de archivo, tipo MIME, recuento de páginas, presencia de tablas, banderas de páginas escaneadas y estadísticas de uso de visión.

Los metadatos recientes del analizador de PDF incluyen campos como:

- `page_count` (recuento de páginas)
- `word_count` (recuento de palabras)
- `has_tables` (contiene tablas)
- `has_scanned_pages` (contiene páginas escaneadas)
- `headers_footers_removed` (encabezados/pies de página eliminados)
- `vision_used` (visión utilizada)
- `vision_tasks_count` (recuento de tareas de visión)
- `vision_scanned_pages_count` (recuento de páginas escaneadas por visión)
- `vision_images_described_count` (recuento de imágenes descritas por visión)

## Desarrollo

```bash
pip install -r requirements.txt
cp .env.example .env
```

Configure `DEBUG_RUNTIME_WS_URL` y `PLUGIN_DEBUG_KEY` en el archivo `.env`, luego ejecútelo con el depurador de su IDE.
