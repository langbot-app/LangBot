# AutoTranslate

Automatically detect foreign language messages in group chats and translate them using LLM.

## Features

- 🌐 Auto-detects message language — no manual commands needed
- 🤖 Uses LLM for natural, high-quality translations
- ⚙️ Configurable target language (Chinese, English, Japanese, Korean, French, Spanish)
- 📏 Skips short messages, emoticons, and URLs
- 🔇 Only translates when needed — same-language messages are ignored
- 👥 Group-only by default, optional private chat support

## How It Works

1. When a message is received in a group chat, the plugin sends the text to an LLM
2. The LLM detects if the message is in a different language than the configured target
3. If translation is needed, the plugin replies with the translated text prefixed with 🌐
4. Messages already in the target language are silently ignored

## Configuration

| Option | Description | Default |
|---|---|---|
| Target Language | Language to translate into | Chinese (Simplified) |
| LLM Model | Model to use for translation | First available |
| Minimum Text Length | Skip messages shorter than this | 4 characters |
| Enable in Private Chat | Also translate private messages | Off |
