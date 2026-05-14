#!/usr/bin/env python3
"""
分析所有语言文件中缺失的翻译键
对比 zh-Hans.ts（完整翻译）和其他语言文件，找出所有英文键
"""

import re
from pathlib import Path
from typing import Dict, List, Set

def extract_keys_from_ts(file_path: Path) -> Dict[str, str]:
    """从 TypeScript 文件中提取所有键值对"""
    content = file_path.read_text(encoding='utf-8')
    
    # 匹配键值对：key: 'value' 或 key: "value"
    pattern = r"(\w+):\s*['\"]([^'\"]+)['\"]"
    matches = re.findall(pattern, content)
    
    return dict(matches)

def is_english(text: str) -> bool:
    """判断文本是否主要是英文"""
    # 如果文本中英文字符占比超过50%，认为是英文
    english_chars = sum(1 for c in text if c.isascii() and c.isalpha())
    total_chars = sum(1 for c in text if c.isalpha())
    
    if total_chars == 0:
        return False
    
    return english_chars / total_chars > 0.5

def analyze_file(file_path: Path, reference_keys: Dict[str, str]) -> Dict[str, List[str]]:
    """分析单个文件，找出需要翻译的英文键"""
    keys = extract_keys_from_ts(file_path)
    
    english_keys = []
    missing_keys = []
    
    for key, value in keys.items():
        if is_english(value):
            english_keys.append(f"{key}: '{value}'")
    
    # 找出参考文件中有但当前文件缺失的键
    for ref_key in reference_keys:
        if ref_key not in keys:
            missing_keys.append(ref_key)
    
    return {
        'english_keys': english_keys,
        'missing_keys': missing_keys,
        'total_keys': len(keys)
    }

def main():
    locales_dir = Path(__file__).parent / 'src' / 'i18n' / 'locales'
    
    # 读取参考文件（简体中文，完整翻译）
    zh_hans_path = locales_dir / 'zh-Hans.ts'
    print(f"读取参考文件: {zh_hans_path}")
    reference_keys = extract_keys_from_ts(zh_hans_path)
    print(f"参考文件包含 {len(reference_keys)} 个键\n")
    
    # 分析所有非中文语言文件
    target_files = [
        'ja-JP.ts',
        'zh-Hant.ts',
        'es-ES.ts',
        'ru-RU.ts',
        'th-TH.ts',
        'vi-VN.ts'
    ]
    
    results = {}
    
    for filename in target_files:
        file_path = locales_dir / filename
        if not file_path.exists():
            print(f"⚠️  文件不存在: {filename}")
            continue
        
        print(f"\n{'='*60}")
        print(f"分析文件: {filename}")
        print(f"{'='*60}")
        
        result = analyze_file(file_path, reference_keys)
        results[filename] = result
        
        print(f"总键数: {result['total_keys']}")
        print(f"英文键数: {len(result['english_keys'])}")
        print(f"缺失键数: {len(result['missing_keys'])}")
        
        if result['english_keys']:
            print(f"\n前10个英文键示例:")
            for key in result['english_keys'][:10]:
                print(f"  - {key}")
        
        if result['missing_keys']:
            print(f"\n前10个缺失键示例:")
            for key in result['missing_keys'][:10]:
                print(f"  - {key}")
    
    # 汇总统计
    print(f"\n\n{'='*60}")
    print("汇总统计")
    print(f"{'='*60}")
    
    total_english = sum(len(r['english_keys']) for r in results.values())
    total_missing = sum(len(r['missing_keys']) for r in results.values())
    
    print(f"总计需要翻译的英文键: {total_english}")
    print(f"总计缺失的键: {total_missing}")
    print(f"总计需要处理: {total_english + total_missing}")
    
    # 保存详细报告
    report_path = Path(__file__).parent.parent / 'plans' / 'translation-analysis-report.txt'
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write("翻译分析报告\n")
        f.write("="*60 + "\n\n")
        
        for filename, result in results.items():
            f.write(f"\n文件: {filename}\n")
            f.write(f"总键数: {result['total_keys']}\n")
            f.write(f"英文键数: {len(result['english_keys'])}\n")
            f.write(f"缺失键数: {len(result['missing_keys'])}\n")
            
            if result['english_keys']:
                f.write(f"\n英文键列表:\n")
                for key in result['english_keys']:
                    f.write(f"  {key}\n")
            
            if result['missing_keys']:
                f.write(f"\n缺失键列表:\n")
                for key in result['missing_keys']:
                    f.write(f"  {key}\n")
            
            f.write("\n" + "="*60 + "\n")
    
    print(f"\n详细报告已保存到: {report_path}")

if __name__ == '__main__':
    main()
