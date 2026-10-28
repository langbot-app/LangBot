# QWeather

[LangBot](https://github.com/langbot-app/LangBot) 的天气插件，使用和风天气 API 显示天气信息。

> 插件代码改编自 [nonebot-plugin-heweather](https://github.com/kexue-z/nonebot-plugin-heweather)

## 功能特性

- 以文本格式展示天气信息。
- 支持和风天气 API（免费、标准和商业订阅）。
- 显示当前天气、空气质量、天气预报、预警和日出日落时间。
- 支持多日天气预报。

## 配置说明

使用本插件前，您需要：

1. 在[和风天气](https://dev.qweather.com/)注册并获取 API Key
2. 在 LangBot WebUI 中配置插件：
   - **和风天气 API Key**: 从和风天气获取的 API Key
   - **API 类型**: 选择您的订阅类型（免费/标准/商业）

## 使用方法

发送以下命令获取天气信息：

```
!weather <城市名称>
```

或使用中文命令：

```
!天气 <城市名称>
```

示例：
```
!weather 北京
!天气 上海
```

## 输出示例

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
