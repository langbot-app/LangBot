# QWeather

一個使用和風天氣 (QWeather) API 顯示天氣資訊的 [LangBot](https://github.com/langbot-app/langbot) 插件。

程式碼改編自 [nonebot-plugin-heweather](https://github.com/kexue-z/nonebot-plugin-heweather)

## 功能特性

- 以文本格式顯示天氣資訊
- 支持和風天氣 API（免費、標準和商業訂閱）
- 顯示當前天氣、空氣質量、預報、預警以及日出/日落時間
- 支持多日天氣預報

## 配置

在使用此插件之前，您需要：

1. 從 [和風天氣開發者控制台](https://dev.qweather.com/) 註冊並獲取 API Key
2. 在 LangBot WebUI 中配置插件：
   - **QWeather API Key**: 您的和風天氣 API Key
   - **API Type**: 選擇您的訂閱類型 (Free/Standard/Commercial)

## 使用方法

發送以下指令獲取天氣資訊：

```
!weather <城市名稱>
```

## 範例輸出

```
📍 北京 天氣資訊

🌡️ 當前天氣
  溫度: 15°C
  天氣: 晴
  風向: 北風 3級
  濕度: 45%
  能見度: 10km

💨 空氣質量
  AQI: 50 (優)
  PM2.5: 12

📅 未來3天預報
  2025-01-15: 晴 5~18°C
  2025-01-16: 多雲 3~16°C
  2025-01-17: 陰 2~14°C

🌅 日出日落
  日出: 07:30
  日落: 17:45
```
