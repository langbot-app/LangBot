#!/usr/bin/env python3
"""
应用workflows翻译到语言文件

使用方法：
1. 编辑 workflows_translations.json 文件
2. 将 'TODO' 替换为实际翻译
3. 运行此脚本：python3 apply_workflows_translations.py

脚本会：
- 读取 workflows_translations.json
- 识别已完成的翻译（非"TODO"）
- 应用到对应的语言文件
- 生成进度报告
- 支持增量应用（可以分批翻译）
"""

import json
import re
from pathlib import Path
from typing import Dict, List, Tuple, Set


def load_translations() -> Dict:
    """加载翻译JSON文件"""
    json_path = Path(__file__).parent / 'workflows_translations.json'
    
    if not json_path.exists():
        raise FileNotFoundError(f"找不到翻译文件: {json_path}")
    
    with open(json_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def get_completed_translations(translations_data: Dict) -> Dict[str, Dict[str, str]]:
    """
    获取已完成的翻译
    
    返回格式：
    {
        'ja-JP': {'title': '工作流对话', 'description': '...', ...},
        'zh-Hant': {...},
        ...
    }
    """
    translations = translations_data.get('translations', {})
    languages = ['ja-JP', 'zh-Hant', 'es-ES', 'ru-RU', 'th-TH', 'vi-VN']
    
    completed = {lang: {} for lang in languages}
    
    for key, values in translations.items():
        for lang in languages:
            translation = values.get(lang, 'TODO')
            if translation != 'TODO' and translation.strip():
                completed[lang][key] = translation
    
    return completed


def apply_translations_to_file(file_path: Path, translations: Dict[str, str], lang_code: str) -> Tuple[int, List[str]]:
    """
    应用翻译到指定语言文件
    
    返回：(成功应用的数量, 失败的键列表)
    """
    if not file_path.exists():
        print(f"⚠️  文件不存在: {file_path}")
        return 0, list(translations.keys())
    
    # 读取文件内容
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 找到workflows部分的起始和结束位置
    workflows_start = content.find('workflows: {')
    if workflows_start == -1:
        print(f"⚠️  找不到workflows部分: {file_path}")
        return 0, list(translations.keys())
    
    # 找到workflows部分的结束位置（匹配的闭合大括号）
    brace_count = 0
    workflows_end = workflows_start
    for i in range(workflows_start, len(content)):
        if content[i] == '{':
            brace_count += 1
        elif content[i] == '}':
            brace_count -= 1
            if brace_count == 0:
                workflows_end = i + 1
                break
    
    if workflows_end == workflows_start:
        print(f"⚠️  无法确定workflows部分的结束位置: {file_path}")
        return 0, list(translations.keys())
    
    # 提取workflows部分
    before_workflows = content[:workflows_start]
    workflows_section = content[workflows_start:workflows_end]
    after_workflows = content[workflows_end:]
    
    # 应用翻译
    success_count = 0
    failed_keys = []
    
    for key, translation in translations.items():
        # 转义特殊字符
        escaped_key = re.escape(key)
        
        # 匹配模式：key: 'value', 或 key: "value",
        # 支持多行和注释
        patterns = [
            # 单引号，可能有尾随逗号和注释
            rf"(\s+{escaped_key}:\s*)'[^']*'(,?\s*(?://.*)?(?:\n|$))",
            # 双引号，可能有尾随逗号和注释
            rf'(\s+{escaped_key}:\s*)"[^"]*"(,?\s*(?://.*)?(?:\n|$))',
        ]
        
        replaced = False
        for pattern in patterns:
            if re.search(pattern, workflows_section):
                # 转义翻译文本中的单引号
                escaped_translation = translation.replace("'", "\\'")
                replacement = rf"\1'{escaped_translation}'\2"
                workflows_section = re.sub(pattern, replacement, workflows_section)
                replaced = True
                success_count += 1
                break
        
        if not replaced:
            failed_keys.append(key)
    
    # 重新组合文件内容
    new_content = before_workflows + workflows_section + after_workflows
    
    # 写回文件
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(new_content)
    
    return success_count, failed_keys


def update_progress_in_json(json_path: Path, completed_by_lang: Dict[str, int]):
    """更新JSON文件中的进度信息"""
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # 计算总的已翻译键数（取所有语言的平均值）
    total_translated = sum(completed_by_lang.values()) // len(completed_by_lang) if completed_by_lang else 0
    total_keys = data.get('_progress', {}).get('total_keys', 0)
    
    data['_progress']['translated_keys'] = total_translated
    data['_progress']['remaining_keys'] = total_keys - total_translated
    data['_progress']['by_language'] = completed_by_lang
    
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def generate_report(results: Dict[str, Tuple[int, List[str]]], total_keys: int):
    """生成应用报告"""
    print("\n" + "="*80)
    print("📊 Workflows翻译应用报告")
    print("="*80)
    
    total_applied = 0
    
    for lang, (success_count, failed_keys) in results.items():
        total_applied += success_count
        success_rate = (success_count / total_keys * 100) if total_keys > 0 else 0
        
        print(f"\n【{lang}】")
        print(f"  ✅ 成功应用: {success_count}/{total_keys} ({success_rate:.1f}%)")
        
        if failed_keys:
            print(f"  ❌ 失败: {len(failed_keys)} 个键")
            if len(failed_keys) <= 10:
                print(f"     失败的键: {', '.join(failed_keys)}")
            else:
                print(f"     失败的键（前10个）: {', '.join(failed_keys[:10])}...")
    
    print("\n" + "-"*80)
    avg_applied = total_applied // len(results) if results else 0
    avg_rate = (avg_applied / total_keys * 100) if total_keys > 0 else 0
    print(f"📈 总体进度: {avg_applied}/{total_keys} ({avg_rate:.1f}%)")
    print(f"📝 剩余待翻译: {total_keys - avg_applied} 个键")
    print("="*80)


def main():
    print("🚀 开始应用workflows翻译...")
    
    # 加载翻译数据
    print("\n📖 读取翻译文件...")
    translations_data = load_translations()
    total_keys = translations_data.get('_progress', {}).get('total_keys', 0)
    print(f"   总键数: {total_keys}")
    
    # 获取已完成的翻译
    print("\n🔍 识别已完成的翻译...")
    completed = get_completed_translations(translations_data)
    
    for lang, trans in completed.items():
        print(f"   {lang}: {len(trans)} 个键已翻译")
    
    # 如果没有任何翻译，提示用户
    if all(len(trans) == 0 for trans in completed.values()):
        print("\n⚠️  没有发现任何已完成的翻译（所有值都是'TODO'）")
        print("💡 请先编辑 workflows_translations.json 文件，将 'TODO' 替换为实际翻译")
        return
    
    # 应用翻译到各个语言文件
    print("\n✏️  应用翻译到语言文件...")
    
    locales_dir = Path(__file__).parent / 'src' / 'i18n' / 'locales'
    
    language_files = {
        'ja-JP': locales_dir / 'ja-JP.ts',
        'zh-Hant': locales_dir / 'zh-Hant.ts',
        'es-ES': locales_dir / 'es-ES.ts',
        'ru-RU': locales_dir / 'ru-RU.ts',
        'th-TH': locales_dir / 'th-TH.ts',
        'vi-VN': locales_dir / 'vi-VN.ts',
    }
    
    results = {}
    completed_by_lang = {}
    
    for lang, file_path in language_files.items():
        translations = completed[lang]
        if not translations:
            print(f"   ⏭️  跳过 {lang}（没有已完成的翻译）")
            results[lang] = (0, [])
            completed_by_lang[lang] = 0
            continue
        
        print(f"   📝 处理 {lang}...")
        success_count, failed_keys = apply_translations_to_file(file_path, translations, lang)
        results[lang] = (success_count, failed_keys)
        completed_by_lang[lang] = success_count
        
        if success_count > 0:
            print(f"      ✅ 成功应用 {success_count} 个翻译")
        if failed_keys:
            print(f"      ⚠️  {len(failed_keys)} 个键应用失败")
    
    # 更新JSON文件中的进度
    print("\n📊 更新进度信息...")
    json_path = Path(__file__).parent / 'workflows_translations.json'
    update_progress_in_json(json_path, completed_by_lang)
    
    # 生成报告
    generate_report(results, total_keys)
    
    print("\n✅ 翻译应用完成！")
    print("\n💡 提示:")
    print("   1. 继续编辑 workflows_translations.json 翻译更多键")
    print("   2. 再次运行此脚本应用新的翻译")
    print("   3. 重复以上步骤直到所有翻译完成")


if __name__ == '__main__':
    main()
