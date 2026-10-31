# FastGPTConnector

Recupere conocimiento de las bases de conocimiento de FastGPT utilizando la API de FastGPT.

## Acerca de FastGPT

FastGPT es un sistema de respuesta a preguntas basado en bases de conocimiento de código abierto construido sobre modelos LLM. Proporciona capacidades listas para usar de procesamiento de datos e invocación de modelos para escenarios complejos de respuesta a preguntas.

## Características

- Buscar y recuperar conocimiento de conjuntos de datos/bases de conocimiento de FastGPT
- Soporta múltiples modos de búsqueda (embedding, recuperación de texto completo, recuperación mixta)
- Umbrales de similitud y límites de tokens configurables
- Re-ranking opcional para mejores resultados
- Optimización de consultas con modelos de extensión

## Configuración

Este complemento requiere los siguientes parámetros de configuración:

### Parámetros Requeridos

- **api_base_url**: URL base para la API de FastGPT
  - Para despliegue local: `http://localhost:3000` (predeterminado)
  - Para servidor remoto: La URL de su servidor (ej., `https://tu-dominio.com`)
- **api_key**: Su clave de API de FastGPT
  - Formato: `fastgpt-xxxxx`
- **dataset_id**: El ID de su base de conocimiento/conjunto de datos de FastGPT

### Parámetros Opcionales

- **limit** (predeterminado: 5000): Número máximo de tokens a recuperar
- **similarity** (predeterminado: 0.0): Puntuación mínima de similitud (0-1)
- **search_mode** (predeterminado: embedding): El método de búsqueda a utilizar
  - `embedding`: Búsqueda semántica por embeddings
  - `fullTextRecall`: Búsqueda de texto completo por palabras clave
  - `mixedRecall`: Búsqueda mixta combinando ambos métodos
- **using_rerank** (predeterminado: false): Si se debe utilizar el re-ranking
- **dataset_search_using_extension_query** (predeterminado: false): Si se debe utilizar la optimización de consultas
- **dataset_search_extension_model** (opcional): Modelo para la optimización de consultas
- **dataset_search_extension_bg** (opcional): Descripción de fondo para la optimización de consultas

## Cómo Obtener los Valores de Configuración

### Obtener su Clave de API de FastGPT

1. Acceda a su instancia de FastGPT (ej., `http://localhost:3000`)
2. Navegue a la sección de gestión de API o configuración
3. Cree o copie su clave de API (formato: `fastgpt-xxxxx`)

### Obtener su ID de Conjunto de Datos

1. En FastGPT, vaya a su lista de bases de conocimiento
2. Haga clic en una base de conocimiento para ver sus detalles
3. El ID del conjunto de datos se puede encontrar en la URL o en la página de detalles del conjunto de datos

## Referencia de la API

Este complemento utiliza la API de Prueba de Búsqueda de Conjuntos de Datos de FastGPT:
- Endpoint: `POST /api/core/dataset/searchTest`
- Documentación: https://doc.fastgpt.io/docs/introduction/development/openapi/dataset

## Métodos de Búsqueda

### Búsqueda por Embeddings (Embedding Search)
Utiliza la similitud semántica basada en embeddings vectoriales. Es la mejor opción para comprender la intención de la consulta y encontrar contenido relacionado semánticamente.

### Recuperación de Texto Completo (Full-Text Recall)
Búsqueda tradicional de texto completo basada en palabras clave. Es la mejor opción para encontrar coincidencias exactas y términos específicos.

### Recuperación Mixta (Mixed Recall)
Combina los métodos de búsqueda por embeddings y de texto completo. Proporciona resultados equilibrados con comprensión semántica y coincidencia de palabras clave.
