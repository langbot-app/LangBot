# Dify Agent

`remove-think` (บูลีน ค่าเริ่มต้น `false`) ซ่อนเนื้อหาการคิดในแท็ก think รวมถึงส่วนที่ยังไม่จบ และ `app-type` รองรับ `chatflow` ด้วย

## ภาพรวม

เรียกใช้แอป Dify เป็น LangBot Runner

## ข้อมูลแพ็กเกจ

- **Runner ID**: `plugin:langbot-team/DifyAgent/default`
- **เวอร์ชัน**: `0.1.2`
- **ที่เก็บโค้ด**: [https://github.com/langbot-app/LangBot/tree/master/plugins/Runner/dify-agent](https://github.com/langbot-app/LangBot/tree/master/plugins/Runner/dify-agent)

## ความสามารถหลัก

- **เปิดใช้**: `streaming`, `tool calling`, `knowledge retrieval`, `multimodal input`
- **ไม่ได้ประกาศ**: `interrupt`

## การกำหนดค่า

| ฟิลด์ | ชนิด | จำเป็น | ค่าเริ่มต้น |
| --- | --- | --- | --- |
| `base-url` | `string` | ใช่ | `https://api.dify.ai/v1` |
| `advanced-settings` | `boolean` | ไม่ | false |
| `base-prompt` | `text` | ใช่ | `When the file content is readable, please read the content of this file. When the file is an image, describe the content of this image.` |
| `app-type` | `select` | ใช่ | `chat` |
| `api-key` | `secret` | ใช่ | ว่าง |
| `timeout` | `integer` | ไม่ | `30` |
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

### Provider identity compatibility (`user-id-source`)

Per-pipeline Runner parameter, not plugin-global configuration. `sender` remains the default.
A `sender` run whose Host actor is missing or empty is refused before any upstream request, instead of minting a per-run provider user; select `legacy-session` explicitly when a conversation-scoped provider user is intended.
Explicit `legacy-session` preserves native provider identity using trusted Host run context only;
missing identity fails before any upstream request, never falls back to the sender or business params.
`legacy-session` uses `conversation.launcher_type` (`group`/`person`) plus `_` plus the exact `conversation.launcher_id`. Host must project the native Query.session launcher into those fields, including interaction/resume runs. Older Hosts that leave these fields empty must be upgraded.
Provider conversation/session persistence remains Runner-owned. Configuration migration does not import old conversation IDs, threads, transcripts, pending forms or files; finish/cancel pending work or perform a separately authorized state migration. Changing identity on an existing stored provider conversation requires an explicit reset/migration decision.
