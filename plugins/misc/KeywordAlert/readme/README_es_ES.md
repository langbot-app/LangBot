# Alerta de palabra clave

Supervise los mensajes de chat grupal en busca de palabras clave específicas y reciba alertas instantáneas de mensajes privados.

## Características

- 🔔 Monitoreo de palabras clave en tiempo real en chats grupales
- 📋 Listas de palabras clave configurables (separadas por comas)
- 🎯 Monitorear grupos específicos o todos los grupos
- 🤖 Elige qué bot envía alertas
- ⏱️ Tiempo de reutilización para evitar alertas no deseadas
- 🔤 Coincidencia opcional que distingue entre mayúsculas y minúsculas

## Cómo funciona

1. Configure las palabras clave que desea monitorear (por ejemplo, "error, urgente, ayuda")
2. Configure su ID de usuario/sesión como administrador para recibir alertas.
3. Cuando alguien envía un mensaje que contiene una palabra clave en un grupo monitoreado, recibe una alerta de mensaje privado con el contexto completo.

## Configuración

| Opción | Descripción | Predeterminado |
|---|---|---|
| Palabras clave | Palabras clave separadas por comas para monitorear | (obligatorio) |
| ID de grupo | ID de grupo separados por comas (vacíos = todos) | Todos los grupos |
| ID de sesión de administrador | Quién recibe las alertas | (obligatorio) |
| Bot de alerta | ¿Qué bot envía la alerta? Primero disponible |
| Distingue entre mayúsculas y minúsculas | Coincidencia que distingue entre mayúsculas y minúsculas | Apagado |
| Enfriamiento | Segundos entre alertas de la misma palabra clave por grupo | 60 |

## Formato de alerta

```
🔔 关键词告警
━━━━━━━━━━━━━━
关键词: urgent
群组: 123456789
发送者: 987654321
━━━━━━━━━━━━━━
Hey, this is urgent, the server is down!
```
