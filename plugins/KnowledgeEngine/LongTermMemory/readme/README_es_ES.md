# LongTermMemory

Plugin de memoria a largo plazo para LangBot con un diseño de doble capa:

- L1 perfil principal inyectado en el prompt del sistema
- L2 memoria episódica recuperada mediante búsqueda vectorial e inyectada en el contexto

## Qué hace

- Expone una herramienta `remember` para escrituras de memoria episódica
- Expone una herramienta `recall_memory` para la búsqueda activa de memoria episódica con filtros controlados
- Expone una herramienta `update_profile` para actualizaciones estables de perfil
- Expone una herramienta `forget` para la eliminación de memorias episódicas específicas iniciada por el agente
- Inyecta la memoria del perfil y la identidad del hablante actual a través de un EventListener
- Utiliza un EventListener para recuperar e inyectar memorias episódicas relevantes antes de la invocación del modelo
- Proporciona un comando `!memory` para inspección y depuración
- Proporciona una página web **Consola de Memoria** para inspección visual: perfiles, episodios (con paginación), registro de auditoría, exportaciones, una comprobación de salud de aislamiento de metadatos y la última instantánea de inyección de memoria
- Proporciona `!memory list [page]` para examinar memorias episódicas con paginación
- Proporciona `!memory forget <episode_id>` para eliminar un episodio específico
- Proporciona `!memory search <query>` para buscar episodios (los resultados incluyen IDs de episodios)
- Proporciona un comando `!memory export` para exportar perfiles L1 para la sesión actual como JSON
- Reemplaza automáticamente episodios antiguos relacionados cuando se almacena una corrección/actualización de hechos/aclaración

## Diseño General

Este plugin no intenta volcar todo el historial de chat en el contexto. En su lugar, divide la memoria a largo plazo en dos capas con diferentes comportamientos de almacenamiento y recuperación:

- **L1 perfil principal**: hechos estables y de baja frecuencia como nombres, preferencias, identidad y notas de larga duración
- **L2 memoria episódica**: hechos temporales y situacionales como eventos recientes, planes y experiencias

Esta división existe por una razón:

- Los datos estables del perfil son económicos y confiables de inyectar en el prompt del sistema
- La memoria episódica sigue creciendo con el tiempo, por lo que debe recuperarse bajo demanda en lugar de inyectarse completamente en cada turno
- Los agentes deben actualizar los hechos estables del perfil de manera diferente a las memorias tipo evento

## En qué se diferencia de la memoria estilo asistente personal de OpenClaw

Recientemente, muchos sistemas de agentes han discutido diseños como OpenClaw: memoria a largo plazo almacenada principalmente como archivos de texto legibles por el usuario como `MEMORY.md`, combinada con resúmenes, reflexión y lógica de recuperación ligera.

Ese enfoque tiene fortalezas claras:

- la memoria es totalmente transparente para el usuario
- el texto plano es naturalmente fácil de respaldar, sincronizar y controlar versiones
- se adapta muy bien a flujos de trabajo personales de un solo usuario, un solo asistente y alta continuidad
- cuando el volumen de memoria se mantiene pequeño, la comprensión de texto completo puede ser "suficientemente buena"

Pero LongTermMemory en LangBot está resolviendo un problema diferente. Un despliegue típico de LangBot se parece más a:

- un bot sirviendo múltiples chats grupales y chats privados
- una instancia del plugin manejando múltiples sesiones y múltiples hablantes
- memoria que incluye contexto grupal compartido, perfil del hablante actual y hechos episódicos a nivel de sesión
- límites de aislamiento explícitos entre sesiones, bots y hablantes

Debido a eso, no adoptamos un diseño de "un solo archivo de texto como fuente de verdad". Elegimos una arquitectura en capas que coincide mejor con el modelo de tiempo de ejecución multisesión de LangBot.

### Para qué está optimizada la memoria tipo OpenClaw

Abstactamente, ese diseño está optimizado para:

- **asistentes personales de un solo usuario**
- **texto legible por humanos como la forma principal de memoria a largo plazo**
- **transparencia, editabilidad y continuidad narrativa**
- **la suposición de que el tamaño de la memoria se mantiene manejable y el usuario está dispuesto a curarla directamente**

Es un ajuste muy razonable para compañeros de IA personales, copilotos de investigación y flujos de trabajo de asistentes privados.

### Por qué LangBot no simplemente copia ese modelo

LongTermMemory está diseñado en torno a diferentes restricciones operativas: múltiples sesiones, múltiples hablantes, aislamiento explícito, inyección controlada y recuperación episódica recuperable.

Si convirtiéramos la memoria a largo plazo en un archivo narrativo como `MEMORY.md`, aparecerían rápidamente varios problemas:

- **El aislamiento sería difícil**
  - ¿cómo deberían coexistir de forma segura las memorias del grupo A, el grupo B y el chat privado C?
  - ¿cómo se separa limpiamente el perfil estable de un solo hablante de un registro narrativo compartido?
- **La granularidad de la inyección sería inestable**
  - los prompts del sistema necesitan un estado de perfil estable, no un diario cronológico completo
  - la recuperación automática necesita los fragmentos de memoria más relevantes para la consulta actual, no toda la historia
- **Los límites multiusuario son de primera clase en LangBot**
  - en un asistente personal, "el usuario" suele ser una persona
  - en LangBot, el hablante actual, la sesión actual y el bot actual importan
- **La inyección automática y la recuperación activa son necesidades diferentes**
  - los datos de perfil estables deben inyectarse de forma consistente
  - la memoria episódica debe recuperarse selectivamente
  - forzar ambos en una sola forma de memoria de solo texto se vuelve incómodo

### El compromiso que hicimos

Así que el diseño de LongTermMemory es esencialmente este compromiso:

- **Lo que tomamos prestado de esa filosofía**
  - la memoria no debe tratarse solo como un almacén de vectores de caja negra
  - el perfil estable, la memoria temporal y el ajuste de comportamiento a largo plazo importan
  - no todo debe volcarse en el contexto en cada turno

- **Donde nos diferenciamos deliberadamente**
  - no utilizamos un diario de texto narrativo como la única fuente de verdad de la memoria
  - dividimos explícitamente el perfil estable y la memoria episódica
  - priorizamos el aislamiento entre sesiones, hablantes y bots
  - permitimos que la memoria L2 se conecte naturalmente al sistema de KB / recuperación de LangBot en lugar de depender solo de la lectura de texto completo

En resumen:

- OpenClaw responde principalmente a: "¿Cómo debería un asistente personal mantener una memoria a largo plazo legible, editable y reflexiva?"
- LongTermMemory responde principalmente a: "¿Cómo debería un bot que trabaja en grupos y chats privados mantener un estado de perfil estable y una memoria de experiencia recuperable bajo reglas de aislamiento explícitas?"

Ninguna dirección es universalmente "mejor". Optimizan para diferentes productos y diferentes modos de falla.

## Diseño

Este plugin permanece intencionalmente cerca de los puntos de extensión existentes de LangBot en lugar de requerir parches personalizados en el núcleo.

- El perfil L1 se almacena en el almacenamiento del plugin como JSON
- La memoria episódica L2 se almacena en la base de datos de vectores
- La recuperación de memoria se habilita por flujo de trabajo adjuntando el KnowledgeEngine de este plugin
- El plugin asume actualmente una única KB de memoria por instancia de plugin e aísla la memoria mediante metadatos

La implementación actual se basa en las APIs existentes de LangBot y el SDK. Si LangBot agrega más adelante APIs más explícitas orientadas a la memoria, APIs de identidad de sesión o APIs de registro de KB, el plugin podría simplificarse, pero la arquitectura actual seguiría siendo válida.

### Compatibilidad con el motor de base de datos de vectores

La memoria episódica L2 depende de campos de metadatos arbitrarios (`user_key`, `episode_id`, `tags`, `importance`, etc.) para el aislamiento y el filtrado. No todos los motores de base de datos de vectores de LangBot admiten metadatos arbitrarios:

| Motor | Metadatos arbitrarios | Soporte de LongTermMemory |
|---------|-------------------|----------------------|
| **Chroma** (predeterminado) | Sí | Soporte completo |
| **Qdrant** | Sí | Soporte completo |
| **SeekDB** | Sí | Soporte completo |
| **Milvus** | No (esquema fijo: `text`, `file_id`, `chunk_uuid`) | No soportado |
| **pgvector** | No (esquema fijo: `text`, `file_id`, `chunk_uuid`) | No soportado |

Milvus y pgvector utilizan un esquema de columnas fijo y descartan silenciosamente los campos de metadatos que no reconocen. Esto significa que el aislamiento basado en metadatos (filtrado por `user_key`) y los comandos de memoria episódica (`!memory list`, `!memory forget`, `!memory search`) no funcionarán correctamente en estos motores; los filtros se ignorarán y las consultas pueden devolver resultados fuera de alcance.

Si necesita usar LongTermMemory, utilice Chroma, Qdrant o SeekDB como su motor de base de datos de vectores.

## Cómo funciona

Un flujo de memoria a largo plazo de extremo a extremo tiene cuatro partes principales:

### 1. Escrituras de perfil L1

- El agente utiliza `update_profile` para escribir hechos estables
- Los datos se almacenan en el almacenamiento del plugin como JSON estructurado
- Los perfiles se almacenan en el ámbito de `session` o `speaker`

### 2. Escrituras episódicas L2

- El agente utiliza `remember` para escribir memorias tipo evento
- Cada memoria lleva metadatos como marca de tiempo, importancia, etiquetas y ámbito
- Esas memorias se vectorizan y almacenan en la base de datos de vectores a través del KnowledgeEngine del plugin

### 3. Inyección automática previa a la respuesta

- Durante `PromptPreProcessing`, el EventListener resuelve la identidad de la sesión actual
- Para L1:
  - carga el perfil de sesión compartido
  - carga el perfil del hablante actual
  - inyecta ambos, junto con la identidad del hablante actual, en `default_prompt`
- Para L2:
  - ejecuta una recuperación episódica utilizando el mensaje del usuario actual
  - las memorias recuperadas se inyectan como bloques de contexto factual

Así que tanto L1 como L2 entran en el contexto del modelo antes de la generación de la respuesta, pero en formas diferentes: L1 como memoria de prompt del sistema, L2 como contexto recuperado.

### 4. Búsqueda activa y depuración

- Si la inyección automática es insuficiente, el agente puede llamar a `recall_memory`
- Para inspección y depuración, puede usar `!memory`, `!memory profile`, `!memory search`, `!memory list` y `!memory forget`
- `!memory export` exporta solo los perfiles L1 del ámbito actual para respaldo o migración

## Relación con AgenticRAG

Cuando AgenticRAG está habilitado junto con LongTermMemory:

- LongTermMemory elimina su propia KB de memoria del preprocesamiento RAG ingenuo
- la recuperación automática L2 sigue siendo manejada por el propio LongTermMemory
- la misma KB de memoria se puede consultar explícitamente a través de la herramienta `query_knowledge` de AgenticRAG

Esto evita la recuperación duplicada mientras se conservan ambas rutas:

- recuperación automática de memoria
- recuperación más profunda iniciada por el agente cuando sea necesario

## Por qué no hay un filtro de metadatos del lado del agente

El tiempo de ejecución subyacente puede admitir el filtrado de metadatos, pero este plugin no expone filtros de metadatos sin procesar arbitrarios al flujo del agente hoy en día.

Razones:

- Los diferentes motores de conocimiento y motores vectoriales no comparten un esquema de metadatos unificado
- Los nombres de los campos de filtro, los formatos de valor y los operadores admitidos pueden diferir
- El agente actualmente no tiene una fuente de esquema estable para construir filtros confiables

Si LangBot proporciona más adelante una forma unificada de describir los campos de metadatos filtrables por base de conocimiento, se puede agregar el filtrado de metadatos del lado del agente.

Este plugin proporciona una interfaz de herramienta de recuperación controlada para su propio esquema de memoria estable. Esa herramienta admite filtros seleccionados como el hablante y el rango de tiempo, sin exponer una sintaxis de filtro específica del motor al modelo.

## Modelo de aislamiento

Se admiten dos modos de aislamiento:

- `session`: cada chat grupal o chat privado tiene memoria independiente
- `bot`: todas las sesiones bajo el mismo bot comparten la memoria

En el modelo de despliegue actual, esto es generalmente suficiente porque las instancias del plugin suelen estar vinculadas a un entorno de bot/tiempo de ejecución de LangBot específico.

## Reglas de aislamiento en detalle

Hay dos conceptos de ámbito relacionados pero ligeramente diferentes en este plugin:

- **session_name**: la identidad de la conversación pasada a través de la ruta de consulta / recuperación actual, formateada como `{launcher_type}_{launcher_id}`
- **session_key**: la clave de almacenamiento L1 interna del plugin. Cuando `bot_uuid` está disponible, se convierte en `{bot_uuid}:{launcher_type}_{launcher_id}`; de lo contrario, vuelve a `{launcher_type}_{launcher_id}`
- **scope_key / user_key**: la clave real utilizada para el almacenamiento de perfiles o el aislamiento de recuperación L2

### Cómo se aíslan los perfiles L1

Los perfiles L1 siempre se almacenan dentro del ámbito de la conversación actual:

- `session profile`
  - perfil compartido para la conversación actual
  - útil para contexto estable a nivel de grupo o conversación
- `speaker profile`
  - hechos estables sobre el hablante actual
  - útil para preferencias específicas de la persona, identidad y notas

Debido a eso, `!memory export` exporta solo los perfiles que pertenecen a la `session_key` actual, no todos los perfiles en toda la instancia del plugin.

### Cómo se aísla la memoria episódica L2

Las memorias L2 se escriben en el almacén de vectores con metadatos de aislamiento, luego se filtran en el momento de la recuperación:

- `session`
  - las memorias del grupo A no se recuperan en el grupo B
  - las memorias de un chat privado no se recuperan en otro
- `bot`
  - todas las sesiones bajo el mismo bot comparten un espacio de memoria episódica
  - útil cuando se desea compartir experiencias a largo plazo entre sesiones

Cuando `sender_id` está disponible, el plugin también puede preferir memorias relacionadas con el hablante antes de ampliar al ámbito más general.

### Por qué el aislamiento L1 y L2 no son exactamente iguales

Eso es intencional:

- L1 se comporta como un estado de perfil estable, por lo que el almacenamiento preciso de sesión / hablante tiene sentido
- L2 se comporta como una base de experiencias recuperable, por lo que el filtrado basado en metadatos es el modelo más escalable
- esto mantiene L1 preciso y L2 flexible

## Cómo usar

1. Instale y habilite el plugin.
2. Cree una base de conocimiento de memoria con el KnowledgeEngine de este plugin.
3. Configure:
   - `embedding_model_uuid`
   - `isolation`
   - opcional `recency_half_life_days`
   - opcional `auto_recall_top_k`
4. Deje que el agente use:
   - `remember` para eventos, planes y hechos episódicos
   - `recall_memory` para la búsqueda activa de memoria cuando la recuperación automática es insuficiente
   - `update_profile` para preferencias estables y datos de perfil
   - `forget` para eliminar una memoria episódica específica por ID
5. Use `!memory`, `!memory profile`, `!memory search <query>`, `!memory list [page]`, `!memory forget <id>` y `!memory export` para inspeccionar el comportamiento.

## Compartir contexto para otros plugins

LongTermMemory escribe un resumen de contexto estructurado en la variable de consulta `_ltm_context` durante cada evento `PromptPreProcessing`. Otros plugins pueden leer esta variable para tomar decisiones programáticas basadas en la memoria del usuario, sin importar ni referenciar LongTermMemory de ninguna manera.

### Clave de variable

`_ltm_context`

### Esquema

```python
{
    "speaker": {
        "id": "user_123",           # sender_id, puede ser una cadena vacía
        "name": "Alice",            # sender_name, puede ser una cadena vacía
    },
    "session_profile": {            # siempre presente, los campos pueden estar vacíos
        "name": "",
        "traits": ["creative", "analytical"],
        "preferences": ["prefers detailed explanations"],
        "notes": "",
        "updated_at": "2025-03-16T12:00:00Z",
    },
    "speaker_profile": {            # null cuando sender_id no está disponible
        "name": "Alice",
        "traits": ["extroverted"],
        "preferences": ["likes humor"],
        "notes": "",
        "updated_at": "2025-03-16T12:00:00Z",
    },
    "episodes": [                   # memorias episódicas L2 recuperadas automáticamente, pueden estar vacías
        {"content": "User mentioned a trip to Beijing last week"},
    ],
}
```

### Ejemplo de uso

```python
from langbot_plugin.api.definition.components.common.event_listener import EventListener
from langbot_plugin.api.entities import events, context
from langbot_plugin.api.entities.builtin.provider.message import Message


class PersonalityCustomizer(EventListener):
    def __init__(self):
        super().__init__()

        @self.handler(events.PromptPreProcessing)
        async def on_prompt(event_ctx: context.EventContext):
            ltm = await event_ctx.get_query_var("_ltm_context")
            if not ltm:
                # LongTermMemory no instalado o inactivo — usar valores predeterminados
                return

            profile = ltm.get("speaker_profile") or ltm.get("session_profile") or {}
            traits = profile.get("traits", [])

            if "likes humor" in traits:
                style = "Use a humorous and playful tone."
            elif "prefers concise" in traits:
                style = "Be concise and direct."
            else:
                return

            event_ctx.event.default_prompt.append(
                Message(role="system", content=style)
            )
```

### Notas de diseño

- Si LongTermMemory no está instalado, `_ltm_context` no existe. Los plugins consumidores deben tratar `None` como normal y volver al comportamiento predeterminado.
- Si LongTermMemory está activo pero aún no se han almacenado datos de perfil, la variable existe con campos vacíos. Esto permite a los plugins consumidores distinguir entre "sin plugin de memoria" y "plugin de memoria activo, sin datos aún".
- Ambas partes dependen solo de la clave de variable y la convención de esquema, no del código del otro. Si LongTermMemory es reemplazado por otro plugin de memoria que escribe la misma clave con el mismo esquema, los plugins consumidores continúan funcionando.
- LongTermMemory debe ejecutarse antes que los plugins consumidores en el orden de despacho de eventos. En la práctica, esto depende del orden de instalación del plugin.

## Importación / Exportación

- **Exportación (perfiles L1):** Use `!memory export` para exportar los perfiles de sesión y hablante del ámbito actual como JSON. No exporta datos de otras sesiones o ámbitos.
- **Importación (memoria episódica L2):** Cargue un archivo JSON a través de la interfaz de usuario de la base de conocimiento de LangBot para importar memorias episódicas de forma masiva.
- **La memoria episódica L2 se puede examinar** a través de `!memory list [page]` y los episodios individuales se pueden eliminar a través de `!memory forget <id>`. La exportación masiva completa aún no está implementada.

## Preguntas técnicas clave

### Q1. ¿Por qué dividir la memoria en L1 y L2 en lugar de almacenar todo en la base de datos de vectores?

Porque los patrones de acceso son diferentes:

- L1 contiene hechos estables y debe inyectarse de forma consistente
- L2 contiene memoria tipo evento y debe recuperarse bajo demanda

Poner ambos en el almacén de vectores haría que la recuperación del perfil estable fuera menos confiable y haría que las actualizaciones de memoria fueran semánticamente desordenadas.

### Q2. ¿Por qué se recupera L2 en lugar de inyectarse completamente en cada turno?

Porque L2 crece con el tiempo. La inyección completa causaría rápidamente:

- hinchazón del prompt
- demasiado ruido irrelevante
- la memoria antigua desplazando al contexto realmente relevante

La estrategia actual es recuperar automáticamente un pequeño subconjunto relevante, luego dejar que el agente use `recall_memory` si necesita más.

### Q3. ¿La memoria L2 decae con el tiempo?

Sí.

La clasificación L2 no depende solo de la similitud vectorial. También aplica un decaimiento temporal para que las memorias más nuevas tiendan a clasificarse más alto que las más antiguas.

La implementación actual utiliza un enfoque de estilo vida media:

- cuando una memoria alcanza `half_life_days`, su peso temporal decae a aproximadamente el 50%
- se favorece la memoria más nueva en la clasificación
- la memoria más antigua no se elimina automáticamente; simplemente pierde ventaja en la clasificación

Esto tiene como objetivo priorizar el contexto reciente, no eliminar de forma drástica el pasado.

### Q4. ¿Las memorias antiguas acaban desapareciendo por completo?

No automáticamente.

El decaimiento temporal afecta a la clasificación, no a la eliminación drástica. Las memorias antiguas aún pueden recuperarse si siguen siendo lo suficientemente relevantes.

### Q5. ¿Cómo debo elegir entre el aislamiento de `session` y `bot`?

En la práctica:

- elija `session`
  - cuando cada chat grupal / chat privado deba mantener una memoria independiente
  - cuando desee un menor riesgo de fuga entre sesiones
- elija `bot`
  - cuando el bot deba compartir la experiencia a largo plazo entre sesiones
  - cuando la recuperación más amplia sea más importante que una separación más estricta

Si no está seguro, comience con `session`.

### Q6. ¿Por qué `!memory export` solo exporta el ámbito actual?

Ese es un límite de seguridad deliberado.

Permitir la exportación de cada perfil L1 en la instancia del plugin facilitaría mucho la fuga de datos entre sesiones. Restringir la exportación al ámbito actual sigue un principio de exposición mínima.

### Q7. ¿Qué sucede si el tiempo de ejecución no expone `_knowledge_base_uuids` en las variables de consulta?

La inyección automática de memoria sigue funcionando, pero el plugin no puede eliminar su propia KB de memoria del preprocesamiento RAG ingenuo.

Eso puede llevar a una recuperación de memoria duplicada:

- una copia inyectada por el propio LongTermMemory
- otra copia recuperada de nuevo por el flujo genérico de KB del ejecutor

Así que esto no es un fallo total, pero puede desperdiciar contexto y hacer que el prompt sea más ruidoso.

### Q8. ¿Por qué no se admite aún la exportación L2?

El SDK ahora proporciona una API `vector_list` para la enumeración paginada del contenido del almacén de vectores. Las memorias episódicas L2 se pueden examinar a través de `!memory list [page]` y eliminarse individualmente a través de `!memory forget <episode_id>` o la herramienta `forget`.

La exportación masiva completa aún no está implementada, pero las piezas fundamentales están en su lugar.

### Q9. ¿LongTermMemory y AgenticRAG duplicarán la recuperación cuando ambos estén habilitados?

No, esa duplicación es exactamente lo que evita el diseño actual:

- LongTermMemory elimina su propio preprocesamiento RAG ingenuo
- la recuperación automática L2 es manejada por LongTermMemory
- la recuperación ad hoc más profunda aún puede realizarse a través de AgenticRAG

## Consola de Memoria

Además del comando `!memory`, el plugin incluye una página web **Consola de Memoria** (registrada como el componente Page del plugin) para inspección visual y mantenimiento. Se comunica con el plugin a través de endpoints de página acotados al alcance y nunca sale del espacio de memoria seleccionado.

La consola se organiza en una barra lateral de espacio más paneles con pestañas:

- **Barra lateral de espacio de memoria** —— elige un alcance conocido, o completa `bot_uuid` / `session_name` / `isolation` y haz clic en **Derive** para calcular el `scope_key` y el `user_key` correspondientes. Un área **Advanced / Raw** expone las claves internas.
- **Perfiles** —— muestra el perfil de sesión y el perfil del hablante actual del alcance seleccionado.
- **Episodios** —— lista (paginada) o busca semánticamente los episodios L2 del `user_key` actual, filtrados por estado del ciclo de vida; archiva, restaura o elimina episodios en línea. Cada acción de modificación escribe una entrada de auditoría acotada, igual que el comando `!memory` equivalente.
- **Inyección** —— carga la **última instantánea de inyección de memoria** del alcance: si se inyectó algo en el último turno, cuántos bloques y caracteres, qué hablante, los perfiles usados y los episodios L2 recuperados automáticamente. Responde "¿qué recordó el bot en el último turno?" sin revisar los registros.
- **Auditoría** —— navega (paginado) y exporta el registro de auditoría acotado.
- **Exportar** —— exporta los perfiles L1 y los episodios L2 del alcance actual como JSON.
- **Diagnóstico** —— **Run Health Check** ejecuta la misma sonda de aislamiento de metadatos que `!memory health` directamente desde la interfaz (configuración del KB, modelo de embedding y aislamiento del filtro `user_key` en search / list / delete), representada como tarjetas de estado rojas/ámbar/verdes. Nota: la consola no puede verificar que el KB esté adjunto a un pipeline específico; ejecuta `!memory health` dentro de un pipeline para confirmar esa parte.

La consola admite i18n (`en_US`, `zh_Hans`) y sigue el tema claro/oscuro de LangBot anfitrión.

## Componentes

- KnowledgeEngine: [memory_engine.py](components/knowledge_engine/memory_engine.py)
- EventListener: [memory_injector.py](components/event_listener/memory_injector.py)
- Herramientas: [remember.py](components/tools/remember.py), [recall_memory.py](components/tools/recall_memory.py), [update_profile.py](components/tools/update_profile.py), [forget.py](components/tools/forget.py)
- Comando: [memory.py](components/commands/memory.py)
- Page: [memory_console.py](components/pages/memory_console/memory_console.py), [index.html](components/pages/memory_console/index.html)

## Brechas actuales

El README ahora cubre el diseño principal, las reglas de aislamiento, los límites de exportación y los componentes principales.

Aún vale la pena agregar más adelante:

- actualizaciones sincronizadas para documentos localizados
- ejemplos concretos de importación JSON
- ejemplos de mejores prácticas para `remember`, `recall_memory` y `update_profile`

## Registro (Logging)

El plugin ahora emite registros en puntos clave del ciclo de vida de la memoria para que pueda observar cómo se utiliza la memoria a largo plazo durante el tiempo de ejecución.

Verá registros de:

- inicialización del plugin y contexto de memoria resuelto
- llamadas a las herramientas `remember`, `recall_memory` y `update_profile`
- inyección de perfil antes de la invocación del modelo
- recuperación automática de memoria L2 en el KnowledgeEngine
- escrituras de vectores de memoria episódica, búsquedas, lotes de importación y eliminaciones

Los mensajes de registro típicos se ven así:

```text
[LongTermMemory] remember called: query_id=123 params_keys=['content', 'importance', 'tags']
[LongTermMemory] memory injection ready: query_id=123 kb_id=kb-1 scope_key=bot:xxx:group_123 sender_id=u1 block_count=2 prompt_chars=280
[LongTermMemory] engine retrieve called: collection_id=kb-1 top_k=5 session_name=group_123 sender_id=u1 bot_uuid=bot-1 query='user asked about travel plan'
[LongTermMemory] search_episodes completed: collection_id=kb-1 result_count=3 filters={'user_key': 'bot:bot-1:group_123'}
```
