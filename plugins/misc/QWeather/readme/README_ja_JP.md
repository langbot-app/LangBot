#Q天気

QWeather API を使用して天気情報を表示するための [LangBot](https://github.com/langbot-app/langbot) プラグイン。

[nonebot-plugin-heweather](https://github.com/kexue-z/nonebot-plugin-heweather) から適応されたコード

＃＃ 特徴

- 天気情報をテキスト形式で表示します
- QWeather API のサポート (無料、標準、および商用サブスクリプション)
- 現在の天気、大気質、予報、警報、日の出/日の入り時刻を表示します
- 複数日の予報のサポート

＃＃ 構成

このプラグインを使用する前に、次のことを行う必要があります。

1. [QWeather](https://dev.qweather.com/) から登録して API キーを取得します
2. LangBot WebUI でプラグインを構成します。
   -**QWeather API キー**: QWeather からの API キー
   -**API タイプ**: サブスクリプション タイプを選択します (無料/標準/商用)

＃＃ 使用法

次のコマンドを送信して天気情報を取得します。

```
!weather <city_name>
```

## 出力例

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
