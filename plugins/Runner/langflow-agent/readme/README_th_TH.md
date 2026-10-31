# Langflow Agent

## ภาพรวม

เรียกใช้โฟลว์ Langflow เป็น LangBot Runner

## ข้อมูลแพ็กเกจ

- **Runner ID**: `plugin:langbot-team/LangflowAgent/default`
- **เวอร์ชัน**: `0.1.2`
- **ที่เก็บโค้ด**: [https://github.com/langbot-app/LangBot/tree/master/plugins/Runner/langflow-agent](https://github.com/langbot-app/LangBot/tree/master/plugins/Runner/langflow-agent)

## ความสามารถหลัก

- **เปิดใช้**: `streaming`, `tool calling`, `knowledge retrieval`
- **ไม่ได้ประกาศ**: `multimodal input`, `interrupt`

## การกำหนดค่า

| ฟิลด์ | ชนิด | จำเป็น | ค่าเริ่มต้น |
| --- | --- | --- | --- |
| `base-url` | `string` | ใช่ | `http://localhost:7860` |
| `api-key` | `secret` | ใช่ | ว่าง |
| `flow-id` | `string` | ใช่ | ว่าง |
| `advanced-settings` | `boolean` | ไม่ | false |
| `input-type` | `string` | ไม่ | `chat` |
| `output-type` | `string` | ไม่ | `chat` |
| `tweaks` | `json` | ไม่ | `{}` |
| `langbot-assets-enabled` | `boolean` | ไม่ | false |
| `langbot-assets-gateway-host` | `string` | ไม่ | `0.0.0.0` |
| `langbot-assets-gateway-port` | `integer` | ไม่ | `8765` |
| `langbot-assets-gateway-request-timeout` | `integer` | ไม่ | `60` |
| `langbot-assets-token-ttl` | `integer` | ไม่ | `3600` |
| `langbot-assets-input-name` | `string` | ไม่ | `langbot_asset_run_token` |

## สิทธิ์ของ Host

- **`tools`**: `detail`, `call`
- **`knowledge_bases`**: `retrieve`
- **`history`**: `page`
- **`storage`**: `plugin`

## การติดตั้งและใช้งาน

1. ติดตั้งปลั๊กอินจากตลาดปลั๊กอิน LangBot
2. เลือก Runner ID ด้านล่างในตัวเลือก Runner ของ Pipeline
3. กรอกข้อมูลการเชื่อมต่อตามตาราง และเก็บค่าลับด้วยฟิลด์ secret ในหน้าจัดการ

## ความปลอดภัยและข้อจำกัด

- Runner ใช้ได้เฉพาะทรัพยากร LangBot ที่ได้รับอนุญาตสำหรับการทำงานปัจจุบัน
- ความพร้อมใช้งาน ความสามารถของโมเดล และขีดจำกัดอัตราขึ้นอยู่กับบริการภายนอก
- ดูพฤติกรรมขั้นสูงและข้อจำกัดเฉพาะผลิตภัณฑ์ใน README ภาษาจีนที่รากหรือ README_en_US.md ภาษาอังกฤษ
