# TavilySearch Plugin

A LangBot plugin that provides search capabilities using Tavily API, a search engine built specifically for AI agents (LLMs).

## Features

- Real-time web search powered by Tavily
- Support for different search depths (basic/advanced)
- Topic-specific search (general/news/finance)
- Include AI-generated answers
- Include relevant images
- Include raw HTML content
- Customizable number of results

## Installation

1. Install the plugin.

2. Configure your Tavily API key:
   - Get your API key from [Tavily](https://tavily.com/)
   - Add the API key to the plugin configuration in LangBot

## Usage

This plugin adds a `tavily_search` tool that can be used by LLMs in conversations.

### Parameters

- **query** (required): The search query string
- **search_depth** (optional): "basic" (default) or "advanced"
- **topic** (optional): "general" (default), "news", or "finance"
- **max_results** (optional): Number of results (1-20, default: 5)
- **include_answer** (optional): Include AI-generated answer (default: false)
- **include_images** (optional): Include related images (default: false)
- **include_raw_content** (optional): Include raw HTML content (default: false)

### Example

When chatting with your LangBot, the LLM can automatically use this tool:

```
User: What's the latest news about artificial intelligence?

Bot: [Uses tavily_search tool with topic="news"]
```

## Development

To develop or modify this plugin:

1. Edit the tool logic in `components/tools/tavily_search.py`
2. Modify configuration in `manifest.yaml`
3. Update tool parameters in `components/tools/tavily_search.yaml`

## Configuration

The plugin requires the following configuration:

- **tavily_api_key**: Your Tavily API key (required)

## License

This plugin is part of the LangBot plugin ecosystem.

## Links

- [Tavily API Documentation](https://docs.tavily.com/)
- [LangBot Documentation](https://langbot.app/docs/)
