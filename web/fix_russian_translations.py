#!/usr/bin/env python3
"""修复 ru-RU.ts 文件中包含中文字符的翻译"""
import re
import os
from pathlib import Path
from anthropic import Anthropic

def contains_chinese(text: str) -> bool:
    """检查文本是否包含中文字符"""
    return bool(re.search(r'[\u4e00-\u9fff]', text))

def extract_workflows_section(file_path: Path) -> dict:
    """从 .ts 文件中提取 workflows 部分的键值对"""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 找到 workflows 部分
    workflows_match = re.search(r'workflows:\s*\{(.*?)\n\s*\},?\s*\n', content, re.DOTALL)
    if not workflows_match:
        return {}
    
    workflows_content = workflows_match.group(1)
    
    # 提取所有键值对
    pattern = r"(\w+):\s*['\"]([^'\"]*(?:\\.[^'\"]*)*)['\"]"
    matches = re.findall(pattern, workflows_content)
    
    result = {}
    for key, value in matches:
        # 处理转义字符
        value = value.replace("\\'", "'").replace('\\"', '"')
        result[key] = value
    
    return result

def translate_text(client: Anthropic, text: str, target_lang: str = "Russian") -> str:
    """使用 Claude API 翻译文本"""
    try:
        message = client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=1000,
            messages=[{
                "role": "user",
                "content": f"""Translate the following English text to {target_lang}. 
Only provide the translation, no explanations or additional text.
Keep any {{variable}} placeholders unchanged.

Text to translate: {text}"""
            }]
        )
        
        translation = message.content[0].text.strip()
        # 移除可能的引号
        translation = translation.strip('"').strip("'")
        return translation
    except Exception as e:
        print(f"翻译错误: {e}")
        return text

def main():
    # 检查 API key
    api_key = os.getenv('ANTHROPIC_API_KEY')
    if not api_key:
        print("错误: 未找到 ANTHROPIC_API_KEY 环境变量")
        print("请设置: export ANTHROPIC_API_KEY='your-api-key'")
        return
    
    client = Anthropic(api_key=api_key)
    
    base_dir = Path(__file__).parent
    en_us_file = base_dir / "src/i18n/locales/en-US.ts"
    ru_ru_file = base_dir / "src/i18n/locales/ru-RU.ts"
    
    # 提取英文和俄文的 workflows 部分
    print("正在提取英文原文...")
    en_workflows = extract_workflows_section(en_us_file)
    print(f"提取了 {len(en_workflows)} 个英文键")
    
    print("\n正在提取俄文翻译...")
    ru_workflows = extract_workflows_section(ru_ru_file)
    print(f"提取了 {len(ru_workflows)} 个俄文键")
    
    # 找出包含中文的俄文翻译
    problematic_keys = []
    for key, ru_text in ru_workflows.items():
        if contains_chinese(ru_text):
            en_text = en_workflows.get(key, '')
            if en_text:
                problematic_keys.append({
                    'key': key,
                    'en_text': en_text,
                    'ru_text': ru_text
                })
    
    print(f"\n发现 {len(problematic_keys)} 个需要修复的翻译")
    
    if not problematic_keys:
        print("没有需要修复的翻译！")
        return
    
    # 翻译前10个作为示例
    print("\n开始翻译前10个键...")
    fixed_translations = {}
    
    for i, item in enumerate(problematic_keys[:10], 1):
        key = item['key']
        en_text = item['en_text']
        old_ru_text = item['ru_text']
        
        print(f"\n[{i}/10] 翻译键: {key}")
        print(f"  英文: {en_text}")
        print(f"  旧俄文: {old_ru_text}")
        
        new_ru_text = translate_text(client, en_text, "Russian")
        print(f"  新俄文: {new_ru_text}")
        
        fixed_translations[key] = new_ru_text
    
    # 保存修复结果到文件
    output_file = base_dir / "russian_fixes.txt"
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(f"需要修复的翻译总数: {len(problematic_keys)}\n\n")
        f.write("=" * 80 + "\n")
        f.write("已翻译的前10个键:\n")
        f.write("=" * 80 + "\n\n")
        
        for key, new_text in fixed_translations.items():
            old_item = next(item for item in problematic_keys if item['key'] == key)
            f.write(f"键: {key}\n")
            f.write(f"英文: {old_item['en_text']}\n")
            f.write(f"旧俄文: {old_item['ru_text']}\n")
            f.write(f"新俄文: {new_text}\n")
            f.write("-" * 80 + "\n\n")
        
        f.write("\n" + "=" * 80 + "\n")
        f.write("剩余需要翻译的键:\n")
        f.write("=" * 80 + "\n\n")
        
        for item in problematic_keys[10:]:
            f.write(f"键: {item['key']}\n")
            f.write(f"英文: {item['en_text']}\n")
            f.write(f"旧俄文: {item['ru_text']}\n")
            f.write("-" * 80 + "\n\n")
    
    print(f"\n修复结果已保存到: {output_file}")
    print(f"\n注意: 由于翻译数量较多({len(problematic_keys)}个)，建议分批处理")
    print("您可以修改脚本中的 [:10] 来处理更多键")

if __name__ == '__main__':
    main()
