# Gestor de FAQ

Gestiona entradas de preguntas frecuentes a través de una página visual en la WebUI de LangBot y permite que el LLM las busque durante las conversaciones.

## Funcionalidades

- **Componente Page**: Interfaz CRUD completa para gestionar pares de preguntas y respuestas, accesible desde la sección "Páginas de plugins" en la barra lateral.
- **Componente Tool**: `search_faq` — permite al LLM buscar en la base de datos de FAQ por palabras clave y devolver las entradas coincidentes al usuario.
- **Almacenamiento persistente**: Las entradas de FAQ se almacenan mediante el almacenamiento del plugin y se mantienen tras los reinicios.
- **Internacionalización**: La página de gestión soporta inglés, chino simplificado y japonés.
- **Modo oscuro**: La página se adapta automáticamente al tema de LangBot.

## Componentes

| Componente | Tipo | Descripción |
|-----------|------|-------------|
| `components/pages/manager/` | Page | Interfaz de gestión de FAQ (crear, editar, eliminar, buscar) |
| `components/tools/search_faq.py` | Tool | Búsqueda por palabras clave en las entradas de FAQ, invocable por el LLM |
| `components/event_listener/default.py` | EventListener | Escuchador de eventos por defecto (marcador de posición) |

## Uso

1. Instala el plugin en LangBot.
2. Abre la sección **Páginas de plugins** en la barra lateral y selecciona **Gestor de FAQ**.
3. Añade pares de preguntas y respuestas a través de la página.
4. Cuando los usuarios hagan preguntas en una conversación, el LLM podrá usar la herramienta `search_faq` para buscar entradas de FAQ coincidentes y responder en consecuencia.
