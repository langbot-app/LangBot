# QWeather

A [LangBot](https://github.com/langbot-app/langbot) plugin for displaying weather information using QWeather API.

Code adapted from [nonebot-plugin-heweather](https://github.com/kexue-z/nonebot-plugin-heweather)

## Features

- Display weather information in text format
- Support for QWeather API (free, standard, and commercial subscriptions)
- Show current weather, air quality, forecast, warnings, and sunrise/sunset times
- Multi-day forecast support

## Configuration

Before using this plugin, you need to:

1. Register and get an API key from [QWeather](https://dev.qweather.com/)
2. Configure the plugin in LangBot WebUI:
   - **QWeather API Key**: Your API key from QWeather
   - **API Type**: Select your subscription type (Free/Standard/Commercial)

## Usage

Send the following command to get weather information:

```
!weather <city_name>
```

## Example Output

```
📍 北京 天气信息

🌡️ 当前天气
  温度: 15°C
  天气: 晴
  风向: 北风 3级
  湿度: 45%
  能见度: 10km

💨 空气质量
  AQI: 50 (优)
  PM2.5: 12

📅 未来3天预报
  2025-01-15: 晴 5~18°C
  2025-01-16: 多云 3~16°C
  2025-01-17: 阴 2~14°C

🌅 日出日落
  日出: 07:30
  日落: 17:45
```
