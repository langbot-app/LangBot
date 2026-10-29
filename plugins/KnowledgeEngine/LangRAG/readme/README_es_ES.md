#LangRAG

Complemento del motor RAG (recuperación-generación aumentada) para LangBot.

Este complemento demuestra cómo crear un motor de conocimiento que maneje la ingestión de documentos y la recuperación de vectores utilizando la infraestructura incorporada de LangBot Host (incrustación de modelos y base de datos de vectores).

## Características

-**Integración de analizador externo**: prefiere contenido analizado previamente de un complemento de analizador como GeneralParsers, incluidas secciones estructuradas y metadatos de documentos.
-**Análisis interno alternativo**: incluye un analizador integrado como recurso alternativo cuando no se configura ningún analizador externo
-**Múltiples estrategias de índice**- Fragmentación plana, fragmentación padre-hijo, pares de preguntas y respuestas generados por LLM
-**Recuperación flexible**- Búsqueda vectorial, de texto completo o híbrida
-**Reescritura de consultas**- Estrategias HyDE, multiconsulta y paso atrás para mejorar la recuperación
-**Fragmento configurable**- División recursiva de caracteres con tamaño de fragmento personalizado y superposición
-**Fragmentación según secciones**: cuando hay secciones estructuradas disponibles, la fragmentación conserva los encabezados, la información de las páginas y los límites de las tablas.
-**Expansión de contexto**: opcionalmente, agrega fragmentos adyacentes alrededor de cada visita para obtener un contexto de recuperación más rico.
-**Gestión de documentos**- Eliminar vectores indexados por documento

## Arquitectura

```
┌─────────────────────────────────┐
│         LangBot Core            │
│  (Embedding / VDB / Storage)    │
└──────────┬──────────────────────┘
           │ RPC (IPC)
┌──────────▼──────────────────────┐
│          LangRAG                │
│  ┌───────────────────────────┐  │
│  │    Knowledge Engine       │  │
│  │  Parse → Chunk → Embed   │  │
│  │      → Store / Search    │  │
│  └───────────────────────────┘  │
└─────────────────────────────────┘
```

## Flujo de ingestión

LangRAG ahora prefiere la salida del analizador proporcionada por LangBot Host:

1. LangBot lee el archivo cargado
2. Un complemento de Parser como GeneralParsers extrae "texto", "secciones" y "metadatos".
3. LangRAG ingiere ese resultado estructurado directamente
4. Si no hay salida del analizador disponible, LangRAG recurre a su analizador interno.
5. La estrategia de índice seleccionada crea pares de fragmentos/preguntas y respuestas
6. LangBot Host genera incrustaciones y almacena vectores.

Esto significa que LangRAG funciona mejor cuando se combina con un complemento de análisis externo.

## Configuración

### Creación de base de conocimientos

| Parámetro | Descripción | Predeterminado |
|-----------|-------------|---------|
|`embedding_model_uuid`| Modelo de incrustación | Requerido |
|`tipo_índice`| Estrategia de índice:`chunk`,`parent_child`o`qa`|`trozo`|
|`tamaño_fragmento`| Caracteres por fragmento | 512 |
|`superposición`| Superposición entre trozos | 50 |
|`parent_chunk_size`| Tamaño del fragmento principal (solo parent_child) | 2048 |
|`child_chunk_size`| Tamaño del fragmento secundario (solo parent_child) | 256 |
|`qa_llm_model_uuid`| LLM para generación de preguntas y respuestas (solo qa) | - |
|`preguntas_por_fragmento`| Preguntas para generar por fragmento (solo qa) | 1 |

### Recuperación

| Parámetro | Descripción | Predeterminado |
|-----------|-------------|---------|
|`top_k`| Número de resultados a devolver | 5 |
|`tipo_búsqueda`| Modo de búsqueda:`vector`,`full_text`o`hybrid`|`vector`|
|`query_rewrite`| Estrategia de reescritura:`off`,`hyde`,`multi_query`o`step_back`|`apagado`|
|`rewrite_llm_model_uuid`| LLM para reescritura de consultas (cuando la reescritura está habilitada) | - |
|`ventana_contexto`| Número de fragmentos adyacentes que se agregarán alrededor de cada visita | 0 |

## Estrategias de índice

-**fragmento**: fragmentación plana predeterminada. Divide los documentos en fragmentos de tamaño fijo e incrusta cada uno de ellos directamente. Cuando las secciones del analizador están disponibles, los fragmentos se crean sección por sección en lugar de aplanar todo el documento.
-**parent_child**- Fragmentación de dos niveles. Se divide en fragmentos principales grandes y luego en fragmentos secundarios más pequeños. Incorpora fragmentos secundarios pero devuelve el texto principal para un contexto más rico. Cuando las secciones del analizador están disponibles, las secciones se utilizan como límites principales naturales.
-**qa**- Pares de preguntas y respuestas generados por LLM. Fragmenta el texto, utiliza un LLM para generar pares de preguntas y respuestas por fragmento e integra las preguntas. Cuando las secciones del analizador están disponibles, la generación de preguntas y respuestas también se vuelve consciente de las secciones.

## Reescritura de consultas

-**hyde**- Incrustación de documentos hipotéticos. Genera una respuesta hipotética a la consulta y luego incrusta esa respuesta para su recuperación.
-**multi_query**: genera 3 variantes de consulta, busca con cada una y combina resultados por puntuación.
-**step_back**: genera una pregunta más abstracta y busca tanto con la consulta original como con la abstracta.

## Emparejamiento con GeneralParsers

GeneralParsers es actualmente el analizador recomendado para LangRAG porque puede proporcionar:

- extracción de PDF más limpia
- secciones estructuradas
- texto que preserva la tabla
- metadatos a nivel de documento
- OCR opcional y descripciones de imágenes a través de un modelo de visión

LangRAG consume esos resultados del analizador directamente durante la ingestión, lo que generalmente produce mejores fragmentos y una mejor calidad de recuperación que el analizador alternativo.

## Desarrollo

```bash
pip install -r requirements.txt
cp .env.example .env
```

Configure`DEBUG_RUNTIME_WS_URL`y`PLUGIN_DEBUG_KEY`en`.env`, luego ejecútelo con su depurador IDE.

## Enlaces

- [Documentación de LangBot](https://langbot.app/docs/)
