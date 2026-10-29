# AI Image Generation Plugin

## Introduction

A drawing plugin compatible with the OpenAI image generation API format. Supports any service compatible with the OpenAI image generation API.

## Features

- ✅ Fully compatible with OpenAI image generation API format
- 🎨 Supports custom API endpoint and model name
- 📐 Supports multiple image aspect ratios
- 🔧 Flexible configuration options

## Configuration Guide

### API Configuration

- **API Endpoint**: Defaults to `https://api.qhaigc.net`, can be customized to any compatible OpenAI-style API endpoint
- **API Key**: Get your API key from [https://api.qhaigc.net/console/token](https://api.qhaigc.net/console/token)
- **Model Name**: You can set a custom model name, default is `qh-draw-x1-pro`

### Image Size Options

The following image sizes are supported:

- Square 1:1 (1024x1024)
- Square 1:1 (1280x1280)
- Portrait 3:5 (768x1280)
- Landscape 5:3 (1280x768)
- Portrait 9:16 (720x1280)
- Landscape 16:9 (1280x720)
- Landscape 4:3 (1024x768)
- Portrait 3:4 (768x1024)

## Usage

Use the `!draw` command to generate images:

```bash
# Generate an image
!draw a beautiful sunset landscape
!draw a cat sitting on a rainbow
```

## Installation Steps

1. Install this plugin from the LangBot plugin management page
2. Obtain your API Key: [https://api.qhaigc.net/console/token](https://api.qhaigc.net/console/token)
3. Fill in the API Key in the plugin configuration
4. (Optional) Configure API endpoint, model name, and default image size

## Supported Models

### Nano Banana Series

- **Nano Banana 1** (Released August 2025): An image generation model by Google DeepMind, based on Gemini 2.5 Flash architecture with 450M to 8B parameters. Core strengths are role consistency, multi-image fusion, and local editing. It leads the LMArena image editing leaderboard with a score of 1362 and is widely used in e-commerce, design, education, and more.

- **Nano Banana 2** (Released November 2025): A comprehensive upgrade of the first generation, supporting native 2K resolution, with optional 4K super-resolution. Generation speed is improved by 300%, enabling complex scenes in just 10 seconds. Major breakthroughs in Chinese text rendering and mathematical formula derivation. It understands physical logic and world knowledge, using a "cognition + generation" hybrid architecture that revolutionizes productivity for creative industries.

### Qihang AI Drawing Series

- **qh-draw-3d**: Focuses on generating popular 3D style images, characterized by delicate 3D models and strong 3D visual effects.
- **qh-draw-4d**: Focuses on generating popular 4D style images, with sophisticated 4D models and visuals close to reality but not actual photos.
- **qh-draw-x1-pro**: Qihang AI Drawing x1-pro model, based on open-source SD models with natural language understanding.
- **qh-draw-x2-preview**: Self-developed professional drawing model V2.0. Based on x1-pro, it enhances language understanding and comprehensive drawing abilities, making it suitable for more tasks.
- **qh-draw:Korean-comic-style**: Specializes in generating classic 2D Korean comic style images, featuring bright colors, smooth lines, and precise scene mood for Korean comics.

### Available Model List

`nano-banana-1`, `nano-banana-2`, `qh-draw-3d`, `qh-draw-4d`, `qh-draw-x1-pro`, `qh-draw-x2-preview`, `qh-draw:Korean-comic-style`

## Compatibility

This plugin is compatible with any service that follows the OpenAI image generation API specification, including but not limited to:

- OpenAI DALL-E 3
- Other image generation services compatible with the OpenAI format

## License

MIT License
