# Tự động dịch

Tự động phát hiện tin nhắn bằng tiếng nước ngoài trong cuộc trò chuyện nhóm và dịch chúng bằng LLM.

## Đặc trưng

- 🌐 Tự động phát hiện ngôn ngữ tin nhắn - không cần lệnh thủ công
- 🤖 Sử dụng LLM để có bản dịch tự nhiên, chất lượng cao
- ⚙️ Ngôn ngữ mục tiêu có thể định cấu hình (tiếng Trung, tiếng Anh, tiếng Nhật, tiếng Hàn, tiếng Pháp, tiếng Tây Ban Nha)
- 📏 Bỏ qua tin nhắn ngắn, biểu tượng cảm xúc và URL
- 🔇 Chỉ dịch khi cần - các tin nhắn cùng ngôn ngữ sẽ bị bỏ qua
- 👥 Theo mặc định, chỉ dành cho nhóm, hỗ trợ trò chuyện riêng tư tùy chọn

## Nó hoạt động như thế nào

1. Khi nhận được tin nhắn trong cuộc trò chuyện nhóm, plugin sẽ gửi văn bản tới LLM
2. LLM phát hiện xem tin nhắn có ở ngôn ngữ khác với mục tiêu đã định cấu hình hay không
3. Nếu cần dịch, plugin sẽ trả lời bằng văn bản đã dịch có tiền tố 🌐
4. Các tin nhắn đã có trong ngôn ngữ đích sẽ bị bỏ qua một cách âm thầm

## Cấu hình

| Tùy chọn | Mô tả | Mặc định |
|---|---|---|
| Ngôn ngữ mục tiêu | Ngôn ngữ cần dịch sang | Tiếng Trung (Giản thể) |
| Mô hình LLM | Mô hình sử dụng để dịch | Có sẵn đầu tiên |
| Độ dài văn bản tối thiểu | Bỏ qua tin nhắn ngắn hơn thế này | 4 ký tự |
| Bật trong Trò chuyện riêng tư | Đồng thời dịch tin nhắn riêng tư | Tắt |
