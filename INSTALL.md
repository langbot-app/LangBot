# LangBot Installation Guide

LangBot is now available as a Python package on PyPI, making installation incredibly simple!

## Quick Start with uvx (Recommended)

The easiest way to run LangBot is using `uvx`, which automatically downloads and runs the package:

```bash
uvx langbot
```

This will:
- Download the latest version of LangBot
- Install all dependencies automatically
- Start LangBot immediately

## Installation with pip

Alternatively, you can install LangBot globally using pip:

```bash
pip install langbot
```

Then run it:

```bash
langbot
```

## Installing Specific Versions

### Latest Beta Version
```bash
uvx langbot  # Always gets the latest version
```

### Specific Version
```bash
uvx langbot@4.4.1b1
pip install langbot==4.4.1b1
```

## System Requirements

- Python 3.10.1 or higher
- 4GB RAM minimum (8GB recommended)
- Internet connection for downloading models and dependencies

## What's Included

The package includes:
- ✅ LangBot core platform
- ✅ All built-in adapters (Telegram, Discord, QQ, WeChat, etc.)
- ✅ Web-based management interface (pre-built)
- ✅ Plugin system support
- ✅ All templates and resources

## First Run

On first run, LangBot will:
1. Check and install any missing dependencies
2. Generate default configuration files
3. Start the web interface at `http://127.0.0.1:5300`

## Traditional Installation (From Source)

If you prefer to run from source code:

1. Download the release archive from [GitHub Releases](https://github.com/langbot-app/LangBot/releases)
2. Extract the archive
3. Install dependencies: `uv sync`
4. Run: `uv run main.py`

## Troubleshooting

### Permission Errors
If you encounter permission errors, try using a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install langbot
langbot
```

### Port Already in Use
If port 5300 is already in use, LangBot will notify you. You can configure a different port in the configuration file after first run.

## Getting Help

- 📖 Documentation: https://docs.langbot.app
- 💬 Discord: https://discord.gg/langbot
- 🐛 Issues: https://github.com/langbot-app/LangBot/issues

## Development

To contribute to LangBot development, see [CONTRIBUTING.md](CONTRIBUTING.md) and [AGENTS.md](AGENTS.md).
