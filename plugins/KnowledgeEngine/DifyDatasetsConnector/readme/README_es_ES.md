# DifyDatasetsConnector

Recupere conocimientos o almacene archivos en las bases de conocimientos de Dify utilizando la API de Dify.

## Configuración

Agregue una base de conocimientos externa en LangBot y seleccione "DifyDatasetsConnector" como tipo de recuperador de conocimientos.

### Configuración de creación (establecida al crear una base de conocimientos)

-**api_base_url**: URL base para la API de Dify
  - Para Dify Cloud:`https://api.dify.ai/v1`(predeterminado)
  - Para instancias autohospedadas: la URL de su servidor (por ejemplo,`http://localhost/api`o`https://your-domain.com/api`)
-**dify_apikey**: Su clave API de Dify de su instancia de Dify
-**dataset_id**: el ID de su base de conocimientos/conjunto de datos de Dify

### Configuración de recuperación (ajustable por consulta)

-**search_method**(predeterminado: semantic_search): el método de búsqueda a utilizar
  -`keyword_search`: búsqueda basada en palabras clave
  -`semantic_search`: búsqueda de similitud semántica (predeterminado)
  -`full_text_search`: búsqueda de texto completo
  -`hybrid_search`: búsqueda híbrida que combina semántica y texto completo
-**top_k**(predeterminado: 5): número máximo de resultados recuperados
-**score_threshold_enabled**(predeterminado: falso): si se habilita el filtrado de umbral de puntuación
-**score_threshold**(predeterminado: 0,5): puntuación de relevancia mínima (0-1), solo se muestra cuando el umbral de puntuación está habilitado
-**reranking_enable**(predeterminado: falso): habilita la reclasificación para mejorar la calidad de los resultados. El modelo de reclasificación se obtiene automáticamente de la configuración de su conjunto de datos de Dify; primero configure el modelo de reclasificación en la consola de Dify.

## Cómo obtener valores de configuración

### Obteniendo su clave API de Dify

1. Vaya a https://cloud.dify.ai/
2. Navegue a la página de su base de conocimientos.
3. Haga clic en "ACCESO API" en la barra lateral izquierda
4. Cree o copie su clave API desde la sección "Claves API"

### Obteniendo su ID de conjunto de datos

1. En la lista de la base de conocimientos de Dify, haga clic en su base de conocimientos.
2. El ID del conjunto de datos está en la URL:`https://cloud.dify.ai/datasets/{dataset_id}`
3. O puede encontrarlo en la página de documentación de API de su base de conocimientos.

### Configuración de reclasificación

1. En la consola Dify, vaya a la configuración de su conjunto de datos.
2. Habilite la reclasificación y seleccione un modelo de reclasificación (por ejemplo,`cohere/rerank-v3.5`)
3. Guarde la configuración
4. En LangBot, habilite la opción "Habilitar reclasificación": el complemento utilizará automáticamente el modelo configurado en Dify.

## Referencia de API

Este complemento utiliza la API Dify Dataset:
- Recuperación:`POST /v1/datasets/{dataset_id}/retrieve`
- Información del conjunto de datos:`GET /v1/datasets/{dataset_id}`
- Carga de documentos:`POST /v1/datasets/{dataset_id}/document/create-by-file`
- Eliminación de documentos:`DELETE /v1/datasets/{dataset_id}/documents/{document_id}`
- Documentación: https://docs.dify.ai/
