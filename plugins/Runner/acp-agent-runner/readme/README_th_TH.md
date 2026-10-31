# ACP Runner

## ภาพรวม

เรียกใช้เอเจนต์เขียนโค้ดที่รองรับ Agent Client Protocol เป็น LangBot Runner

## ข้อมูลแพ็กเกจ

- **Runner ID**: `plugin:langbot-team/ACPAgentRunner/default`
- **เวอร์ชัน**: `0.1.4`
- **ที่เก็บโค้ด**: [https://github.com/langbot-app/LangBot/tree/master/plugins/Runner/acp-agent-runner](https://github.com/langbot-app/LangBot/tree/master/plugins/Runner/acp-agent-runner)

## ความสามารถหลัก

- **เปิดใช้**: `streaming`, `tool calling`, `knowledge retrieval`, `multimodal input`, `steering`
- **ไม่ได้ประกาศ**: `interrupt`

## การกำหนดค่า

| ฟิลด์ | ชนิด | จำเป็น | ค่าเริ่มต้น |
| --- | --- | --- | --- |
| `daemon-enabled` | `boolean` | ไม่ | false |
| `daemon-host` | `string` | ไม่ | `127.0.0.1` |
| `daemon-port` | `integer` | ไม่ | `8766` |
| `daemon-token` | `secret` | ไม่ | ว่าง |
| `provider` | `select` | ใช่ | `claude-code` |
| `location` | `select` | ใช่ | `local` |
| `workspace` | `string` | ไม่ | ว่าง |
| `advanced-settings` | `boolean` | ไม่ | false |
| `ssh-target` | `string` | ไม่ | ว่าง |
| `daemon-id` | `string` | ไม่ | ว่าง |
| `daemon-connect-timeout` | `integer` | ไม่ | `30` |
| `ssh-port` | `integer` | ไม่ | `22` |
| `ssh-identity-file` | `string` | ไม่ | ว่าง |
| `acp-command` | `string` | ไม่ | ว่าง |
| `knowledge-bases` | `knowledge-base-multi-selector` | ไม่ | `[]` |
| `langbot-assets-enabled` | `boolean` | ไม่ | true |
| `langbot-assets-mode` | `select` | ไม่ | `auto` |
| `langbot-assets-gateway-host` | `string` | ไม่ | `127.0.0.1` |
| `langbot-assets-gateway-port` | `integer` | ไม่ | `0` |
| `langbot-assets-gateway-public-url` | `string` | ไม่ | ว่าง |
| `langbot-assets-token-ttl` | `integer` | ไม่ | `3600` |
| `timeout` | `integer` | ไม่ | `300` |
| `reuse-session` | `boolean` | ไม่ | true |
| `env-json` | `text` | ไม่ | ว่าง |
| `ssh-connect-timeout` | `integer` | ไม่ | `10` |
| `ssh-extra-options` | `string` | ไม่ | ว่าง |
| `startup-timeout` | `integer` | ไม่ | `30` |
| `initialize-timeout` | `integer` | ไม่ | `120` |
| `create-session-if-missing` | `boolean` | ไม่ | true |
| `streaming` | `boolean` | ไม่ | true |
| `append-run-scope-prompt` | `boolean` | ไม่ | true |
| `mcp-servers-json` | `text` | ไม่ | ว่าง |

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


> Shared runtime / daemon upgrade: [required setup and safety contract](../README.md#shared-worker-candidate--daemon-upgrade). Shared 模式必须配置独立强 token 和端口；默认本地工作目录为 `/data/workspace`。请同时升级 daemon.py 与完整 pkg 目录；旧客户端不兼容。
