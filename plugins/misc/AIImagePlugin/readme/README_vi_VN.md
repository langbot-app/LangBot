# Plugin tạo hình ảnh AI

## Giới thiệu

Một plugin vẽ tương thích với định dạng API tạo hình ảnh OpenAI. Hỗ trợ mọi dịch vụ tương thích với API tạo hình ảnh OpenAI.

## Đặc trưng

- ✅ Hoàn toàn tương thích với định dạng API tạo hình ảnh OpenAI
- 🎨 Hỗ trợ tên mô hình và điểm cuối API tùy chỉnh
- 📐 Hỗ trợ nhiều tỷ lệ khung hình hình ảnh
- 🔧 Tùy chọn cấu hình linh hoạt

## Hướng dẫn cấu hình

### Cấu hình API

-**Điểm cuối API**: Mặc định là`https://api.qhaigc.net`, có thể được tùy chỉnh theo bất kỳ điểm cuối API kiểu OpenAI tương thích nào
-**Khóa API**: Nhận khóa API của bạn từ [https://api.qhaigc.net/console/token](https://api.qhaigc.net/console/token)
-**Tên mẫu**: Bạn có thể đặt tên mẫu tùy chỉnh, mặc định là`qh-draw-x1-pro`

### Tùy chọn kích thước hình ảnh

Các kích thước hình ảnh sau được hỗ trợ:

- Hình vuông 1:1 (1024x1024)
- Hình vuông 1:1 (1280x1280)
- Chân dung 3:5 (768x1280)
- Phong cảnh 5:3 (1280x768)
- Chân dung 9:16 (720x1280)
- Phong cảnh 16:9 (1280x720)
- Phong cảnh 4:3 (1024x768)
- Chân dung 3:4 (768x1024)

## Cách sử dụng

Sử dụng lệnh`!draw`để tạo hình ảnh:

```bash
# Generate an image
!draw a beautiful sunset landscape
!draw a cat sitting on a rainbow
```

## Các bước cài đặt

1. Cài đặt plugin này từ trang quản lý plugin LangBot
2. Lấy Khóa API của bạn: [https://api.qhaigc.net/console/token](https://api.qhaigc.net/console/token)
3. Điền API Key vào cấu hình plugin
4. (Tùy chọn) Định cấu hình điểm cuối API, tên kiểu máy và kích thước hình ảnh mặc định

## Model được hỗ trợ

###Dòng chuối Nano

-**Nano Banana 1**(Phát hành tháng 8 năm 2025): Một mô hình tạo hình ảnh của Google DeepMind, dựa trên kiến ​​trúc Gemini 2.5 Flash với thông số 450M đến 8B. Điểm mạnh cốt lõi là tính nhất quán của vai trò, kết hợp nhiều hình ảnh và chỉnh sửa cục bộ. Nó dẫn đầu bảng xếp hạng chỉnh sửa hình ảnh LMArena với số điểm 1362 và được sử dụng rộng rãi trong thương mại điện tử, thiết kế, giáo dục, v.v.

-**Nano Banana 2**(Ra mắt tháng 11 năm 2025): Bản nâng cấp toàn diện của thế hệ đầu tiên, hỗ trợ độ phân giải gốc 2K, với tùy chọn siêu phân giải 4K. Tốc độ tạo được cải thiện 300%, cho phép thực hiện các cảnh phức tạp chỉ trong 10 giây. Những đột phá lớn trong việc diễn đạt văn bản và đạo hàm công thức toán học của tiếng Trung. Nó hiểu logic vật lý và kiến ​​thức thế giới, sử dụng kiến ​​trúc kết hợp "nhận thức + thế hệ" nhằm cách mạng hóa năng suất cho các ngành công nghiệp sáng tạo.

### Dòng tranh vẽ Qihang AI

-**qh-draw-3d**: Tập trung tạo hình ảnh theo phong cách 3D phổ biến, đặc trưng bởi mô hình 3D tinh tế và hiệu ứng hình ảnh 3D mạnh mẽ.
-**qh-draw-4d**: Tập trung tạo hình ảnh phong cách 4D phổ biến, với mô hình 4D tinh xảo và hình ảnh gần giống thực tế nhưng không phải ảnh thực tế.
-**qh-draw-x1-pro**: Mô hình Qihang AI Vẽ x1-pro, dựa trên các mô hình SD nguồn mở với khả năng hiểu ngôn ngữ tự nhiên.
-**qh-draw-x2-preview**: Mô hình vẽ chuyên nghiệp tự phát triển V2.0. Dựa trên x1-pro, nó nâng cao khả năng hiểu ngôn ngữ và khả năng vẽ toàn diện, giúp nó phù hợp với nhiều tác vụ hơn.
-**qh-draw:Phong cách truyện tranh Hàn Quốc**: Chuyên tạo hình ảnh phong cách truyện tranh 2D cổ điển Hàn Quốc, màu sắc tươi sáng, đường nét mượt mà, tâm cảnh cảnh chính xác dành cho truyện tranh Hàn Quốc.

### Danh sách mẫu có sẵn

`nano-banana-1`,`nano-banana-2`,`qh-draw-3d`,`qh-draw-4d`,`qh-draw-x1-pro`,`qh-draw-x2-preview`,`qh-draw:Hàn Quốc-truyện tranh`

## Khả năng tương thích

Plugin này tương thích với mọi dịch vụ tuân theo đặc tả API tạo hình ảnh OpenAI, bao gồm nhưng không giới hạn ở:

- OpenAI DALL-E 3
- Các dịch vụ tạo hình ảnh khác tương thích với định dạng OpenAI

## Giấy phép

Giấy phép của tôi
