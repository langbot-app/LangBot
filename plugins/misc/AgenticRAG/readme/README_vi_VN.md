# AgenticRAG

AgenticRAG hiển thị các cơ sở kiến ​​thức được định cấu hình cho quy trình hiện tại dưới dạng Công cụ LLM, do đó, tổng đài viên có thể kiểm tra các KB có sẵn và truy xuất các khối có liên quan theo yêu cầu.

## Nó làm gì

- Cung cấp một công cụ duy nhất,`query_know`
- Hỗ trợ hai hành động:
  -`list`: liệt kê các cơ sở kiến thức có sẵn cho quy trình hiện tại
  -`query`: truy xuất các tài liệu liên quan từ một hoặc nhiều cơ sở kiến thức đã chọn
- Trả về kết quả truy xuất dưới dạng JSON để tác nhân có thể tiếp tục suy luận về chúng

## Thiết kế tổng thể

AgenticRAG không phải là một chương trình phụ trợ RAG mới. Đây là một plugin lớp điều khiển có chức năng thay đổi**người quyết định khi nào quá trình truy xuất sẽ diễn ra**.

Thay vì người chạy luôn tự động đưa kiến ​​thức vào trước khi mô hình phản hồi, AgenticRAG chuyển quá trình truy xuất vào vòng lặp tác nhân:

- trước tiên mô hình sẽ quyết định xem có cần truy xuất hay không
- mô hình có thể kiểm tra cơ sở kiến thức sẵn có
- mô hình có thể chọn một KB hoặc truy vấn nhiều KB song song
- việc truy xuất chỉ xảy ra khi mô hình yêu cầu rõ ràng

Thiết kế này tồn tại để giải quyết một vấn đề cụ thể: việc truy xuất luôn bật ngây thơ rất đơn giản nhưng nó cũng gây ra nhiễu, bối cảnh lãng phí và các đoạn không liên quan trong nhiều lượt.

## Thiết kế

Plugin này có chủ ý mỏng. Nó không triển khai chương trình phụ trợ RAG mới. Thay vào đó, nó bao gồm các API truy xuất kiến ​​thức trong phạm vi truy vấn được tích hợp sẵn của LangBot:

-`list_pipeline_know_bases()`để liệt kê các KB hiển thị cho truy vấn hiện tại
-`retrieve_know()`để truy xuất các mục hàng đầu từ một hoặc nhiều KB đã chọn

`query_id`được đưa vào trong thời gian chạy khi công cụ được gọi, sau đó được lưu trữ bên trong`QueryBasedAPIProxy`. Do đó, mã công cụ chỉ cần truyền các tham số nghiệp vụ như`kb_id`hoặc`kb_ids`,`query_text`và`top_k`.

Mặc dù thời gian chạy cơ bản có thể hỗ trợ các bộ lọc siêu dữ liệu nhưng plugin này không hiển thị các bộ lọc thô cho tác nhân trong luồng công cụ tác nhân hiện tại. Các công cụ kiến ​​thức và chương trình phụ trợ vectơ khác nhau có thể sử dụng các trường siêu dữ liệu, định dạng giá trị và ngữ nghĩa bộ lọc khác nhau và tác nhân hiện không có nguồn lược đồ đáng tin cậy cho các trường đó.

Các phiên bản trong tương lai có thể hiển thị tính năng lọc siêu dữ liệu sau khi hệ sinh thái có cách thống nhất hơn để mô tả các trường và toán tử có thể lọc cho từng cơ sở kiến ​​thức.

## Nó hoạt động như thế nào

Một yêu cầu AgenticRAG có bốn giai đoạn chính:

### 1. Vô hiệu hóa truy xuất đơn giản

Trong`PromptPreProcessing`, plugin sẽ kiểm tra xem LLM đang hoạt động có hỗ trợ gọi công cụ hay không.

- nếu việc gọi công cụ được hỗ trợ, nó sẽ xóa`_know_base_uuids`của người chạy nên bước truy xuất trước ngây thơ thông thường sẽ bị bỏ qua
- nếu việc gọi công cụ không được hỗ trợ, nó sẽ tiếp tục kích hoạt RAG nguyên bản như một phương án dự phòng để việc truy xuất KB không biến mất hoàn toàn

### 2. Đưa chính sách truy xuất vào dấu nhắc hệ thống

Đồng thời, AgenticRAG đưa vào một lời nhắc hệ thống bổ sung để thông báo cho mô hình rằng:

- KB được định cấu hình là nguồn thông tin chính xác về các dữ kiện trong phạm vi
- không có dự phòng truy xuất tự động
- đối với các câu hỏi thực tế, chính sách, thủ tục, sản phẩm và tên miền cụ thể, nên ưu tiên`query_know`

Điều này quan trọng vì chỉ mô tả công cụ thường không đủ mạnh để thay đổi hành vi của mô hình một cách đáng tin cậy.

### 3. Để model kiểm tra và truy vấn KB

Sau đó, tổng đài viên có thể sử dụng`query_know`theo hai bước:

-`action="list"`để xem KB nào có sẵn
-`action="query"`để tìm kiếm song song một KB hoặc nhiều KB

Để truy xuất một KB, tham số ưu tiên là`kb_id`.
Để truy xuất nhiều KB, hãy sử dụng`kb_ids`.

### 4. Trả về kết quả truy xuất dưới dạng JSON có cấu trúc

Công cụ này hợp nhất các kết quả, chú thích chúng bằng`know_base_id`và trả về JSON để mô hình có thể tiếp tục suy luận, sử dụng công cụ hoặc trả lời cuối cùng.

## Hành vi truy xuất

Khi AgenticRAG được bật, nó sẽ vô hiệu hóa quá trình xử lý trước RAG đơn giản tự động của người chạy cho đường dẫn hiện tại.

- Việc truy xuất không còn được thực hiện tự động trước khi mô hình trả lời
- Việc truy vấn cơ sở kiến thức hiện nay có được quyết định theo mô hình có chủ ý hay không thông qua`query_know`
- Nếu mô hình không gọi công cụ thì sẽ không có nội dung KB nào được đưa vào ngữ cảnh

Có một ngoại lệ quan trọng:

- nếu LLM đang hoạt động không hỗ trợ gọi công cụ, AgenticRAG sẽ tiếp tục kích hoạt RAG nguyên bản thay vì tắt nó

Điều này làm giảm tiếng ồn truy xuất vô điều kiện, nhưng nó cũng có nghĩa là nhắc nhở các vấn đề. Do đó, việc triển khai hiện tại sử dụng**cả hai**:

- lời nhắc công cụ về`query_know`
- lời nhắc hệ thống được đưa vào trong`PromptPreProcessing`

Cùng nhau, họ thiên về mô hình theo hướng truy xuất các câu hỏi thực tế, chính sách, thủ tục, sản phẩm và các câu hỏi theo miền cụ thể khác.

## Tại sao nó được thiết kế theo cách này

Plugin này được tối ưu hóa cho một sự cân bằng cụ thể:

- giữ KB hiện có của LangBot và cơ sở hạ tầng truy xuất
- loại bỏ truy xuất luôn bật không cần thiết
- để mô hình đưa ra quyết định truy xuất rõ ràng
- vẫn giữ hành vi truy xuất bị hạn chế đối với quy trình hiện tại

So với RAG ngây thơ, thiết kế này mang lại cho bạn:

- bối cảnh ít liên quan hơn ở những lượt không cần truy cập KB
- kiểm soát tốt hơn KB nào được truy vấn
- chỗ cho việc truy xuất lặp lại, truy vấn lại và lý luận nhiều KB

Nhược điểm cũng có thực: nếu mô hình không bao giờ gọi công cụ thì sẽ không có nội dung KB nào xuất hiện. Đó là lý do tại sao plugin bổ sung rõ ràng lời nhắc hướng truy xuất, thay vì cho rằng mô hình sẽ chọn truy xuất thường xuyên một cách tự nhiên.

Đây cũng là lý do tại sao plugin hiện phát hiện khả năng gọi công cụ trước khi vô hiệu hóa RAG ngây thơ. Nếu không có biện pháp bảo vệ đó, việc bật AgenticRAG trên một mô hình không có khả năng sử dụng công cụ sẽ vô tình làm hỏng hoàn toàn quá trình truy xuất KB.

## Ranh giới an ninh

Công cụ này nằm trong phạm vi quy trình hiện tại.

- Thời gian chạy LangBot cũng xác thực rằng`kb_id`được yêu cầu thuộc về đường dẫn hiện tại trước khi thực hiện truy xuất

Điều này có nghĩa là chỉ riêng việc tiêm nhắc sẽ không cho phép tác nhân truy vấn các KB tùy ý bên ngoài cấu hình đường ống.

## Cách sử dụng

1. Cài đặt và kích hoạt plugin.
2. Định cấu hình một hoặc nhiều cơ sở kiến ​​thức trong cài đặt tác nhân cục bộ của đường dẫn hiện tại.
3. Để Agent gọi`query_know`:
   - Bắt đầu với`action="list"`để kiểm tra các KB có sẵn
   - Sau đó gọi`action="query"`với`kb_id`cho một KB, hoặc`kb_ids`cho nhiều KB được truy vấn song song
   - Cung cấp`query_text`và`top_k`tùy chọn để đếm kết quả được hợp nhất

## Thông số

Đối với`action="query"`, công cụ hiện chấp nhận:

-`kb_id`: UUID cơ sở tri thức đích để truy xuất KB đơn; được ưu tiên khi truy vấn chính xác một KB
-`kb_ids`: mảng tùy chọn gồm các UUID cơ sở kiến thức đích để truy xuất song song nhiều KB; chỉ sử dụng khi truy vấn nhiều KB
-`query_text`: truy xuất văn bản truy vấn
-`top_k`: số nguyên dương tùy chọn, mặc định`5`, áp dụng cho tập kết quả đã hợp nhất

Nếu một truy vấn KB không thành công trong khi các truy vấn khác thành công, thì công cụ này sẽ trả về một đối tượng JSON có`results`và`failed_kbs`để tác nhân có thể tiếp tục với một phần kết quả.

## Dòng chảy điển hình

1. Đại lý liệt kê các KB hiện có.
2. Đại lý chọn một KB hoặc một nhóm nhỏ KB dựa trên tên và mô tả.
3. Tác nhân gửi truy vấn truy xuất tập trung.
4. Tác nhân sử dụng các đoạn được trả về để trả lời hoặc tiếp tục sử dụng công cụ.

## Ý định thúc giục

Lớp nhắc nhở được thiết kế để truyền đạt hai điều tới mô hình:

- những cơ sở kiến thức này là nguồn có thẩm quyền cho thông tin trong phạm vi
- không tồn tại truy xuất tự động dự phòng sau khi bật AgenticRAG

Nếu không có hướng dẫn đó, LLM có thể quá tin tưởng vào kiến ​​thức đã được đào tạo trước và khả năng truy xuất chưa được sử dụng của nó. Do đó, việc triển khai hiện tại củng cố chính sách tương tự ở cả lớp nhắc hệ thống và lớp nhắc nhở công cụ.

## Ghi nhật ký

Plugin hiện phát ra nhật ký trong quá trình thực thi công cụ để bạn có thể quan sát cách LLM đang sử dụng AgenticRAG trong thực tế.

Bạn sẽ thấy nhật ký cho:

- bắt đầu lệnh gọi công cụ, bao gồm`query_id`,`action`và các phím tham số
- Bắt đầu/kết thúc danh sách KB và hiển thị bao nhiêu KB
- bắt đầu truy xuất, bao gồm các KB đã chọn,`top_k`và bản xem trước`văn bản truy vấn`rút gọn
- bắt đầu truy xuất trên mỗi KB/thành công/thất bại
- tóm tắt truy xuất cuối cùng, bao gồm số kết quả được hợp nhất, số KB không thành công và số kết quả được trả về

Thông điệp tường trình điển hình trông giống như:

```text
[AgenticRAG] tool call started: query_id=123 action=query params_keys=['action', 'kb_id', 'query_text', 'top_k']
[AgenticRAG] retrieval requested: query_id=123 kb_ids=['kb-1'] kb_count=1 top_k=5 query='what is the refund policy'
[AgenticRAG] querying knowledge base: query_id=123 kb_id=kb-1 top_k=5
[AgenticRAG] knowledge base query succeeded: query_id=123 kb_id=kb-1 result_count=4
[AgenticRAG] retrieval completed: query_id=123 merged_results=4 failed_kbs=0
```
