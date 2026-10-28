# เอเจนต์ในตัว

## ภาพรวม

เอเจนต์ในตัวที่รองรับโมเดลสำรอง การเรียกใช้เครื่องมือ และการค้นคืนความรู้

## ข้อมูลแพ็กเกจ

- **Runner ID**: `plugin:langbot-team/LocalAgent/default`
- **เวอร์ชัน**: `0.1.0`
- **ที่เก็บโค้ด**: [https://github.com/langbot-app/LangBot/tree/master/plugins/Runner/LocalAgent](https://github.com/langbot-app/LangBot/tree/master/plugins/Runner/LocalAgent)

## ความสามารถหลัก

- **เปิดใช้**: `streaming`, `tool calling`, `knowledge retrieval`, `multimodal input`, `skill authoring`, `interrupt`, `steering`
- **ไม่ได้ประกาศ**: ว่าง

## การกำหนดค่า

| ฟิลด์ | ชนิด | จำเป็น | ค่าเริ่มต้น |
| --- | --- | --- | --- |
| `model` | `model-fallback-selector` | ใช่ | `{fallbacks: [], primary: '', reasoning: {}}` |
| `timeout` | `integer` | ไม่ | `300` |
| `prompt` | `prompt-editor` | ใช่ | `[{content: You are a helpful assistant., role: system}]` |
| `remove-think` | `boolean` | ไม่ | false |
| `knowledge-bases` | `knowledge-base-multi-selector` | ไม่ | `[]` |
| `advanced-settings` | `boolean` | ไม่ | `false` |
| `date-grounding` | `boolean` | ไม่ | `true` |
| `retrieval-top-k` | `integer` | ไม่ | `5` |
| `rerank-model` | `rerank-model-selector` | ไม่ | ว่าง |
| `rerank-top-k` | `integer` | ไม่ | `5` |
| `max-tool-iterations` | `integer` | ไม่ | `100` |
| `tool-execution-mode` | `select` | ไม่ | `parallel` |
| `max-tool-result-chars` | `integer` | ไม่ | `20000` |
| `context-history-fetch-limit` | `integer` | ไม่ | `50` |
| `context-window-tokens` | `integer` | ไม่ | `200000` |
| `context-reserve-tokens` | `integer` | ไม่ | `16384` |
| `context-keep-recent-tokens` | `integer` | ไม่ | `20000` |
| `context-summary-tokens` | `integer` | ไม่ | `8000` |

## สิทธิ์ของ Host

- **`models`**: `count_tokens`, `invoke`, `stream`, `rerank`
- **`tools`**: `detail`, `call`
- **`knowledge_bases`**: `list`, `retrieve`
- **`history`**: `page`

## การติดตั้งและใช้งาน

1. ติดตั้งปลั๊กอินจากตลาดปลั๊กอิน LangBot
2. เลือก Runner ID ด้านล่างในตัวเลือก Runner ของ Pipeline
3. กรอกข้อมูลการเชื่อมต่อตามตาราง และเก็บค่าลับด้วยฟิลด์ secret ในหน้าจัดการ

## ความปลอดภัยและข้อจำกัด

- Runner ใช้ได้เฉพาะทรัพยากร LangBot ที่ได้รับอนุญาตสำหรับการทำงานปัจจุบัน
- ความพร้อมใช้งาน ความสามารถของโมเดล และขีดจำกัดอัตราขึ้นอยู่กับบริการภายนอก
- ดูพฤติกรรมขั้นสูงและข้อจำกัดเฉพาะผลิตภัณฑ์ใน README ภาษาจีนที่รากหรือ README_en_US.md ภาษาอังกฤษ

## Box

`box-enabled` ใช้เปิด sandbox ส่วน `box-session-id-template` มีค่าเริ่มต้นเป็น `{launcher_type}_{launcher_id}` เพื่อใช้ซ้ำตามแชต หรือใช้ `{global}` เพื่อใช้ร่วมกันในพื้นที่ทำงาน รองรับ `{sender_id}`, `{bot_id}`, `{run_id}` และตัวแปรคำขอ Runner จะเลือก Box นำเข้าไฟล์แนบ และส่งออกไฟล์ใน outbox ของการทำงานครั้งนี้เมื่อสำเร็จ
