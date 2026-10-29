# Trình quản lý FAQ

Quản lý các mục câu hỏi thường gặp thông qua trang trực quan trong WebUI của LangBot và cho phép LLM tìm kiếm chúng trong các cuộc trò chuyện.

## Tính năng

- **Thành phần Page**: Giao diện CRUD đầy đủ để quản lý các cặp câu hỏi-trả lời, truy cập từ mục "Trang plugin" trên thanh bên.
- **Thành phần Tool**: `search_faq` — cho phép LLM tìm kiếm cơ sở dữ liệu FAQ theo từ khóa và trả về các mục phù hợp cho người dùng.
- **Lưu trữ bền vững**: Các mục FAQ được lưu qua bộ nhớ plugin và không bị mất khi khởi động lại.
- **Đa ngôn ngữ**: Trang quản lý hỗ trợ tiếng Anh, tiếng Trung giản thể và tiếng Nhật.
- **Chế độ tối**: Trang tự động thích ứng với giao diện LangBot.

## Thành phần

| Thành phần | Loại | Mô tả |
|-----------|------|-------|
| `components/pages/manager/` | Page | Giao diện quản lý FAQ (thêm, sửa, xóa, tìm kiếm) |
| `components/tools/search_faq.py` | Tool | Tìm kiếm từ khóa trong các mục FAQ, có thể gọi bởi LLM |
| `components/event_listener/default.py` | EventListener | Trình lắng nghe sự kiện mặc định (giữ chỗ) |

## Cách sử dụng

1. Cài đặt plugin trong LangBot.
2. Mở mục **Trang plugin** trên thanh bên và chọn **Trình quản lý FAQ**.
3. Thêm các cặp câu hỏi-trả lời qua trang.
4. Khi người dùng đặt câu hỏi trong cuộc trò chuyện, LLM sẽ sử dụng công cụ `search_faq` để tìm các mục FAQ phù hợp và trả lời tương ứng.
