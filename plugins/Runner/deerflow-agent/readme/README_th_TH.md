# DeerFlow Agent

## ภาพรวม

เรียกใช้เอเจนต์ DeerFlow LangGraph เป็น LangBot Runner

## ข้อมูลแพ็กเกจ

- **Runner ID**: `plugin:langbot-team/DeerFlowAgent/default`
- **เวอร์ชัน**: `0.1.2`
- **ที่เก็บโค้ด**: [https://github.com/langbot-app/LangBot/tree/master/plugins/Runner/deerflow-agent](https://github.com/langbot-app/LangBot/tree/master/plugins/Runner/deerflow-agent)

## ความสามารถหลัก

- **เปิดใช้**: `streaming`, `multimodal input`
- **ไม่ได้ประกาศ**: `tool calling`, `knowledge retrieval`, `interrupt`

## การกำหนดค่า

| ฟิลด์ | ชนิด | จำเป็น | ค่าเริ่มต้น |
| --- | --- | --- | --- |
| `api-base` | `string` | ใช่ | `http://127.0.0.1:2026` |
| `api-key` | `secret` | ไม่ | ว่าง |
| `auth-header` | `secret` | ไม่ | ว่าง |
| `assistant-id` | `string` | ใช่ | `lead_agent` |
| `advanced-settings` | `boolean` | ไม่ | false |
| `model-name` | `string` | ไม่ | ว่าง |
| `thinking-enabled` | `boolean` | ไม่ | false |
| `plan-mode` | `boolean` | ไม่ | false |
| `subagent-enabled` | `boolean` | ไม่ | false |
| `max-concurrent-subagents` | `integer` | ไม่ | `3` |
| `timeout` | `integer` | ไม่ | `300` |
| `recursion-limit` | `integer` | ไม่ | `1000` |

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
