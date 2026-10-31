# WeKnora Agent

`agent-id` เป็นตัวเลือกในทั้งสองโหมด หากไม่กำหนด `chat` ใช้ `builtin-quick-answer` และ `agent` ใช้ `builtin-smart-reasoning` ค่าว่างที่ระบุชัดเจนจะไม่ส่ง ID และจะไม่แทนที่ ID ที่บันทึกไว้ `knowledge-base-ids` คือ ID ระยะไกลของ WeKnora สำหรับทั้งสองโหมด ไม่ใช่ UUID ของ LangBot

## ภาพรวม

เรียกใช้เอเจนต์ WeKnora หรือแอปแชตฐานความรู้เป็น LangBot Runner

## ข้อมูลแพ็กเกจ

- **Runner ID**: `plugin:langbot-team/WeKnoraAgent/default`
- **เวอร์ชัน**: `0.1.2`
- **ที่เก็บโค้ด**: [https://github.com/langbot-app/LangBot/tree/master/plugins/Runner/weknora-agent](https://github.com/langbot-app/LangBot/tree/master/plugins/Runner/weknora-agent)

## ความสามารถหลัก

- **เปิดใช้**: `streaming`
- **ไม่ได้ประกาศ**: `tool calling`, `knowledge retrieval`, `multimodal input`, `interrupt`

## การกำหนดค่า

| ฟิลด์ | ชนิด | จำเป็น | ค่าเริ่มต้น |
| --- | --- | --- | --- |
| `base-url` | `string` | ใช่ | `http://localhost:8080/api/v1` |
| `api-key` | `secret` | ใช่ | ว่าง |
| `app-type` | `select` | ใช่ | `agent` |
| `agent-id` | `string` | ไม่ | `chat`: `builtin-quick-answer`; `agent`: `builtin-smart-reasoning` |
| `knowledge-base-ids` | `array[string]` | ไม่ | `[]` |
| `web-search-enabled` | `boolean` | ไม่ | false |
| `advanced-settings` | `boolean` | ไม่ | false |
| `timeout` | `integer` | ไม่ | `120` |
| `base-prompt` | `string` | ไม่ | `请回答用户的问题。` |

## สิทธิ์ของ Host

- **`storage`**: `plugin`

## การติดตั้งและใช้งาน

1. ติดตั้งปลั๊กอินจากตลาดปลั๊กอิน LangBot
2. เลือก Runner ID ด้านล่างในตัวเลือก Runner ของ Pipeline
3. กรอกข้อมูลการเชื่อมต่อตามตาราง และเก็บค่าลับด้วยฟิลด์ secret ในหน้าจัดการ

## ความปลอดภัยและข้อจำกัด

- Runner ใช้ได้เฉพาะทรัพยากร LangBot ที่ได้รับอนุญาตสำหรับการทำงานปัจจุบัน
- ความพร้อมใช้งาน ความสามารถของโมเดล และขีดจำกัดอัตราขึ้นอยู่กับบริการภายนอก
- ดูพฤติกรรมขั้นสูงและข้อจำกัดเฉพาะผลิตภัณฑ์ใน README ภาษาจีนที่รากหรือ README_en_US.md ภาษาอังกฤษ
