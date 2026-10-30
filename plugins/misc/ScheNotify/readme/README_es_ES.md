# ProgramarNotificar

Programar notificaciones con lenguaje natural

## Características

ScheNotify es un complemento de LangBot que permite a los usuarios configurar recordatorios programados mediante la interacción en lenguaje natural con LLM.

### Características principales

-**Interacción en lenguaje natural**: comprenda las intenciones de programación del usuario a través de LLM
-**Análisis inteligente de la hora**: obtiene automáticamente la hora actual y calcula la hora del recordatorio
-**Soporte multilingüe**: Admite mensajes recordatorios en chino e inglés
-**Comandos de gestión de programación**: ver y eliminar recordatorios programados
-**Notificaciones automáticas**: envía mensajes recordatorios automáticamente a la hora programada

## Configuración

### Configuración de idioma

Puede seleccionar el idioma de los mensajes recordatorios en la configuración del complemento:

-`zh_Hans`(chino simplificado) - Predeterminado
-`en_US`(inglés)

## Uso

### 1. Programar a través de LLM

Simplemente dígale al LLM su horario en lenguaje natural:

**Ejemplos:**
```
Remind me to have a meeting at 3 PM tomorrow
Remind me to submit the report at 9 AM the day after tomorrow
Remind me to have lunch at 12 PM next Monday
Remind me about Christmas dinner at 2024-12-25 18:00
```

El LLM automáticamente:
1. Llame a`get_current_time_str`para obtener la hora actual
2. Analice su expresión de tiempo y conviértala al formato estándar.
3. Llame a`schedule_notify`para crear un recordatorio.

### 2. Ver recordatorios programados

Utilice el comando para ver todos los recordatorios programados:

```
!sche
```

Salida de ejemplo:
```
[Notify] Scheduled reminders:
#1 2024-12-25 18:00:00: Christmas dinner
#2 2024-12-26 09:00:00: Submit report
```

### 3. Eliminar recordatorio

Use el comando para eliminar un recordatorio específico (usando el número de`!sche`):

```
!dsche i <number>
```

Ejemplo:
```
!dsche i 1   # Delete the 1st reminder
```

## Componentes

### Herramientas

1.**get_current_time_str**- Obtener la hora actual
   - Formato de retorno:`AAAA-MM-DD HH:MM:SS`
   - LLM debe llamar a esta herramienta antes de configurar recordatorios

2.**schedule_notify**- Programar notificación
   - Parámetros: cadena de tiempo, mensaje recordatorio
   - Obtiene automáticamente información de la sesión del parámetro de sesión de la herramienta

### Comandos

1.**sche**(alias: s): enumera todos los recordatorios programados
2.**dsche**(alias: d): eliminar el recordatorio especificado

## Detalles técnicos

- Intervalo de control: Cada 60 segundos
- Precisión del tiempo: nivel de minutos (comprueba cada minuto)
- Información de sesión: obtenida automáticamente a través del parámetro de sesión de la herramienta
- Persistencia: actualmente utiliza almacenamiento en memoria (se pierde al reiniciar)

## Ejemplo de conversación

**Usuario:**Recuérdame asistir a una reunión mañana a las 2 p.m.

**LLM:**Claro, te estableceré un recordatorio.

*[LLM llama a get_current_time_str]*
*[LLAMADA DE LLM Schedule_notify(time_str="2024-12-26 14:00:00", message="Asistir a la reunión")]*

**LLM:**¡Listo! Te lo recordaré el 26-12-2024 14:00:00: Asistir a la reunión

*[Al día siguiente a las 2 p.m.]*

**Bot:**[Notificar] Asistir a la reunión

## Notas

- La hora del recordatorio debe ser en el futuro, las horas pasadas serán rechazadas.
- Los mensajes recordatorios se enviarán a la misma sesión donde se configuró el recordatorio.
- Los recordatorios no enviados se perderán después de reiniciar el complemento (la persistencia será compatible en versiones futuras)

## Información del desarrollador

- Autor: RockChinQ
- Versión: 0.2.0
- Tipo de complemento: complemento LangBot v1

## Licencia

Parte del ecosistema de complementos de LangBot.
