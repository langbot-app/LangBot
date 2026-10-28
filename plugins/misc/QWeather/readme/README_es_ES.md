# QWeather

Plugin de [LangBot](https://github.com/langbot-app/langbot) para mostrar información meteorológica utilizando la API de QWeather.

Código adaptado de [nonebot-plugin-heweather](https://github.com/kexue-z/nonebot-plugin-heweather)

## Características

- Muestra información meteorológica en formato de texto
- Soporte para la API de QWeather (suscripciones gratuita, estándar y comercial)
- Muestra el clima actual, calidad del aire, pronóstico, advertencias y horas de salida/puesta del sol
- Soporte para pronóstico de varios días

## Configuración

Antes de usar este plugin, debe:

1. Registrarse y obtener una clave de API de [QWeather](https://dev.qweather.com/)
2. Configurar el plugin en la WebUI de LangBot:
   - **QWeather API Key**: Su clave de API de QWeather
   - **API Type**: Seleccione su tipo de suscripción (Free/Standard/Commercial)

## Uso

Envíe el siguiente comando para obtener información meteorológica:

```
!weather <nombre_de_la_ciudad>
```

## Ejemplo de salida

```
📍 Madrid Información Meteorológica

🌡️ Clima actual
  Temperatura: 15°C
  Clima: Despejado
  Dirección del viento: Norte Nivel 3
  Humedad: 45%
  Visibilidad: 10km

💨 Calidad del aire
  AQI: 50 (Excelente)
  PM2.5: 12

📅 Pronóstico para los próximos 3 días
  2025-01-15: Despejado 5~18°C
  2025-01-16: Parcialmente nublado 3~16°C
  2025-01-17: Nublado 2~14°C

🌅 Salida/Puesta del sol
  Salida del sol: 07:30
  Puesta del sol: 17:45
```
