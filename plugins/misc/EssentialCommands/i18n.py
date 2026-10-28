# -*- coding: utf-8 -*-
"""
Internationalization support for EssentialCommands plugin
"""

TRANSLATIONS = {
    "en_US": {
        # version command
        "version.output": "LangBot Version: {version}",

        # help command
        "help.title": "LangBot - Production-grade IM bot development platform",
        "help.website": "https://langbot.app",
        "help.command_tip": "Type `{command_prefix}cmd` for command usage.",

        # cmd command
        "cmd.title": "Available Commands:",
        "cmd.tip": "Type `{command_prefix}cmd man <command>` for more detailed manual.",
        "cmd.man_not_found": "Command {command_name} not found",
        "cmd.man_title": "Command {command_name} manual:\n{description}",

        # func command
        "func.title": "Available LLM Tools:",
        "func.tool_item": "{name} - {description}\n - Prompt: {prompt}",

        # plugin command
        "plugin.title": "Loaded Plugins:",
        "plugin.item": "{name} - {description}",

        # reset command
        "reset.success": "Session reset",
    },
    "zh_Hans": {
        # version command
        "version.output": "LangBot 版本: {version}",

        # help command
        "help.title": "LangBot - 生产级 IM 机器人开发平台",
        "help.website": "https://langbot.app",
        "help.command_tip": "输入 `{command_prefix}cmd` 查看命令用法。",

        # cmd command
        "cmd.title": "可用命令:",
        "cmd.tip": "输入 `{command_prefix}cmd man <命令>` 查看详细手册。",
        "cmd.man_not_found": "未找到命令 {command_name}",
        "cmd.man_title": "命令 {command_name} 手册:\n{description}",

        # func command
        "func.title": "可用的 LLM 工具:",
        "func.tool_item": "{name} - {description}\n - 提示词: {prompt}",

        # plugin command
        "plugin.title": "已加载的插件:",
        "plugin.item": "{name} - {description}",

        # reset command
        "reset.success": "会话已重置",
    }
}


def get_text(language: str, key: str, **kwargs) -> str:
    """
    Get translated text for the given language and key.

    Args:
        language: Language code (e.g., 'en_US', 'zh_Hans')
        key: Translation key (e.g., 'version.output')
        **kwargs: Format arguments for the text

    Returns:
        Translated and formatted text
    """
    # Fallback to en_US if language not found
    if language not in TRANSLATIONS:
        language = "en_US"

    # Get translation
    text = TRANSLATIONS.get(language, {}).get(key, "")

    # If key not found, fallback to en_US
    if not text:
        text = TRANSLATIONS["en_US"].get(key, key)

    # Format with kwargs
    if kwargs:
        return text.format(**kwargs)

    return text
