# LangBot PyPI Package Installation

## Quick Start with uvx

The easiest way to run LangBot is using `uvx` (recommended for quick testing):

```bash
uvx langbot
```

This will automatically download and run the latest version of LangBot.

## Install with pip/uv

You can also install LangBot as a regular Python package:

```bash
# Using pip
pip install langbot

# Using uv
uv pip install langbot
```

Then run it:

```bash
langbot
```

Or using Python module syntax:

```bash
python -m langbot
```

## Installation with Frontend

When published to PyPI, the LangBot package includes the pre-built frontend files. You don't need to build the frontend separately.

## Data Directory

When running LangBot as a package, it will create a `data/` directory in your current working directory to store configuration, logs, and other runtime data. You can run LangBot from any directory, and it will set up its data directory there.

## Command Line Options

LangBot supports the following command line options:

- `--standalone-runtime`: Use standalone plugin runtime
- `--debug`: Enable debug mode

Example:

```bash
langbot --debug
```

## Comparison with Other Installation Methods

### PyPI Package (uvx/pip)
- **Pros**: Easy to install and update, no need to clone repository or build frontend
- **Cons**: Less flexible for development/customization

### Docker
- **Pros**: Isolated environment, easy deployment
- **Cons**: Requires Docker

### Manual Source Installation
- **Pros**: Full control, easy to customize and develop
- **Cons**: Requires building frontend, managing dependencies manually

## Development

If you want to contribute or customize LangBot, you should still use the manual installation method by cloning the repository:

```bash
git clone https://github.com/langbot-app/LangBot
cd LangBot
uv sync
cd web
npm install
npm run build
cd ..
uv run main.py
```

## Updating

To update to the latest version:

```bash
# With pip
pip install --upgrade langbot

# With uv
uv pip install --upgrade langbot

# With uvx (automatically uses latest)
uvx langbot
```

## System Requirements

- Python 3.10.1 or higher
- Operating System: Linux, macOS, or Windows

## Differences from Source Installation

When running LangBot from the PyPI package (via uvx or pip), there are a few behavioral differences compared to running from source:

1. **Version Check**: The package version does not prompt for user input when the Python version is incompatible. It simply prints an error message and exits. This makes it compatible with non-interactive environments like containers and CI/CD.

2. **Working Directory**: The package version does not require being run from the LangBot project root. You can run `langbot` from any directory, and it will create a `data/` directory in your current working directory.

3. **Frontend Files**: The frontend is pre-built and included in the package, so you don't need to run `npm build` separately.

These differences are intentional to make the package more user-friendly and suitable for various deployment scenarios.
