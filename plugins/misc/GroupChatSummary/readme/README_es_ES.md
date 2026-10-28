# Resumen de chat grupal

Resuma los mensajes de chat grupal usando LLM. No vuelvas a perderte discusiones importantes.

## Características

-**Recopilación de mensajes**: registra automáticamente todos los mensajes del grupo
-**Resumen manual**: use el comando`!summary`para obtener resúmenes instantáneos
-**Resumen basado en tiempo**: resume los mensajes de las últimas N horas
-**Herramienta LLM**: la IA puede llamar a la herramienta de resumen cuando los usuarios preguntan "¿qué me perdí?"
-**Resumen automático**: opcionalmente activa resúmenes después de que se acumulen N mensajes
-**Almacenamiento persistente**: el historial de mensajes sobrevive a los reinicios del complemento

## Comandos

| Comando | Descripción |
|---------|-------------|
|`!resumen [recuento]`| Resumir N mensajes recientes (predeterminado: 100) |
|`!resumen de horas <N>`| Resumir mensajes de las últimas N horas |
|`!estado de resumen`| Mostrar estado del buffer de mensajes |
|`!resumen claro`| Borrar mensajes almacenados |

## Configuración

| Opción | Predeterminado | Descripción |
|--------|---------|-------------|
| Mensajes máximos | 500 | Máximo de mensajes almacenados por grupo |
| Recuento de resumen predeterminado | 100 | Mensajes para resumir por defecto |
| Resumen automático | Apagado | Resumir automáticamente cada N mensajes |
| Umbral de resumen automático | 200 | Mensajes antes del disparo automático |
| Idioma | Chino | Idioma de salida del resumen |

## Cómo funciona

1. El complemento escucha todos los mensajes del grupo y los almacena en la memoria (permanece en el almacenamiento)
2. Cuando se activa (comando, llamada de herramienta o automático), formatea los mensajes y los envía a su LLM configurado.
3. El LLM genera un resumen estructurado con temas, decisiones y elementos de acción clave.

## Ejemplo

```
User: !summary 50
Bot: ⏳ Summarizing 50 messages...
Bot: 📋 Group Chat Summary

**Project Discussion**
- Team decided to use React for the frontend
- Backend API deadline moved to next Friday

**Action Items**
- @Alice: Prepare design mockups by Wednesday
- @Bob: Set up CI/CD pipeline
```
