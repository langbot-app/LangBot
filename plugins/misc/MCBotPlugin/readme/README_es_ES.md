# MCBotPlugin

Complemento de LangBot para grupos de chat de servidores de Minecraft: vincula un servidor de Minecraft a tu grupo, consulta el estado del servidor en tiempo real y los jugadores conectados, y registra el tiempo de juego de cada jugador.

> Esta es la migración del antiguo [MCBotPlugin](https://github.com/langbot-app/MCBotPlugin) (creado para QChatGPT) al nuevo SDK de complementos de LangBot. El almacenamiento en MongoDB se reemplaza por el almacenamiento KV integrado del complemento (sin necesidad de una base de datos externa), la consulta de estado de Minecraft pasa del `mctools` síncrono al `mcstatus` asíncrono, y el muestreo de tiempo de juego en segundo plano pasa de hilos a una tarea asyncio.

## Funciones

- **Vincular un servidor**: cada grupo puede vincular un servidor de Minecraft (Java Edition)
- **Consulta de estado**: MOTD, versión, número de jugadores conectados y lista de jugadores en tiempo real
- **Estadísticas de tiempo de juego**: una tarea en segundo plano muestrea a los jugadores conectados y agrega el tiempo en línea de cada jugador durante cualquier período

## Comandos

| Comando | Descripción | Permiso |
| --- | --- | --- |
| `!mcbot` | Mostrar ayuda | Todos |
| `!mcbot bind <dirección[:puerto]>` | Vincular un servidor a este grupo | Administrador |
| `!mcbot unbind` | Desvincular el servidor | Administrador |
| `!mcbot status` | Mostrar el estado del servidor y los jugadores conectados | Todos |
| `!mcbot time [minutos]` | Mostrar estadísticas de tiempo de juego (predeterminado 1440 min = 24 h) | Todos |

> Los administradores se determinan mediante la configuración `admins` de LangBot (`{launcher_type}_{launcher_id}`).

## Configuración

| Clave | Descripción | Predeterminado |
| --- | --- | --- |
| `track_interval` | Intervalo de muestreo de jugadores conectados en segundos (mín. 15) | 60 |
| `ping_timeout` | Tiempo de espera del ping al servidor en segundos | 10 |

## Dependencias

- [`mcstatus`](https://github.com/py-mine/mcstatus) — Consultas de estado de servidores de Minecraft

## Almacenamiento

Las vinculaciones y los registros de conexión se guardan en el almacenamiento KV integrado del complemento de LangBot; no se necesita MongoDB. Los registros de conexión se conservan durante 14 días de forma predeterminada.
