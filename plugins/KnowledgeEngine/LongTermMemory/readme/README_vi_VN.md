# LongTermMemory

Plugin bộ nhớ dài hạn cho LangBot với thiết kế hai lớp:

- L1 cấu hình cốt lõi (Core profile) được chèn vào prompt hệ thống
- L2 bộ nhớ tình tiết (Episodic memory) được truy xuất qua tìm kiếm vector và chèn vào ngữ cảnh

## Chức năng của nó

- Cung cấp công cụ `remember` để ghi nhớ các bộ nhớ tình tiết
- Cung cấp công cụ `recall_memory` để tra cứu chủ động bộ nhớ tình tiết với các bộ lọc được kiểm soát
- Cung cấp công cụ `update_profile` để cập nhật cấu hình ổn định
- Cung cấp công cụ `forget` để xóa các bộ nhớ tình tiết cụ thể do agent khởi xướng
- Chèn bộ nhớ cấu hình và danh tính người nói hiện tại thông qua một EventListener
- Sử dụng một EventListener để truy xuất và chèn các bộ nhớ tình tiết liên quan trước khi gọi mô hình
- Cung cấp lệnh `!memory` để kiểm tra và gỡ lỗi
- Cung cấp trang web **Bảng điều khiển Bộ nhớ** để kiểm tra trực quan: hồ sơ, tình tiết (có phân trang), nhật ký kiểm toán, xuất dữ liệu, kiểm tra sức khỏe cô lập metadata, và ảnh chụp lần chèn bộ nhớ gần nhất
- Cung cấp lệnh `!memory list [page]` để duyệt các bộ nhớ tình tiết với tính năng phân trang
- Cung cấp lệnh `!memory forget <episode_id>` để xóa một tình tiết cụ thể
- Cung cấp lệnh `!memory search <query>` để tìm kiếm các tình tiết (kết quả bao gồm ID tình tiết)
- Cung cấp lệnh `!memory export` để xuất cấu hình L1 cho phiên hiện tại dưới dạng JSON
- Tự động thay thế các tình tiết cũ liên quan khi có bản sửa lỗi/cập nhật thông tin/làm rõ được lưu trữ

## Thiết kế tổng thể

Plugin này không cố gắng đổ toàn bộ lịch sử trò chuyện vào ngữ cảnh. Thay vào đó, nó chia bộ nhớ dài hạn thành hai lớp với các hành vi lưu trữ và truy xuất khác nhau:

- **L1 cấu hình cốt lõi**: các sự thật ổn định, tần suất thấp như tên, sở thích, danh tính và các ghi chú lâu dài
- **L2 bộ nhớ tình tiết**: các sự thật nhạy cảm với thời gian và tình huống như các sự kiện gần đây, kế hoạch và trải nghiệm

Sự phân chia này tồn tại vì một lý do:

- Dữ liệu cấu hình ổn định rẻ và đáng tin cậy để chèn vào prompt hệ thống
- Bộ nhớ tình tiết liên tục phát triển theo thời gian, vì vậy nó nên được truy xuất theo yêu cầu thay vì chèn đầy đủ sau mỗi lượt
- Agent nên cập nhật các sự thật cấu hình ổn định khác với các bộ nhớ dạng sự kiện

## Sự khác biệt so với bộ nhớ kiểu trợ lý cá nhân OpenClaw

Gần đây, nhiều hệ thống agent đã thảo luận về các thiết kế như OpenClaw: bộ nhớ dài hạn được lưu trữ chủ yếu dưới dạng các tệp văn bản mà người dùng có thể đọc được như `MEMORY.md`, kết hợp với tóm tắt, phản tư và logic truy xuất nhẹ nhàng.

Cách tiếp cận đó có những điểm mạnh rõ rệt:

- bộ nhớ hoàn toàn minh bạch với người dùng
- văn bản thuần túy tự nhiên dễ dàng sao lưu, đồng bộ hóa và kiểm soát phiên bản
- nó rất phù hợp với quy trình làm việc cá nhân của một người dùng đơn lẻ, trợ lý đơn lẻ và tính liên tục cao
- khi khối lượng bộ nhớ nhỏ, việc hiểu toàn bộ văn bản thực sự có thể "đủ tốt"

Nhưng LongTermMemory trong LangBot đang giải quyết một vấn đề khác. Một đợt triển khai LangBot điển hình thường giống như:

- một bot phục vụ nhiều cuộc trò chuyện nhóm và trò chuyện riêng tư
- một thực thể plugin xử lý nhiều phiên và nhiều người nói
- bộ nhớ bao gồm ngữ cảnh nhóm dùng chung, cấu hình người nói hiện tại và các tình tiết cấp phiên
- các ranh giới cô lập rõ ràng giữa các phiên, bot và người nói

Vì lý do đó, chúng tôi không áp dụng thiết kế "một tệp văn bản duy nhất là nguồn sự thật". Chúng tôi đã chọn một kiến trúc phân lớp phù hợp hơn với mô hình runtime đa phiên của LangBot.

### Bộ nhớ kiểu OpenClaw được tối ưu hóa cho điều gì

Về mặt trừu tượng, thiết kế đó được tối ưu hóa cho:

- **trợ lý cá nhân một người dùng**
- **văn bản mà con người có thể đọc được là hình thức bộ nhớ dài hạn chính**
- **tính minh bạch, khả năng chỉnh sửa và tính liên tục của câu chuyện**
- **giả định rằng kích thước bộ nhớ vẫn có thể quản lý được và người dùng sẵn sàng trực tiếp quản lý nó**

Đó là một sự phù hợp rất hợp lý cho các người bạn đồng hành AI cá nhân, trợ lý nghiên cứu và quy trình làm việc trợ lý riêng.

### Tại sao LangBot không chỉ đơn giản là sao chép mô hình đó

LongTermMemory được thiết kế xung quanh các ràng buộc vận hành khác nhau: đa phiên, đa người nói, cô lập rõ ràng, chèn có kiểm soát và truy xuất tình tiết có thể phục hồi.

Nếu chúng ta biến bộ nhớ dài hạn thành một tệp kể chuyện duy nhất như `MEMORY.md`, một số vấn đề sẽ nhanh chóng xuất hiện:

- **Cô lập sẽ trở nên khó khăn**
  - làm thế nào các bộ nhớ từ nhóm A, nhóm B và trò chuyện riêng tư C có thể cùng tồn tại an toàn?
  - làm thế nào để bạn tách bạch rõ ràng cấu hình ổn định của một người nói khỏi nhật ký câu chuyện dùng chung?
- **Độ chi tiết của việc chèn sẽ trở nên không ổn định**
  - prompt hệ thống cần trạng thái cấu hình ổn định, không phải toàn bộ nhật ký theo trình tự thời gian
  - truy xuất tự động cần các lát cắt bộ nhớ liên quan nhất cho truy vấn hiện tại, không phải toàn bộ câu chuyện
- **Ranh giới đa người dùng là ưu tiên hàng đầu trong LangBot**
  - trong trợ lý cá nhân, "người dùng" thường là một người
  - trong LangBot, người nói hiện tại, phiên hiện tại và bot hiện tại đều quan trọng
- **Chèn tự động và truy xuất chủ động là các nhu cầu khác nhau**
  - dữ liệu cấu hình ổn định nên được chèn một cách nhất quán
  - bộ nhớ tình tiết nên được truy xuất có chọn lọc
  - buộc cả hai vào một hình thức bộ nhớ chỉ có văn bản trở nên vụng về

### Sự đánh đổi mà chúng tôi đã thực hiện

Vì vậy, thiết kế của LongTermMemory về cơ bản là sự đánh đổi này:

- **Những gì chúng tôi mượn từ triết lý đó**
  - bộ nhớ không nên chỉ được coi là một kho lưu trữ vector hộp đen
  - cấu hình ổn định, bộ nhớ thời gian và điều chỉnh hành vi dài hạn đều quan trọng
  - không phải mọi thứ đều nên được đổ vào ngữ cảnh sau mỗi lượt

- **Nơi chúng tôi cố tình khác biệt**
  - chúng tôi không sử dụng nhật ký văn bản kể chuyện làm nguồn sự thật bộ nhớ duy nhất
  - chúng tôi chia cấu hình ổn định và bộ nhớ tình tiết một cách rõ ràng
  - chúng tôi ưu tiên cô lập giữa các phiên, người nói và bot
  - chúng tôi để bộ nhớ L2 cắm tự nhiên vào hệ thống KB / truy xuất của LangBot thay vì chỉ dựa vào việc đọc toàn văn

Nói tóm lại:

- OpenClaw chủ yếu trả lời: "Làm thế nào một trợ lý cá nhân nên giữ bộ nhớ dài hạn có thể đọc được, có thể chỉnh sửa và mang tính phản tư?"
- LongTermMemory chủ yếu trả lời: "Làm thế nào một bot làm việc trên các nhóm và trò chuyện riêng tư nên giữ trạng thái cấu hình ổn định và bộ nhớ trải nghiệm có thể truy xuất dưới các quy tắc cô lập rõ ràng?"

Không có hướng đi nào là "tốt hơn" một cách tuyệt đối. Chúng tối ưu hóa cho các sản phẩm khác nhau và các chế độ lỗi khác nhau.

## Thiết kế

Plugin này cố tình bám sát các điểm mở rộng hiện có của LangBot thay vì yêu cầu các bản vá lõi tùy chỉnh.

- Cấu hình L1 được lưu trữ trong bộ nhớ plugin dưới dạng JSON
- Bộ nhớ tình tiết L2 được lưu trữ trong cơ sở dữ liệu vector
- Truy xuất bộ nhớ được bật cho mỗi pipeline bằng cách đính kèm KnowledgeEngine của plugin này
- Plugin hiện giả định một KB bộ nhớ duy nhất cho mỗi thực thể plugin và cô lập bộ nhớ bằng siêu dữ liệu (metadata)

Bản thực hiện hiện tại được xây dựng xung quanh các API hiện có của LangBot và SDK. Nếu sau này LangBot thêm nhiều API hướng tới bộ nhớ rõ ràng hơn, API danh tính phiên hoặc API đăng ký KB, plugin có thể được đơn giản hóa, nhưng kiến trúc hiện tại vẫn sẽ có giá trị.

### Khả năng tương thích của Backend cơ sở dữ liệu Vector

Bộ nhớ tình tiết L2 dựa trên các trường siêu dữ liệu tùy ý (`user_key`, `episode_id`, `tags`, `importance`, v.v.) để cô lập và lọc. Không phải tất cả các backend cơ sở dữ liệu vector của LangBot đều hỗ trợ siêu dữ liệu tùy ý:

| Backend | Siêu dữ liệu tùy ý | Hỗ trợ LongTermMemory |
|---------|-------------------|----------------------|
| **Chroma** (mặc định) | Có | Hỗ trợ đầy đủ |
| **Qdrant** | Có | Hỗ trợ đầy đủ |
| **SeekDB** | Có | Hỗ trợ đầy đủ |
| **Milvus** | Không (schema cố định: `text`, `file_id`, `chunk_uuid`) | Không hỗ trợ |
| **pgvector** | Không (schema cố định: `text`, `file_id`, `chunk_uuid`) | Không hỗ trợ |

Milvus và pgvector sử dụng một schema cột cố định và âm thầm loại bỏ các trường siêu dữ liệu mà chúng không nhận ra. Điều này có nghĩa là việc cô lập dựa trên siêu dữ liệu (lọc `user_key`) và các lệnh bộ nhớ tình tiết (`!memory list`, `!memory forget`, `!memory search`) sẽ không hoạt động chính xác trên các backend này — các bộ lọc sẽ bị bỏ qua và các truy vấn có thể trả về kết quả không có phạm vi.

Nếu bạn cần sử dụng LongTermMemory, hãy sử dụng Chroma, Qdrant hoặc SeekDB làm backend cơ sở dữ liệu vector của bạn.

## Cách thức hoạt động

Một luồng bộ nhớ dài hạn từ đầu đến cuối có bốn phần chính:

### 1. Ghi cấu hình L1

- Agent sử dụng `update_profile` để ghi lại các sự thật ổn định
- Dữ liệu được lưu trữ trong bộ nhớ plugin dưới dạng JSON có cấu trúc
- Cấu hình được lưu trữ ở phạm vi `session` (phiên) hoặc `speaker` (người nói)

### 2. Ghi tình tiết L2

- Agent sử dụng `remember` để ghi lại bộ nhớ dạng sự kiện
- Mỗi bộ nhớ mang siêu dữ liệu như dấu thời gian, tầm quan trọng, thẻ và phạm vi
- Những bộ nhớ đó được nhúng và lưu trữ trong cơ sở dữ liệu vector thông qua KnowledgeEngine của plugin

### 3. Tự động chèn trước khi phản hồi

- Trong quá trình `PromptPreProcessing`, EventListener sẽ phân giải danh tính phiên hiện tại
- Đối với L1:
  - nó tải cấu hình phiên dùng chung
  - nó tải cấu hình người nói hiện tại
  - nó chèn cả hai, cùng với danh tính người nói hiện tại, vào `default_prompt`
- Đối với L2:
  - nó chạy một truy xuất tình tiết bằng tin nhắn của người dùng hiện tại
  - các bộ nhớ được truy xuất được chèn vào dưới dạng các khối ngữ cảnh thực tế

Vì vậy cả L1 và L2 đều đi vào ngữ cảnh mô hình trước khi tạo câu trả lời, nhưng dưới các hình thức khác nhau: L1 dưới dạng bộ nhớ prompt hệ thống, L2 dưới dạng ngữ cảnh được truy xuất.

### 4. Tra cứu chủ động và gỡ lỗi

- Nếu việc chèn tự động là không đủ, agent có thể gọi `recall_memory`
- Để kiểm tra và gỡ lỗi, bạn có thể sử dụng `!memory`, `!memory profile`, `!memory search`, `!memory list` và `!memory forget`
- `!memory export` chỉ xuất cấu hình L1 của phạm vi hiện tại để sao lưu hoặc di chuyển

## Quan hệ với AgenticRAG

Khi AgenticRAG được bật cùng với LongTermMemory:

- LongTermMemory loại bỏ KB bộ nhớ của chính nó khỏi quá trình tiền xử lý RAG thông thường
- truy xuất L2 tự động vẫn được xử lý bởi chính LongTermMemory
- cùng một KB bộ nhớ vẫn có thể được truy vấn rõ ràng thông qua công cụ `query_knowledge` của AgenticRAG

Điều này tránh việc truy xuất trùng lặp trong khi vẫn bảo toàn cả hai con đường:

- truy xuất bộ nhớ tự động
- truy xuất sâu hơn do agent khởi xướng khi cần thiết

## Tại sao không có bộ lọc siêu dữ liệu phía Agent

Runtime bên dưới có thể hỗ trợ lọc siêu dữ liệu, nhưng plugin này hiện không để lộ các bộ lọc siêu dữ liệu thô tùy ý cho luồng của agent.

Lý do:

- Các công cụ kiến thức và backend vector khác nhau không chia sẻ một schema siêu dữ liệu thống nhất
- Tên trường bộ lọc, định dạng giá trị và các toán tử được hỗ trợ có thể khác nhau
- Agent hiện không có nguồn schema ổn định để xây dựng các bộ lọc đáng tin cậy

Nếu sau này LangBot cung cấp một cách thống nhất để mô tả các trường siêu dữ liệu có thể lọc trên mỗi cơ sở kiến thức, tính năng lọc siêu dữ liệu phía agent có thể được thêm vào.

Plugin này cung cấp một giao diện công cụ truy xuất có kiểm soát cho schema bộ nhớ ổn định của riêng nó. Công cụ đó hỗ trợ các bộ lọc được chọn như người nói và phạm vi thời gian, mà không để lộ cú pháp bộ lọc đặc thù của backend cho mô hình.

## Mô hình cô lập

Hai chế độ cô lập được hỗ trợ:

- `session`: mỗi cuộc trò chuyện nhóm hoặc trò chuyện riêng tư có bộ nhớ độc lập
- `bot`: tất cả các phiên dưới cùng một bot dùng chung bộ nhớ

Trong mô hình triển khai hiện tại, điều này nói chung là đủ vì các thực thể plugin thường được gắn với một môi trường runtime/bot LangBot cụ thể.

## Chi tiết các quy tắc cô lập

Có hai khái niệm phạm vi liên quan nhưng hơi khác nhau trong plugin này:

- **session_name**: danh tính cuộc trò chuyện được truyền qua đường dẫn truy vấn / truy xuất hiện tại, có định dạng là `{launcher_type}_{launcher_id}`
- **session_key**: khóa lưu trữ L1 nội bộ của plugin. Khi có `bot_uuid`, nó trở thành `{bot_uuid}:{launcher_type}_{launcher_id}`; nếu không nó sẽ trở lại thành `{launcher_type}_{launcher_id}`
- **scope_key / user_key**: khóa thực sự được sử dụng để lưu trữ cấu hình hoặc cô lập truy xuất L2

### Cách các cấu hình L1 được cô lập

Các cấu hình L1 luôn được lưu trữ trong phạm vi cuộc trò chuyện hiện tại:

- `session profile`
  - cấu hình dùng chung cho cuộc trò chuyện hiện tại
  - hữu ích cho ngữ cảnh ổn định cấp nhóm hoặc cấp cuộc trò chuyện
- `speaker profile`
  - các sự thật ổn định về người nói hiện tại
  - hữu ích cho các sở thích, danh tính và ghi chú cụ thể của từng người

Vì lý do đó, `!memory export` chỉ xuất các cấu hình thuộc về `session_key` hiện tại, không phải mọi cấu hình trong toàn bộ thực thể plugin.

### Cách bộ nhớ tình tiết L2 được cô lập

Các bộ nhớ L2 được ghi vào kho lưu trữ vector với siêu dữ liệu cô lập, sau đó được lọc tại thời điểm truy xuất:

- `session`
  - bộ nhớ từ nhóm A không được gọi lại trong nhóm B
  - bộ nhớ từ một cuộc trò chuyện riêng tư không được gọi lại trong một cuộc trò chuyện khác
- `bot`
  - tất cả các phiên dưới cùng một bot dùng chung một không gian bộ nhớ tình tiết
  - hữu ích khi bạn muốn chia sẻ trải nghiệm dài hạn giữa các phiên

Khi có `sender_id`, plugin cũng có thể ưu tiên các bộ nhớ liên quan đến người nói trước khi mở rộng ra phạm vi rộng hơn.

### Tại sao cô lập L1 và L2 không hoàn toàn giống nhau

Đó là sự cố ý:

- L1 hoạt động giống như trạng thái cấu hình ổn định, vì vậy việc lưu trữ chính xác theo phiên / người nói là hợp lý
- L2 hoạt động giống như một cơ sở trải nghiệm có thể truy xuất, vì vậy lọc dựa trên siêu dữ liệu là mô hình có khả năng mở rộng tốt hơn
- điều này giữ cho L1 chính xác và L2 linh hoạt

## Cách sử dụng

1. Cài đặt và bật plugin.
2. Tạo một cơ sở kiến thức bộ nhớ với KnowledgeEngine của plugin này.
3. Cấu hình:
   - `embedding_model_uuid`
   - `isolation`
   - tùy chọn `recency_half_life_days`
   - tùy chọn `auto_recall_top_k`
4. Để agent sử dụng:
   - `remember` cho các sự kiện, kế hoạch và sự thật tình tiết
   - `recall_memory` để tra cứu bộ nhớ chủ động khi truy xuất tự động là không đủ
   - `update_profile` cho các sở thích ổn định và dữ liệu cấu hình
   - `forget` để xóa một bộ nhớ tình tiết cụ thể theo ID
5. Sử dụng `!memory`, `!memory profile`, `!memory search <query>`, `!memory list [page]`, `!memory forget <id>` và `!memory export` để kiểm tra hành vi.

## Chia sẻ ngữ cảnh cho các plugin khác

LongTermMemory ghi một bản tóm tắt ngữ cảnh có cấu trúc vào biến truy vấn `_ltm_context` trong mỗi sự kiện `PromptPreProcessing`. Các plugin khác có thể đọc biến này để đưa ra các quyết định theo chương trình dựa trên bộ nhớ của người dùng, mà không cần nhập hoặc tham chiếu LongTermMemory dưới bất kỳ hình thức nào.

### Khóa biến

`_ltm_context`

### Schema

```python
{
    "speaker": {
        "id": "user_123",           # sender_id, có thể là chuỗi trống
        "name": "Alice",            # sender_name, có thể là chuỗi trống
    },
    "session_profile": {            # luôn hiện diện, các trường có thể trống
        "name": "",
        "traits": ["creative", "analytical"],
        "preferences": ["prefers detailed explanations"],
        "notes": "",
        "updated_at": "2025-03-16T12:00:00Z",
    },
    "speaker_profile": {            # null khi không có sender_id
        "name": "Alice",
        "traits": ["extroverted"],
        "preferences": ["likes humor"],
        "notes": "",
        "updated_at": "2025-03-16T12:00:00Z",
    },
    "episodes": [                   # các bộ nhớ tình tiết L2 được gọi lại tự động, có thể trống
        {"content": "User mentioned a trip to Beijing last week"},
    ],
}
```

### Ví dụ sử dụng

```python
from langbot_plugin.api.definition.components.common.event_listener import EventListener
from langbot_plugin.api.entities import events, context
from langbot_plugin.api.entities.builtin.provider.message import Message


class PersonalityCustomizer(EventListener):
    def __init__(self):
        super().__init__()

        @self.handler(events.PromptPreProcessing)
        async def on_prompt(event_ctx: context.EventContext):
            ltm = await event_ctx.get_query_var("_ltm_context")
            if not ltm:
                # LongTermMemory chưa được cài đặt hoặc không hoạt động — sử dụng mặc định
                return

            profile = ltm.get("speaker_profile") or ltm.get("session_profile") or {}
            traits = profile.get("traits", [])

            if "thích hài hước" in traits:
                style = "Use a humorous and playful tone."
            elif "thích ngắn gọn" in traits:
                style = "Be concise and direct."
            else:
                return

            event_ctx.event.default_prompt.append(
                Message(role="system", content=style)
            )
```

### Ghi chú thiết kế

- Nếu LongTermMemory không được cài đặt, `_ltm_context` sẽ không tồn tại. Các plugin tiêu thụ nên coi `None` là bình thường và quay lại hành vi mặc định.
- Nếu LongTermMemory đang hoạt động nhưng chưa có dữ liệu cấu hình nào được lưu trữ, biến này vẫn tồn tại với các trường trống. Điều này cho phép các plugin tiêu thụ phân biệt giữa "không có plugin bộ nhớ" và "plugin bộ nhớ đang hoạt động, chưa có dữ liệu".
- Cả hai bên chỉ phụ thuộc vào khóa biến và quy ước schema, không phụ thuộc vào mã của nhau. Nếu LongTermMemory được thay thế bằng một plugin bộ nhớ khác ghi vào cùng một khóa với cùng một schema, các plugin tiêu thụ vẫn tiếp tục hoạt động.
- LongTermMemory phải chạy trước các plugin tiêu thụ trong thứ tự điều phối sự kiện. Trong thực tế, điều này phụ thuộc vào thứ tự cài đặt plugin.

## Nhập / Xuất

- **Xuất (cấu hình L1):** Sử dụng `!memory export` để xuất cấu hình phiên và người nói của phạm vi hiện tại dưới dạng JSON. Nó không xuất dữ liệu từ các phiên hoặc phạm vi khác.
- **Nhập (bộ nhớ tình tiết L2):** Tải lên tệp JSON thông qua giao diện người dùng cơ sở kiến thức LangBot để nhập hàng loạt các bộ nhớ tình tiết.
- **Bộ nhớ tình tiết L2 có thể được duyệt** qua `!memory list [page]` và các tình tiết riêng lẻ được xóa qua `!memory forget <id>`. Việc xuất hàng loạt đầy đủ vẫn chưa được thực hiện.

## Các câu hỏi kỹ thuật chính

### Q1. Tại sao chia bộ nhớ thành L1 và L2 thay vì lưu trữ mọi thứ trong cơ sở dữ liệu vector?

Bởi vì các mẫu truy cập là khác nhau:

- L1 chứa các sự thật ổn định và nên được chèn một cách nhất quán
- L2 chứa bộ nhớ dạng sự kiện và nên được truy xuất theo yêu cầu

Việc đưa cả hai vào kho lưu trữ vector sẽ làm cho việc gọi lại cấu hình ổn định kém tin cậy hơn và làm cho các cập nhật bộ nhớ trở nên lộn xộn về mặt ngữ nghĩa.

### Q2. Tại sao L2 được truy xuất thay vì chèn đầy đủ sau mỗi lượt?

Bởi vì L2 tăng dần theo thời gian. Việc chèn đầy đủ sẽ nhanh chóng gây ra:

- làm phình prompt
- quá nhiều nhiễu không liên quan
- bộ nhớ cũ lấn át ngữ cảnh thực sự liên quan

Chiến lược hiện tại là tự động truy xuất một tập hợp con nhỏ liên quan, sau đó để agent sử dụng `recall_memory` nếu nó cần thêm.

### Q3. Bộ nhớ L2 có bị phai nhạt theo thời gian không?

Có.

Xếp hạng L2 không chỉ phụ thuộc vào độ tương tự vector. Nó cũng áp dụng sự suy giảm theo thời gian để các bộ nhớ mới hơn có xu hướng xếp hạng cao hơn các bộ nhớ cũ hơn.

Bản thực hiện hiện tại sử dụng phương pháp kiểu chu kỳ bán rã (half-life):

- khi một bộ nhớ đạt đến `half_life_days`, trọng số thời gian của nó giảm xuống còn khoảng 50%
- bộ nhớ mới hơn được ưu tiên trong xếp hạng
- bộ nhớ cũ hơn không bị xóa tự động; nó chỉ mất lợi thế xếp hạng

Điều này nhằm mục đích ưu tiên ngữ cảnh gần đây, không phải để xóa cứng quá khứ.

### Q4. Các bộ nhớ cũ cuối cùng có biến mất hoàn toàn không?

Không tự động.

Sự suy giảm theo thời gian ảnh hưởng đến xếp hạng, không phải xóa cứng. Các bộ nhớ cũ vẫn có thể được gọi lại nếu chúng vẫn đủ liên quan.

### Q5. Tôi nên chọn giữa cô lập theo `session` hay `bot` như thế nào?

Trong thực tế:

- chọn `session`
  - khi mỗi cuộc trò chuyện nhóm / trò chuyện riêng tư nên giữ bộ nhớ độc lập
  - khi bạn muốn rủi ro rò rỉ chéo phiên thấp hơn
- chọn `bot`
  - khi bot nên chia sẻ trải nghiệm dài hạn giữa các phiên
  - khi việc gọi lại rộng hơn quan trọng hơn việc phân tách nghiêm ngặt

Nếu bạn không chắc chắn, hãy bắt đầu với `session`.

### Q6. Tại sao `!memory export` chỉ xuất phạm vi hiện tại?

Đó là một ranh giới an toàn có tính toán.

Việc cho phép xuất mọi cấu hình L1 trong thực thể plugin sẽ làm cho việc rò rỉ dữ liệu chéo phiên trở nên dễ dàng hơn nhiều. Việc hạn chế xuất trong phạm vi hiện tại tuân theo nguyên tắc tiếp xúc tối thiểu.

### Q7. Điều gì xảy ra nếu runtime không để lộ `_knowledge_base_uuids` trong các biến truy vấn?

Việc chèn bộ nhớ tự động vẫn hoạt động, nhưng plugin không thể loại bỏ KB bộ nhớ của chính nó khỏi quá trình tiền xử lý RAG thông thường.

Điều đó có thể dẫn đến việc gọi lại bộ nhớ trùng lặp:

- một bản sao được chèn bởi chính LongTermMemory
- một bản sao khác được gọi lại lần nữa bởi luồng KB chung của runner

Vì vậy, đây không phải là một thất bại hoàn toàn, nhưng nó có thể lãng phí ngữ cảnh và làm cho prompt ồn ào hơn.

### Q8. Tại sao xuất L2 chưa được hỗ trợ?

SDK hiện cung cấp API `vector_list` để liệt kê phân trang nội dung kho lưu trữ vector. Các bộ nhớ tình tiết L2 có thể được duyệt qua `!memory list [page]` và xóa riêng lẻ qua `!memory forget <episode_id>` hoặc công cụ `forget`.

Việc xuất hàng loạt đầy đủ vẫn chưa được thực hiện, nhưng các khối xây dựng đã sẵn sàng.

### Q9. LongTermMemory và AgenticRAG có bị trùng lặp truy xuất khi cả hai đều được bật không?

Không, sự trùng lặp đó chính là điều mà thiết kế hiện tại tránh được:

- LongTermMemory loại bỏ tiền xử lý RAG thông thường của chính nó
- việc gọi lại L2 tự động được xử lý bởi LongTermMemory
- việc truy xuất sâu hơn có thể thực hiện thông qua AgenticRAG

## Bảng điều khiển Bộ nhớ

Ngoài lệnh `!memory`, plugin còn đi kèm một trang web **Bảng điều khiển Bộ nhớ** (đăng ký như thành phần Page của plugin) để kiểm tra trực quan và bảo trì. Nó giao tiếp với plugin thông qua các endpoint trang bị giới hạn phạm vi và không bao giờ vượt ra ngoài không gian bộ nhớ đang chọn.

Bảng điều khiển gồm một thanh bên phạm vi cùng các bảng tab:

- **Thanh bên không gian bộ nhớ** —— chọn một phạm vi đã biết, hoặc điền `bot_uuid` / `session_name` / `isolation` rồi nhấn **Derive** để tính ra `scope_key` và `user_key` tương ứng. Khu vực **Advanced / Raw** hiển thị các khóa nội bộ.
- **Hồ sơ** —— xem hồ sơ phiên và hồ sơ người nói hiện tại của phạm vi đã chọn.
- **Tình tiết** —— liệt kê (có phân trang) hoặc tìm kiếm ngữ nghĩa các tình tiết L2 của `user_key` hiện tại, lọc theo trạng thái vòng đời; lưu trữ, khôi phục hoặc xóa từng bản ghi tại chỗ. Mỗi thao tác thay đổi đều ghi một mục kiểm toán theo phạm vi, giống hệt lệnh `!memory` tương ứng.
- **Chèn (Injection)** —— tải **ảnh chụp lần chèn bộ nhớ gần nhất** của phạm vi: lượt vừa rồi có chèn gì không, bao nhiêu khối và ký tự, người nói nào, các hồ sơ đã dùng và các tình tiết L2 được tự động truy hồi. Trả lời câu hỏi "bot đã nhớ gì ở lượt trước?" mà không cần lục nhật ký.
- **Kiểm toán** —— duyệt (có phân trang) và xuất nhật ký kiểm toán theo phạm vi.
- **Xuất** —— xuất hồ sơ L1 và tình tiết L2 của phạm vi hiện tại dưới dạng JSON.
- **Chẩn đoán** —— **Run Health Check** chạy cùng một phép dò cô lập metadata như `!memory health` ngay từ giao diện (cấu hình KB, mô hình embedding, và sự cô lập của bộ lọc `user_key` trên search / list / delete), hiển thị dưới dạng thẻ trạng thái đỏ/vàng/xanh. Lưu ý: bảng điều khiển không thể xác minh KB đã được gắn vào một pipeline cụ thể hay chưa; hãy chạy `!memory health` bên trong một pipeline để xác nhận phần đó.

Bảng điều khiển hỗ trợ i18n (`en_US`, `zh_Hans`) và tuân theo giao diện sáng/tối của LangBot máy chủ.

## Các thành phần

- KnowledgeEngine: [memory_engine.py](components/knowledge_engine/memory_engine.py)
- EventListener: [memory_injector.py](components/event_listener/memory_injector.py)
- Công cụ: [remember.py](components/tools/remember.py), [recall_memory.py](components/tools/recall_memory.py), [update_profile.py](components/tools/update_profile.py), [forget.py](components/tools/forget.py)
- Lệnh: [memory.py](components/commands/memory.py)
- Page: [memory_console.py](components/pages/memory_console/memory_console.py), [index.html](components/pages/memory_console/index.html)

## Các khoảng trống hiện tại

README hiện đã bao gồm thiết kế cốt lõi, các quy tắc cô lập, ranh giới xuất và các thành phần chính.

Vẫn đáng để thêm vào sau này:

- cập nhật đồng bộ cho các tài liệu đã địa phương hóa
- các ví dụ nhập JSON cụ thể
- các ví dụ về thực hành tốt nhất cho `remember`, `recall_memory` và `update_profile`

## Nhật ký (Logging)

Plugin hiện phát ra các nhật ký tại các thời điểm quan trọng trong vòng đời bộ nhớ để bạn có thể quan sát cách bộ nhớ dài hạn đang được sử dụng trong thời gian chạy.

Bạn sẽ thấy nhật ký cho:

- khởi tạo plugin và ngữ cảnh bộ nhớ được phân giải
- các cuộc gọi công cụ `remember`, `recall_memory` và `update_profile`
- chèn cấu hình trước khi gọi mô hình
- truy xuất bộ nhớ L2 tự động trong KnowledgeEngine
- các lần ghi vector bộ nhớ tình tiết, tìm kiếm, nhập hàng loạt và xóa

Các thông báo nhật ký điển hình trông như sau:

```text
[LongTermMemory] remember called: query_id=123 params_keys=['content', 'importance', 'tags']
[LongTermMemory] memory injection ready: query_id=123 kb_id=kb-1 scope_key=bot:xxx:group_123 sender_id=u1 block_count=2 prompt_chars=280
[LongTermMemory] engine retrieve called: collection_id=kb-1 top_k=5 session_name=group_123 sender_id=u1 bot_uuid=bot-1 query='user asked about travel plan'
[LongTermMemory] search_episodes completed: collection_id=kb-1 result_count=3 filters={'user_key': 'bot:bot-1:group_123'}
```
