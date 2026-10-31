# Codex Agent

## ภาพรวม

เรียกใช้ Codex CLI เป็น LangBot Runner

## ข้อมูลแพ็กเกจ

- **Runner ID**: `plugin:langbot-team/CodexAgent/default`
- **เวอร์ชัน**: `0.1.9`
- **ที่เก็บโค้ด**: [https://github.com/langbot-app/LangBot/tree/master/plugins/Runner/codex-agent](https://github.com/langbot-app/LangBot/tree/master/plugins/Runner/codex-agent)

## ความสามารถหลัก

- **เปิดใช้**: `streaming`, `tool calling`, `knowledge retrieval`, `steering`
- **ไม่ได้ประกาศ**: `multimodal input`, `interrupt`

## การกำหนดค่า

| ฟิลด์ | ชนิด | จำเป็น | ค่าเริ่มต้น |
| --- | --- | --- | --- |
| `daemon-enabled` | `boolean` | ไม่ | false |
| `daemon-host` | `string` | ไม่ | `127.0.0.1` |
| `daemon-port` | `integer` | ไม่ | `8768` |
| `daemon-token` | `secret` | ไม่ | ว่าง |
| `location` | `select` | ใช่ | `local` |
| `workspace` | `string` | ไม่ | ว่าง |
| `advanced-settings` | `boolean` | ไม่ | false |
| `command` | `string` | ไม่ | `codex` |
| `args-json` | `string` | ไม่ | `[]` |
| `env-json` | `string` | ไม่ | `{}` |
| `ssh-target` | `string` | ไม่ | ว่าง |
| `ssh-port` | `integer` | ไม่ | `22` |
| `daemon-id` | `string` | ไม่ | ว่าง |
| `timeout` | `integer` | ไม่ | `300` |
| `streaming` | `boolean` | ไม่ | true |
| `reuse-session` | `boolean` | ไม่ | true |
| `approval-policy` | `select` | ไม่ | `never` |
| `sandbox-mode` | `select` | ไม่ | `danger-full-access` |
| `knowledge-bases` | `knowledge-base-multi-selector` | ไม่ | `[]` |
| `langbot-assets-enabled` | `boolean` | ไม่ | true |
| `mcp-bridge-transport` | `select` | ไม่ | `auto` |
| `mcp-servers-json` | `string` | ไม่ | `[]` |

## สิทธิ์ของ Host

- **`tools`**: `detail`, `call`
- **`knowledge_bases`**: `retrieve`
- **`history`**: `page`

## การติดตั้งและใช้งาน

1. ติดตั้งปลั๊กอินจากตลาดปลั๊กอิน LangBot
2. เลือก Runner ID ด้านล่างในตัวเลือก Runner ของ Pipeline
3. กรอกข้อมูลการเชื่อมต่อตามตาราง และเก็บค่าลับด้วยฟิลด์ secret ในหน้าจัดการ

## ความปลอดภัยและข้อจำกัด

- การกำหนดค่าเริ่มต้นเปิด Codex ด้วย `approvalPolicy=never` และ `sandbox=danger-full-access` และจะไม่รอการอนุมัติแบบโต้ตอบ โปรดใช้เฉพาะกับพื้นที่ทำงานที่เชื่อถือได้และบัญชีระบบปฏิบัติการที่จำกัดสิทธิ์
- Runner ใช้ได้เฉพาะทรัพยากร LangBot ที่ได้รับอนุญาตสำหรับการทำงานปัจจุบัน
- ความพร้อมใช้งาน ความสามารถของโมเดล และขีดจำกัดอัตราขึ้นอยู่กับบริการภายนอก
- ดูพฤติกรรมขั้นสูงและข้อจำกัดเฉพาะผลิตภัณฑ์ใน README ภาษาจีนที่รากหรือ README_en_US.md ภาษาอังกฤษ


> Shared runtime / daemon upgrade: [required setup and safety contract](../README.md#shared-worker-candidate--daemon-upgrade). Shared 模式必须配置独立强 token 和端口；默认本地工作目录为 `/data/workspace`。请同时升级 daemon.py 与完整 pkg 目录；旧客户端不兼容。
