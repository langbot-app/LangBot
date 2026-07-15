<p align="center">
<a href="https://langbot.app">
<img width="130" src="res/logo-blue.png" alt="LangBot"/>
</a>

<div align="center">

<a href="https://www.producthunt.com/products/langbot/launches/langbot?embed=true&amp;utm_source=badge-featured&amp;utm_medium=badge&amp;utm_campaign=badge-langbot" target="_blank" rel="noopener noreferrer"><img alt="LangBot - Easy-to-use global IM bot platform designed for the LLM era | Product Hunt" width="250" height="54" src="https://api.producthunt.com/widgets/embed-image/v1/featured.svg?post_id=979554&amp;theme=light&amp;t=1782822143403"></a>

<h3>Nền tảng cấp sản xuất để xây dựng bot IM với AI agent.</h3>
<h4>Xây dựng, gỡ lỗi và triển khai bot AI nhanh chóng trên Slack, Discord, Telegram, WeChat và nhiều nền tảng khác.</h4>

[English](README.md) / [简体中文](README_CN.md) / [繁體中文](README_TW.md) / [日本語](README_JP.md) / [Español](README_ES.md) / [Français](README_FR.md) / [한국어](README_KO.md) / [Русский](README_RU.md) / Tiếng Việt

[![Discord](https://img.shields.io/discord/1335141740050649118?logo=discord&labelColor=%20%235462eb&logoColor=%20%23f5f5f5&color=%20%235462eb)](https://discord.gg/wdNEHETs87)
[![Ask DeepWiki](https://deepwiki.com/badge.svg)](https://deepwiki.com/langbot-app/LangBot)
[![GitHub release (latest by date)](https://img.shields.io/github/v/release/langbot-app/LangBot)](https://github.com/langbot-app/LangBot/releases/latest)
<img src="https://img.shields.io/badge/python-3.10 ~ 3.13 -blue.svg" alt="python">
[![GitHub stars](https://img.shields.io/github/stars/langbot-app/LangBot?style=social)](https://github.com/langbot-app/LangBot/stargazers)

<a href="https://langbot.app">Trang chủ</a> ｜
<a href="https://link.langbot.app/en/docs/features">Tính năng</a> ｜
<a href="https://link.langbot.app/en/docs/guide">Tài liệu</a> ｜
<a href="https://link.langbot.app/en/docs/api">API</a> ｜
<a href="https://space.langbot.app">Chợ Plugin</a> ｜
<a href="https://langbot.featurebase.app/roadmap">Lộ trình</a>

</div>

</p>

---

## LangBot là gì?

LangBot là một **nền tảng mã nguồn mở, cấp sản xuất** để xây dựng bot nhắn tin tức thời được hỗ trợ bởi AI. Nó kết nối các Mô hình Ngôn ngữ Lớn (LLM) với bất kỳ nền tảng chat nào, cho phép bạn tạo các agent thông minh có thể trò chuyện, thực hiện tác vụ và tích hợp với quy trình làm việc hiện có của bạn.

<p align="center">
<img src="res/dashboard-overview.png" alt="Bảng điều khiển quản lý web LangBot — giám sát thời gian thực khối lượng tin nhắn, lệnh gọi mô hình, tỷ lệ thành công và phiên hoạt động" width="720"/>
</p>

### Khả năng chính

- **Hội thoại AI & Agent** — Đối thoại nhiều lượt, gọi công cụ, hỗ trợ đa phương thức, đầu ra streaming. RAG (cơ sở kiến thức) tích hợp sẵn với tích hợp sâu vào [Dify](https://dify.ai), [Coze](https://coze.com), [n8n](https://n8n.io), [Langflow](https://langflow.org), [Deerflow](https://deerflow.tech), [Weknora](https://weknora.weixin.qq.com).
- **Hỗ trợ đa nền tảng IM** — Một mã nguồn cho Discord, Telegram, Slack, LINE, QQ, WeChat, WeCom, Lark, DingTalk, KOOK.
- **Sẵn sàng cho sản xuất** — Kiểm soát truy cập, giới hạn tốc độ, lọc từ nhạy cảm, giám sát toàn diện và xử lý ngoại lệ. Được doanh nghiệp tin dùng.
- **Hệ sinh thái Plugin** — Hàng trăm plugin, kiến trúc hướng sự kiện, mở rộng thành phần, và hỗ trợ [giao thức MCP](https://modelcontextprotocol.io/).
- **Bảng quản lý Web** — Cấu hình, quản lý và giám sát bot thông qua giao diện trình duyệt trực quan. Không cần chỉnh sửa YAML.
- **Kiến trúc đa Pipeline** — Các bot khác nhau cho các kịch bản khác nhau, với giám sát toàn diện và xử lý ngoại lệ.

[→ Tìm hiểu thêm về tất cả tính năng](https://link.langbot.app/en/docs/features)

📍 Hướng dẫn thực hành: [triển khai bot AI đa nền tảng trong 5 phút](https://langbot.app/en/blog/deploy-ai-bot-in-5-minutes/), [kết nối DeepSeek với WeChat, Discord và Telegram](https://langbot.app/en/blog/connect-deepseek-to-wechat/), [chạy Dify Agent trên Discord, Telegram và Slack](https://langbot.app/en/blog/dify-agent-discord-telegram-slack/) và [xây dựng chatbot với n8n](https://langbot.app/en/blog/n8n-multi-platform-ai-chatbot/).

---

## 😎 Cập nhật Mới nhất

Nhấp vào các nút Star và Watch ở góc trên bên phải của kho lưu trữ để nhận các bản cập nhật mới nhất.

![star gif](https://langbot.app/star.gif)

## Bắt đầu nhanh

### ☁️ LangBot Cloud (Khuyên dùng)

**[LangBot Cloud](https://space.langbot.app/cloud)** — Không cần triển khai, sẵn sàng sử dụng.

### Khởi chạy một dòng

```bash
uvx langbot
```

> Yêu cầu [uv](https://docs.astral.sh/uv/getting-started/installation/). Truy cập http://localhost:5300 — xong.

### Docker Compose

```bash
git clone https://github.com/langbot-app/LangBot
cd LangBot/docker
docker compose --profile all up -d
```

### Triển khai đám mây một cú nhấp

[![Deploy on Zeabur](https://zeabur.com/button.svg)](https://zeabur.com/en-US/templates/ZKTBDH)
[![Deploy on Railway](https://railway.com/button.svg)](https://railway.app/template/yRrAyL?referralCode=vogKPF)

**Thêm tùy chọn:** [Docker](https://link.langbot.app/en/docs/docker) · [Thủ công](https://link.langbot.app/en/docs/manual-deploy) · [BTPanel](https://link.langbot.app/en/docs/bt-panel) · [Kubernetes](https://docs.langbot.app/en/deploy/langbot/kubernetes)

---

## Demo trực tuyến

**Thử ngay:** https://demo.langbot.dev/
- Email: `demo@langbot.app`
- Mật khẩu: `langbot123456`

*Lưu ý: Môi trường demo công khai. Không nhập thông tin nhạy cảm.*

---

## Nền tảng được hỗ trợ

| Nền tảng | Trạng thái | Ghi chú |
|----------|--------|-------|
| Discord | ✅ | Chính thức |
| Telegram | ✅ | Chính thức |
| Slack | ✅ | Chính thức |
| LINE | ✅ | Chính thức |
| QQ | ✅ | Cá nhân & API chính thức (Kênh, DM, Nhóm) |
| WeCom | ✅ | WeChat doanh nghiệp, CS bên ngoài, AI Bot |
| WeChat | ✅ | Cá nhân & Tài khoản công khai |
| Lark | ✅ | Chính thức |
| DingTalk | ✅ | Chính thức |
| KOOK | ✅ | Chính thức |
| Satori | ✅ |  |
| Email | ✅ | Matrix, Satori |
| Matrix | ✅ | Hỗ trợ nhiều nền tảng qua bridge như Signal, WhatsApp, Messenger, iMessage, Mattermost, Google Chat, IRC, XMPP, Zulip và hơn thế nữa |

---

## LLM và tích hợp được hỗ trợ

| Nhà cung cấp | Loại | Trạng thái |
|----------|------|--------|
| [OpenAI](https://platform.openai.com/) | LLM | ✅ |
| [Anthropic](https://www.anthropic.com/) | LLM | ✅ |
| [DeepSeek](https://www.deepseek.com/) | LLM | ✅ |
| [Google Gemini](https://aistudio.google.com/prompts/new_chat) | LLM | ✅ |
| [xAI](https://x.ai/) | LLM | ✅ |
| [Moonshot](https://www.moonshot.cn/) | LLM | ✅ |
| [Zhipu AI](https://open.bigmodel.cn/) | LLM | ✅ |
| [Ollama](https://ollama.com/) | LLM cục bộ | ✅ |
| [LM Studio](https://lmstudio.ai/) | LLM cục bộ | ✅ |
| [Dify](https://dify.ai) | LLMOps | ✅ |
| [MCP](https://modelcontextprotocol.io/) | Giao thức | ✅ |
| [SiliconFlow](https://siliconflow.cn/) | Cổng | ✅ |
| [Aliyun Bailian](https://bailian.console.aliyun.com/) | Cổng | ✅ |
| [Volc Engine Ark](https://console.volcengine.com/ark/region:ark+cn-beijing/model?vendor=Bytedance&view=LIST_VIEW) | Cổng | ✅ |
| [ModelScope](https://modelscope.cn/docs/model-service/API-Inference/intro) | Cổng | ✅ |
| [GiteeAI](https://ai.gitee.com/) | Cổng | ✅ |
| [CompShare](https://www.compshare.cn/?ytag=GPU_YY-gh_langbot) | Nền tảng GPU | ✅ |
| [PPIO](https://ppinfra.com/user/register?invited_by=QJKFYD&utm_source=github_langbot) | Nền tảng GPU | ✅ |
| [ShengSuanYun](https://www.shengsuanyun.com/?from=CH_KYIPP758) | Nền tảng GPU | ✅ |
| [接口 AI](https://jiekou.ai/) | Cổng | ✅ |
| [302.AI](https://share.302ai.cn/SuTG99) | Cổng | ✅ |
| [Qiniu](https://www.qiniu.com/ai/agent) | Cổng | ✅ |

[→ Xem tất cả tích hợp](https://link.langbot.app/en/docs/features)

---

## Tại sao chọn LangBot?

| Trường hợp sử dụng | LangBot giúp như thế nào |
|----------|-------------------|
| **Hỗ trợ khách hàng** | Triển khai agent AI trên Slack/Discord/Telegram để trả lời câu hỏi bằng cơ sở kiến thức của bạn |
| **Công cụ nội bộ** | Kết nối quy trình n8n/Dify với WeCom/DingTalk để tự động hóa quy trình kinh doanh |
| **Quản lý cộng đồng** | Quản lý nhóm QQ/Discord với tính năng lọc nội dung và tương tác được hỗ trợ bởi AI |
| **Đa nền tảng** | Một bot, tất cả nền tảng. Quản lý từ một bảng điều khiển duy nhất |

---

## Được xây dựng cho AI Agent 🤖

LangBot **thân thiện với agent ngay từ thiết kế** —— các coding agent của bạn (Claude Code, Codex, Copilot, Cursor, …) có thể vận hành, mở rộng và triển khai LangBot với sự hỗ trợ hạng nhất:

- **MCP Server** —— LangBot cung cấp endpoint [Model Context Protocol](https://modelcontextprotocol.io/) tích hợp tại `/mcp`, phản chiếu HTTP API để agent quản lý bot, pipeline, plugin và model theo cách lập trình. Xác thực bằng cùng một API key (đặt key toàn cục trong `config.yaml` hoặc dùng key theo người dùng) —— không cần luồng đăng nhập. Cấu hình tại tab **API & MCP** trong bảng điều khiển Web.
- **Skills trong repo** —— Thư mục [`skills/`](skills/) là **nguồn sự thật duy nhất** để làm việc với LangBot: phát triển plugin, phát triển core, kiểm thử end-to-end, triển khai và vận hành MCP Server của LangBot / LangBot Space. Trỏ agent của bạn vào thư mục này và nó sẽ biết cách xây dựng.
- **AGENTS.md** —— Mỗi repo đều có [`AGENTS.md`](AGENTS.md) (liên kết tượng trưng tới `CLAUDE.md`) mô tả kiến trúc, quy ước và quy tắc rằng thay đổi API phải giữ MCP Server và skills đồng bộ.
- **`llms.txt`** —— Ngữ cảnh dự án có thể đọc bằng máy dành cho LLM được công bố trên website.

> **Cloud / Marketplace:** [LangBot Space](https://space.langbot.app) cũng cung cấp MCP Server để agent tìm kiếm và kiểm tra marketplace plugin / MCP / skill, xác thực bằng Personal Access Token.

---

## Cộng đồng

[![Discord](https://img.shields.io/discord/1335141740050649118?logo=discord&label=Discord)](https://discord.gg/wdNEHETs87)

- [Cộng đồng Discord](https://discord.gg/wdNEHETs87)

---

## Người đóng góp

Cảm ơn tất cả [người đóng góp](https://github.com/langbot-app/LangBot/graphs/contributors) đã giúp LangBot trở nên tốt hơn:

<a href="https://github.com/langbot-app/LangBot/graphs/contributors">
  <img src="https://contrib.rocks/image?repo=langbot-app/LangBot" />
</a>
