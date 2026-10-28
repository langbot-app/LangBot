# Plugin TavilySearch

Un plugin de [LangBot](https://github.com/langbot-app/langbot) que proporciona capacidades de búsqueda utilizando la API de Tavily, un motor de búsqueda creado específicamente para agentes de IA (LLMs).

## Características

- Búsqueda web en tiempo real impulsada por Tavily
- Soporte para diferentes profundidades de búsqueda (basic/advanced)
- Búsqueda específica por tema (general/news/finance)
- Incluye respuestas generadas por IA
- Incluye imágenes relevantes
- Incluye contenido HTML sin procesar
- Número personalizable de resultados

## Instalación

1. Instala el plugin.

2. Configura tu clave de API de Tavily:
   - Obtén tu clave de API de [Tavily](https://tavily.com/)
   - Agrega la clave de API a la configuración del plugin en LangBot

## Uso

Este plugin añade una herramienta `tavily_search` que puede ser utilizada por los LLMs en las conversaciones.

### Parámetros

- **query** (obligatorio): La cadena de consulta de búsqueda
- **search_depth** (opcional): "basic" (por defecto) o "advanced"
- **topic** (opcional): "general" (por defecto), "news" o "finance"
- **max_results** (opcional): Número de resultados (1-20, por defecto: 5)
- **include_answer** (opcional): Incluir respuesta generada por IA (por defecto: false)
- **include_images** (opcional): Incluir imágenes relacionadas (por defecto: false)
- **include_raw_content** (opcional): Incluir contenido HTML sin procesar (por defecto: false)

### Ejemplo

Al chatear con tu LangBot, el LLM puede usar automáticamente esta herramienta:

```
Usuario: ¿Cuáles son las últimas noticias sobre inteligencia artificial?

Bot: [Usa la herramienta tavily_search con topic="news"]
```

## Desarrollo

Para desarrollar o modificar este plugin:

1. Edita la lógica de la herramienta en `components/tools/tavily_search.py`
2. Modifica la configuración en `manifest.yaml`
3. Actualiza los parámetros de la herramienta en `components/tools/tavily_search.yaml`

## Configuración

El plugin requiere la siguiente configuración:

- **tavily_api_key**: Tu clave de API de Tavily (obligatorio)

## Licencia

Este plugin es parte del ecosistema de plugins de LangBot.

## Enlaces

- [Documentación de la API de Tavily](https://docs.tavily.com/)
- [Documentación de LangBot](https://langbot.app/docs/)
