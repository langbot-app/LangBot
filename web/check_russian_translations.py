#!/usr/bin/env python3
"""检查俄语翻译中的中文字符问题"""
import json
import re
from pathlib import Path

def contains_chinese(text: str) -> bool:
    """检查文本是否包含中文字符"""
    return bool(re.search(r'[\u4e00-\u9fff]', text))

def main():
    json_path = Path(__file__).parent / "workflows_translations.json"
    
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    translations = data.get('translations', {})
    
    problematic_keys = []
    
    for key, value in translations.items():
        if isinstance(value, dict) and 'ru-RU' in value:
            ru_text = value['ru-RU']
            if ru_text != 'TODO' and contains_chinese(ru_text):
                zh_hans = value.get('zh-Hans', '')
                problematic_keys.append({
                    'key': key,
                    'ru_text': ru_text,
                    'zh_hans': zh_hans
                })
    
    print(f"发现 {len(problematic_keys)} 个包含中文字符的俄语翻译：\n")
    
    for item in problematic_keys[:20]:  # 只显示前20个
        print(f"键: {item['key']}")
        print(f"  中文原文: {item['zh_hans']}")
        print(f"  俄语翻译: {item['ru_text']}")
        print()
    
    if len(problematic_keys) > 20:
        print(f"... 还有 {len(problematic_keys) - 20} 个问题翻译")

if __name__ == '__main__':
    main()
