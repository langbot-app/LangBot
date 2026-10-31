# QWeather

Một plugin [LangBot](https://github.com/langbot-app/langbot) để hiển thị thông tin thời tiết bằng API QWeather.

Mã nguồn được chuyển thể từ [nonebot-plugin-heweather](https://github.com/kexue-z/nonebot-plugin-heweather)

## Tính năng

- Hiển thị thông tin thời tiết ở định dạng văn bản
- Hỗ trợ API QWeather (các gói đăng ký miễn phí, tiêu chuẩn và thương mại)
- Hiển thị thời tiết hiện tại, chất lượng không khí, dự báo, cảnh báo và thời gian bình minh/hoàng hôn
- Hỗ trợ dự báo nhiều ngày

## Cấu hình

Trước khi sử dụng plugin này, bạn cần:

1. Đăng ký và nhận khóa API từ [QWeather](https://dev.qweather.com/)
2. Cấu hình plugin trong LangBot WebUI:
   - **QWeather API Key**: Khóa API của bạn từ QWeather
   - **API Type**: Chọn loại đăng ký của bạn (Free/Standard/Commercial)

## Cách sử dụng

Gửi lệnh sau để lấy thông tin thời tiết:

```
!weather <tên_thành_phố>
```

## Ví dụ đầu ra

```
📍 Hà Nội Thông tin thời tiết

🌡️ Thời tiết hiện tại
  Nhiệt độ: 15°C
  Thời tiết: Trời quang
  Hướng gió: Gió Bắc Cấp 3
  Độ ẩm: 45%
  Tầm nhìn: 10km

💨 Chất lượng không khí
  AQI: 50 (Tốt)
  PM2.5: 12

📅 Dự báo trong 3 ngày tới
  2025-01-15: Trời quang 5~18°C
  2025-01-16: Có mây 3~16°C
  2025-01-17: Trời u ám 2~14°C

🌅 Bình minh và Hoàng hôn
  Bình minh: 07:30
  Hoàng hôn: 17:45
```
