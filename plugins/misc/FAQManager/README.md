# FAQ Manager

Manage FAQ entries through a visual page in the LangBot WebUI, and let the LLM search them during conversations.

## Features

- **Page component**: A full CRUD interface for managing question-answer pairs, accessible from the "Plugin Pages" section in the sidebar.
- **Tool component**: `search_faq` — allows the LLM to search the FAQ database by keyword and return matching entries to the user.
- **Persistent storage**: FAQ entries are stored via plugin storage and survive restarts.
- **i18n**: The management page supports English, Simplified Chinese, and Japanese.
- **Dark mode**: The page automatically adapts to the LangBot theme.

## Components

| Component | Type | Description |
|-----------|------|-------------|
| `components/pages/manager/` | Page | FAQ management UI (add, edit, delete, search) |
| `components/tools/search_faq.py` | Tool | Keyword search over FAQ entries, callable by LLM |
| `components/event_listener/default.py` | EventListener | Default event listener (placeholder) |

## Usage

1. Install the plugin in LangBot.
2. Open the **Plugin Pages** section in the sidebar and select **FAQ Manager**.
3. Add question-answer pairs through the page.
4. When users ask questions in a conversation, the LLM can use the `search_faq` tool to look up matching FAQ entries and respond accordingly.

Entries are kept per installation, so the plugin can be placed on a shared worker: see
[SHARED_RUNTIME.md](SHARED_RUNTIME.md).
