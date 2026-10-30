# Conector RAGFlow

Recupere conocimientos o almacene archivos en las bases de conocimientos de RAGFlow utilizando la API de RAGFlow.

## Acerca de RAGFlow

RAGFlow es un motor RAG (Recuperación-Generación Aumentada) de código abierto basado en una comprensión profunda de los documentos. Proporciona capacidades veraces para responder preguntas con citas bien fundadas de varios datos con formato complejo.

## Características

- Recuperar fragmentos de conocimiento de conjuntos de datos/bases de conocimiento de RAGFlow
- Cargue e ingiera archivos en conjuntos de datos RAGFlow con análisis automático
- Soporte para múltiples conjuntos de datos en una sola consulta
- Umbrales de similitud configurables y pesos vectoriales.
- Búsqueda híbrida que combina palabras clave y similitud de vectores.
- Construcción del gráfico de conocimiento GraphRAG de activación automática después de la ingestión
- Resumen jerárquico de activación automática de RAPTOR después de la ingestión
- Validación de ID del conjunto de datos en la creación de la base de conocimientos.
- Devuelve resultados con metadatos enriquecidos que incluyen puntuaciones de similitud de términos y vectores

## Configuración

Este complemento requiere los siguientes parámetros de configuración:

### Parámetros requeridos (Configuración de creación)

-**api_base_url**: URL base para la API RAGFlow
  - Para implementación local:`http://localhost:9380`(predeterminado)
  - Para servidor remoto: la URL de su servidor (por ejemplo,`http://su-dominio.com:9380`)
-**api_key**: Su clave API de RAGFlow de su instancia de RAGFlow
-**dataset_ids**: ID de conjuntos de datos separados por comas para buscar
  - Formato:`"conjunto de datos_id1, conjunto de datos_id2, conjunto de datos_id3"`
  - Ejemplo:`"b2a62730759d11ef987d0242ac120004,a3b52830859d11ef887d0242ac120005"`

### Parámetros opcionales (configuraciones de creación)

-**auto_graphrag**(predeterminado: falso): activa automáticamente la construcción del gráfico de conocimiento GraphRAG después de la ingestión del archivo
-**auto_raptor**(predeterminado: falso): activa automáticamente el resumen jerárquico de RAPTOR después de la ingesta de archivos

### Parámetros opcionales (configuraciones de recuperación)

-**top_k**(predeterminado: 1024): número máximo de resultados recuperados
-**similitud_umbral**(predeterminado: 0,2): puntuación mínima de similitud (0-1)
-**vector_similarity_weight**(predeterminado: 0,3): Peso para la similitud de vectores en la búsqueda híbrida (0-1)
-**page_size**(predeterminado: 30): número de resultados por página
-**palabra clave**(predeterminado: falso): use LLM para extraer palabras clave de la consulta para mejorar la recuperación
-**rerank_id**: ID de modelo de reclasificación configurado en RAGFlow (por ejemplo,`BAAI/bge-reranker-v2-m3`)
-**use_kg**(predeterminado: falso): habilita la recuperación del gráfico de conocimiento

## Cómo obtener valores de configuración

### Obteniendo su clave API RAGFlow

1. Acceda a su instancia de RAGFlow (por ejemplo,`http://localhost:9380`)
2. Vaya a la sección**Configuración de usuario**>**API**
3. Genere o copie su clave API (formato:`ragflow-xxxxx`)

### Obteniendo los ID de su conjunto de datos

1. En RAGFlow, vaya a su base de conocimientos/lista de conjuntos de datos
2. Haga clic en un conjunto de datos para ver sus detalles.
3. El ID del conjunto de datos normalmente se muestra en la URL o en los detalles del conjunto de datos.
4. Para múltiples conjuntos de datos, recopile todos los ID y únalos con comas.

## Referencia de API

Este complemento utiliza las siguientes API de RAGFlow:
- Recuperación:`POST /api/v1/recuperación`
- Subir documentos:`POST /api/v1/datasets/{dataset_id}/documents`
- Analizar documentos:`POST /api/v1/datasets/{dataset_id}/chunks`
- Eliminar documentos:`DELETE /api/v1/datasets/{dataset_id}/documents`
- Construcción de GraphRAG:`POST /api/v1/datasets/{dataset_id}/run_graphrag`
- Construcción de RAPTOR:`POST /api/v1/datasets/{dataset_id}/run_raptor`
- Listar conjuntos de datos (validación):`GET /api/v1/datasets`
- Documentación: https://ragflow.io/docs/dev/http_api_reference

## Método de recuperación

RAGFlow emplea un enfoque de recuperación híbrido:
-**Similitud de palabras clave**: concordancia tradicional basada en palabras clave
-**Similitud vectorial**: similitud semántica mediante incrustaciones
-**Combinación ponderada**: combina ambos métodos con pesos configurables
-**Gráfico de conocimiento**: recuperación opcional basada en gráficos para respuestas basadas en relaciones
-**Reclasificación**: modelo de reclasificación opcional para mejorar la calidad de los resultados.

El parámetro`vector_similarity_weight`controla el equilibrio entre los métodos de palabras clave y vectores.
