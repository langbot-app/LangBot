# Lên lịchThông báo

Lên lịch thông báo bằng ngôn ngữ tự nhiên

## Đặc trưng

ScheNotify là một plugin LangBot cho phép người dùng đặt lời nhắc theo thời gian thông qua tương tác ngôn ngữ tự nhiên với LLM.

### Tính năng chính

-**Tương tác ngôn ngữ tự nhiên**: Hiểu ý định lên lịch của người dùng thông qua LLM
-**Phân tích thời gian thông minh**: Tự động lấy thời gian hiện tại và tính toán thời gian nhắc nhở
-**Hỗ trợ đa ngôn ngữ**: Hỗ trợ tin nhắn nhắc nhở bằng tiếng Trung và tiếng Anh
-**Lệnh quản lý lịch trình**: Xem và xóa lời nhắc đã lên lịch
-**Thông báo tự động**: Tự động gửi tin nhắn nhắc nhở vào thời gian đã lên lịch

## Cấu hình

### Cài đặt ngôn ngữ

Bạn có thể chọn ngôn ngữ cho thông báo nhắc nhở trong cấu hình plugin:

-`zh_Hans`(Tiếng Trung giản thể) - Mặc định
-`en_US`(tiếng Anh)

## Cách sử dụng

### 1. Lên lịch qua LLM

Chỉ cần cho LLM biết lịch trình của bạn bằng ngôn ngữ tự nhiên:

**Ví dụ:**
```
Remind me to have a meeting at 3 PM tomorrow
Remind me to submit the report at 9 AM the day after tomorrow
Remind me to have lunch at 12 PM next Monday
Remind me about Christmas dinner at 2024-12-25 18:00
```

LLM sẽ tự động:
1. Gọi`get_current_time_str`để biết thời gian hiện tại
2. Phân tích biểu thức thời gian của bạn và chuyển đổi sang định dạng chuẩn
3. Gọi`schedule_notify`để tạo lời nhắc

### 2. Xem lời nhắc đã lên lịch

Sử dụng lệnh để xem tất cả các lời nhắc đã lên lịch:

```
!sche
```

Đầu ra ví dụ:
```
[Notify] Scheduled reminders:
#1 2024-12-25 18:00:00: Christmas dinner
#2 2024-12-26 09:00:00: Submit report
```

### 3. Xóa lời nhắc

Sử dụng lệnh để xóa một lời nhắc cụ thể (sử dụng số từ`!sche`):

```
!dsche i <number>
```

Ví dụ:
```
!dsche i 1   # Delete the 1st reminder
```

## Thành phần

### Công cụ

1.**get_current_time_str**- Lấy thời gian hiện tại
   - Định dạng trả về:`YYYY-MM-DD HH:MM:SS`
   - LLM phải gọi công cụ này trước khi đặt lời nhắc

2.**schedule_notify**- Thông báo lịch trình
   - Thông số: chuỗi thời gian, tin nhắn nhắc nhở
   - Tự động lấy thông tin phiên từ tham số phiên của Công cụ

### Lệnh

1.**sche**(bí danh: s) - Liệt kê tất cả các lời nhắc đã lên lịch
2.**dsche**(bí danh: d) - Xóa lời nhắc được chỉ định

## Chi tiết kỹ thuật

- Khoảng thời gian kiểm tra: Cứ sau 60 giây
- Độ chính xác về thời gian: Mức phút (kiểm tra mỗi phút)
- Thông tin phiên: Tự động lấy được thông qua tham số phiên của Công cụ
- Persistence: Hiện đang sử dụng bộ nhớ trong (mất khi khởi động lại)

## Cuộc trò chuyện mẫu

**Người dùng:**Nhắc tôi tham dự cuộc họp lúc 2 giờ chiều ngày mai

**LLM:**Chắc chắn rồi, tôi sẽ đặt lời nhắc cho bạn.

*[LLM gọi get_current_time_str]*
*[Cuộc gọi LLM lịch_notify(time_str="2024-12-26 14:00:00", message="Tham dự cuộc họp")]*

**LLM:**Xong rồi! Tôi sẽ nhắc bạn vào lúc 26-12-2024 14:00:00: Tham dự cuộc họp

*[Ngày hôm sau lúc 2 giờ chiều]*

**Bot:**[Thông báo] Tham dự cuộc họp

## Ghi chú

- Thời gian nhắc phải ở tương lai, thời gian đã qua sẽ bị từ chối
- Tin nhắn nhắc nhở sẽ được gửi đến cùng phiên đã đặt lời nhắc
- Lời nhắc chưa gửi sẽ bị mất sau khi khởi động lại plugin (tính bền vững sẽ được hỗ trợ trong các phiên bản sau)

## Thông tin nhà phát triển

- Tác giả: RockChinQ
- Phiên bản: 0.2.0
- Loại plugin: Plugin LangBot v1

## Giấy phép

Một phần của hệ sinh thái plugin LangBot.
