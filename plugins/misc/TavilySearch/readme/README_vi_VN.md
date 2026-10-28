# Plugin TavilySearch

Một plugin [LangBot](https://github.com/langbot-app/langbot) cung cấp khả năng tìm kiếm bằng Tavily API, một công cụ tìm kiếm được xây dựng riêng cho các tác nhân AI (LLMs).

## Tính năng

- Tìm kiếm web thời gian thực được hỗ trợ bởi Tavily
- Hỗ trợ các độ sâu tìm kiếm khác nhau (basic/advanced)
- Tìm kiếm theo chủ đề cụ thể (general/news/finance)
- Bao gồm câu trả lời do AI tạo ra
- Bao gồm hình ảnh liên quan
- Bao gồm nội dung HTML thô
- Tùy chỉnh số lượng kết quả

## Cài đặt

1. Cài đặt plugin.

2. Cấu hình khóa Tavily API của bạn:
   - Nhận khóa API của bạn từ [Tavily](https://tavily.com/)
   - Thêm khóa API vào cấu hình plugin trong LangBot

## Cách sử dụng

Plugin này thêm một công cụ `tavily_search` có thể được LLMs sử dụng trong các cuộc hội thoại.

### Thông số

- **query** (bắt buộc): Chuỗi truy vấn tìm kiếm
- **search_depth** (tùy chọn): "basic" (mặc định) hoặc "advanced"
- **topic** (tùy chọn): "general" (mặc định), "news", hoặc "finance"
- **max_results** (tùy chọn): Số lượng kết quả (1-20, mặc định: 5)
- **include_answer** (tùy chọn): Bao gồm câu trả lời do AI tạo ra (mặc định: false)
- **include_images** (tùy chọn): Bao gồm hình ảnh liên quan (mặc định: false)
- **include_raw_content** (tùy chọn): Bao gồm nội dung HTML thô (mặc định: false)

### Ví dụ

Khi trò chuyện với LangBot của bạn, LLM có thể tự động sử dụng công cụ này:

```
User: Tin tức mới nhất về trí tuệ nhân tạo là gì?

Bot: [Sử dụng công cụ tavily_search với topic="news"]
```

## Phát triển

Để phát triển hoặc sửa đổi plugin này:

1. Chỉnh sửa logic công cụ trong `components/tools/tavily_search.py`
2. Sửa đổi cấu hình trong `manifest.yaml`
3. Cập nhật các thông số công cụ trong `components/tools/tavily_search.yaml`

## Cấu hình

Plugin yêu cầu cấu hình sau:

- **tavily_api_key**: Khóa Tavily API của bạn (bắt buộc)

## Giấy phép

Plugin này là một phần của hệ sinh thái plugin LangBot.

## Liên kết

- [Tài liệu Tavily API](https://docs.tavily.com/)
- [Tài liệu LangBot](https://langbot.app/docs/)
