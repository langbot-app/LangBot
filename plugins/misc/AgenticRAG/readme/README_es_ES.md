# AgenticRAG

AgenticRAG expone las bases de conocimiento configuradas para el flujo (pipeline) actual como una herramienta de LLM, de modo que un agente puede inspeccionar las bases de conocimiento disponibles y recuperar fragmentos relevantes bajo demanda.

## Qué hace

- Proporciona una única herramienta, `query_knowledge`.
- Admite dos acciones:
  - `list`: enumera las bases de conocimiento disponibles para el flujo actual.
  - `query`: recupera documentos relevantes de una o más bases de conocimiento seleccionadas.
- Devuelve los resultados de la recuperación como JSON para que el agente pueda continuar razonando sobre ellos.

## Diseño general

AgenticRAG no pretende ser un nuevo motor de RAG. Es un complemento de capa de control que cambia **quién decide cuándo debe ocurrir la recuperación**.

En lugar de que el ejecutor (runner) inyecte siempre conocimientos automáticamente antes de que el modelo responda, AgenticRAG traslada la recuperación al ciclo del agente:

- El modelo decide primero si es necesaria la recuperación.
- El modelo puede inspeccionar las bases de conocimiento disponibles.
- El modelo puede elegir una base de conocimiento o consultar varias en paralelo.
- La recuperación solo ocurre cuando el modelo lo solicita explícitamente.

Este diseño existe para resolver un problema específico: la recuperación ingenua siempre activa es sencilla, pero también introduce ruido, desperdicia contexto y genera fragmentos irrelevantes en muchos turnos.

## Detalles del diseño

Este complemento es intencionadamente ligero. No implementa un nuevo motor de RAG, sino que envuelve las API de recuperación de conocimiento integradas de LangBot:

- `list_pipeline_knowledge_bases()` para enumerar las bases de conocimiento visibles para la consulta actual.
- `retrieve_knowledge()` para recuperar las mejores k entradas de una o más bases de conocimiento seleccionadas.

El `query_id` lo inyecta el entorno de ejecución cuando se llama a la herramienta y luego se almacena dentro de `QueryBasedAPIProxy`. Debido a eso, el código de la herramienta solo necesita pasar parámetros de negocio como `kb_id` o `kb_ids`, `query_text` y `top_k`.

Aunque el entorno de ejecución subyacente puede admitir filtros de metadatos, este complemento no expone filtros directos al agente en el flujo actual de herramientas de agentes. Diferentes motores de conocimiento y backends vectoriales pueden usar diferentes campos de metadatos, formatos de valor y semántica de filtros, y el agente actualmente no tiene una fuente de esquema confiable para esos campos.

Versiones futuras pueden exponer el filtrado de metadatos después de que el ecosistema tenga una forma más unificada de describir los campos filtrables y los operadores para cada base de conocimiento.

## Cómo funciona

Una solicitud de AgenticRAG tiene cuatro etapas principales:

### 1. Desactivar la recuperación ingenua

Durante el `PromptPreProcessing`, el complemento verifica si el LLM activo admite llamadas a herramientas (tool calling).

- Si se admiten las llamadas a herramientas, borra los `_knowledge_base_uuids` del ejecutor para que se omita el paso normal de recuperación previa ingenua.
- Si no se admiten las llamadas a herramientas, mantiene habilitado el RAG ingenuo como respaldo para que la recuperación de la base de conocimiento no desaparezca por completo.

### 2. Inyectar la política de recuperación en el mensaje del sistema (system prompt)

Al mismo tiempo, AgenticRAG inyecta un mensaje de sistema adicional que le indica al modelo que:

- Las bases de conocimiento configuradas son la principal fuente de verdad para los hechos dentro del alcance.
- No hay recuperación automática de respaldo.
- Para preguntas sobre hechos, políticas, procedimientos, productos y preguntas específicas del dominio, debe preferir `query_knowledge`.

Esto es importante porque las descripciones de las herramientas por sí solas a menudo no son lo suficientemente fuertes como para cambiar el comportamiento del modelo de manera confiable.

### 3. Permitir que el modelo inspeccione y consulte las bases de conocimiento

El agente puede usar `query_knowledge` en dos pasos:

- `action="list"` para ver qué bases de conocimiento están disponibles.
- `action="query"` para buscar en una base de conocimiento o en varias en paralelo.

Para la recuperación de una sola base de conocimiento, el parámetro preferido es `kb_id`.
Para la recuperación de múltiples bases de conocimiento, use `kb_ids`.

### 4. Devolver los resultados de la recuperación como JSON estructurado

La herramienta combina los resultados, los anota con `knowledge_base_id` y devuelve un JSON para que el modelo pueda continuar con el razonamiento, el uso de herramientas o la respuesta final.

## Comportamiento de recuperación

Cuando AgenticRAG está habilitado, desactiva el procesamiento previo de RAG ingenuo automático del ejecutor para el flujo actual.

- La recuperación ya no se realiza automáticamente antes de que el modelo responda.
- La decisión de consultar una base de conocimiento es ahora una decisión deliberada del modelo a través de `query_knowledge`.
- Si el modelo no llama a la herramienta, no se inyectará ningún contenido de la base de conocimiento en el contexto.

Hay una excepción importante:

- Si el LLM activo no admite llamadas a herramientas, AgenticRAG mantiene habilitado el RAG ingenuo en lugar de desactivarlo.

Esto reduce el ruido de recuperación incondicional, pero también significa que el prompting es importante. Por lo tanto, la implementación actual utiliza **ambos**:

- Un mensaje de herramienta en `query_knowledge`.
- Un mensaje de sistema inyectado durante el `PromptPreProcessing`.

Juntos, sesgan el modelo hacia la recuperación para preguntas sobre hechos, políticas, procedimientos, productos y otras preguntas específicas del dominio.

## Por qué está diseñado de esta manera

Este complemento está optimizado para un compromiso específico:

- Mantener la infraestructura de base de conocimiento y recuperación existente de LangBot.
- Eliminar la recuperación innecesaria siempre activa.
- Permitir que el modelo tome decisiones de recuperación explícitas.
- Mantener el comportamiento de recuperación restringido al flujo actual.

En comparación con el RAG ingenuo, este diseño le brinda:

- Menos contexto irrelevante en los turnos que no necesitan acceso a la base de conocimiento.
- Mejor control sobre qué base de conocimiento se consulta.
- Espacio para la recuperación iterativa, la nueva consulta y el razonamiento sobre múltiples bases de conocimiento.

La desventaja también es real: si el modelo nunca llama a la herramienta, no aparecerá contenido de la base de conocimiento. Es por eso que el complemento agrega explícitamente mensajes orientados a la recuperación, en lugar de asumir que el modelo elegirá naturalmente la recuperación con la frecuencia suficiente.

Esta es también la razón por la cual el complemento ahora detecta la capacidad de llamada a herramientas antes de desactivar el RAG ingenuo. Sin esa protección, habilitar AgenticRAG en un modelo sin capacidad de herramientas rompería accidentalmente la recuperación de la base de conocimiento por completo.

## Límite de seguridad

Esta herramienta está restringida al flujo actual.

- El entorno de ejecución de LangBot también valida que el `kb_id` solicitado pertenezca al flujo actual antes de ejecutar la recuperación.

Esto significa que la inyección de mensajes por sí sola no debería permitir al agente consultar bases de conocimiento arbitrarias fuera de la configuración del flujo.

## Cómo usar

1. Instale y habilite el complemento.
2. Configure una o más bases de conocimiento en la configuración del agente local del flujo actual.
3. Deje que el agente llame a `query_knowledge`:
   - Comience con `action="list"` para inspeccionar las bases de conocimiento disponibles.
   - Luego llame a `action="query"` con `kb_id` para una base de conocimiento, o `kb_ids` para múltiples bases de conocimiento consultadas en paralelo.
   - Proporcione `query_text` y un `top_k` opcional para el recuento de resultados combinados.

## Parámetros

Para `action="query"`, la herramienta acepta actualmente:

- `kb_id`: UUID de la base de conocimiento de destino para la recuperación de una sola base de conocimiento; preferido cuando se consulta exactamente una.
- `kb_ids`: matriz opcional de UUID de bases de conocimiento de destino para la recuperación paralela de múltiples bases de conocimiento; utilícelo solo cuando consulte varias.
- `query_text`: texto de la consulta de recuperación.
- `top_k`: entero positivo opcional, por defecto `5`, aplicado al conjunto de resultados combinados.

Si la consulta de una base de conocimiento falla mientras que otras tienen éxito, la herramienta devuelve un objeto JSON con `results` y `failed_kbs` para que el agente pueda continuar con resultados parciales.

## Flujo típico

1. El agente enumera las bases de conocimiento disponibles.
2. El agente selecciona una base de conocimiento o un pequeño conjunto de ellas basándose en el nombre y la descripción.
3. El agente envía una consulta de recuperación enfocada.
4. El agente utiliza los fragmentos devueltos para responder o continuar con el uso de herramientas.

## Intención del Prompting

La capa de mensajes está diseñada para comunicar dos cosas al modelo:

- Estas bases de conocimiento son la fuente autorizada para la información dentro del alcance.
- No existe una recuperación automática de respaldo una vez que AgenticRAG está habilitado.

Sin esa guía, un LLM puede confiar demasiado en su conocimiento preentrenado y subutilizar la recuperación. La implementación actual, por lo tanto, refuerza la misma política tanto en la capa de mensajes del sistema como en la capa de mensajes de la herramienta.

## Registros (Logging)

El complemento ahora emite registros durante la ejecución de la herramienta para que pueda observar cómo el LLM está utilizando AgenticRAG en la práctica.

Verá registros para:

- Inicio de la llamada a la herramienta, incluyendo `query_id`, `action` y claves de parámetros.
- Inicio/fin de la enumeración de bases de conocimiento y cuántas son visibles.
- Inicio de la recuperación, incluyendo las bases de conocimiento seleccionadas, `top_k` y una vista previa abreviada de `query_text`.
- Inicio/éxito/falla de recuperación por cada base de conocimiento.
- Resumen final de la recuperación, incluyendo el recuento de resultados combinados, el recuento de bases de conocimiento fallidas y el recuento de resultados devueltos.

Los mensajes de registro típicos se ven así:

```text
[AgenticRAG] tool call started: query_id=123 action=query params_keys=['action', 'kb_id', 'query_text', 'top_k']
[AgenticRAG] retrieval requested: query_id=123 kb_ids=['kb-1'] kb_count=1 top_k=5 query='what is the refund policy'
[AgenticRAG] querying knowledge base: query_id=123 kb_id=kb-1 top_k=5
[AgenticRAG] knowledge base query succeeded: query_id=123 kb_id=kb-1 result_count=4
[AgenticRAG] retrieval completed: query_id=123 merged_results=4 failed_kbs=0
```
