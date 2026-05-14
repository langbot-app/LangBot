#!/usr/bin/env python3
"""
检查workflows翻译进度

使用方法：
python3 check_translation_progress.py

显示：
- 每种语言的翻译进度
- 已完成和待完成的键数量
- 翻译完成百分比
- 最近翻译的键（如果有）
"""

import json
from pathlib import Path
from typing import Dict, List, Tuple


def load_translations() -> Dict:
    """加载翻译JSON文件"""
    json_path = Path(__file__).parent / 'workflows_translations.json'
    
    if not json_path.exists():
        raise FileNotFoundError(f"找不到翻译文件: {json_path}")
    
    with open(json_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def analyze_progress(translations_data: Dict) -> Dict[str, Dict]:
    """
    分析每种语言的翻译进度
    
    返回格式：
    {
        'ja-JP': {
            'completed': 50,
            'total': 627,
            'percentage': 7.97,
            'completed_keys': ['title', 'description', ...],
            'pending_keys': ['...', ...]
        },
        ...
    }
    """
    translations = translations_data.get('translations', {})
    languages = ['ja-JP', 'zh-Hant', 'es-ES', 'ru-RU', 'th-TH', 'vi-VN']
    
    progress = {}
    
    for lang in languages:
        completed_keys = []
        pending_keys = []
        
        for key, values in translations.items():
            translation = values.get(lang, 'TODO')
            if translation != 'TODO' and translation.strip():
                completed_keys.append(key)
            else:
                pending_keys.append(key)
        
        total = len(translations)
        completed = len(completed_keys)
        percentage = (completed / total * 100) if total > 0 else 0
        
        progress[lang] = {
            'completed': completed,
            'total': total,
            'percentage': percentage,
            'completed_keys': completed_keys,
            'pending_keys': pending_keys
        }
    
    return progress


def get_language_name(lang_code: str) -> str:
    """获取语言的中文名称"""
    names = {
        'ja-JP': '日语',
        'zh-Hant': '繁体中文',
        'es-ES': '西班牙语',
        'ru-RU': '俄语',
        'th-TH': '泰语',
        'vi-VN': '越南语'
    }
    return names.get(lang_code, lang_code)


def print_progress_bar(percentage: float, width: int = 40) -> str:
    """生成进度条"""
    filled = int(width * percentage / 100)
    bar = '█' * filled + '░' * (width - filled)
    return f"[{bar}] {percentage:.1f}%"


def display_progress(progress: Dict[str, Dict]):
    """显示翻译进度"""
    print("\n" + "="*80)
    print("📊 Workflows翻译进度报告")
    print("="*80)
    
    # 按完成度排序
    sorted_langs = sorted(progress.items(), key=lambda x: x[1]['percentage'], reverse=True)
    
    for lang, data in sorted_langs:
        lang_name = get_language_name(lang)
        completed = data['completed']
        total = data['total']
        percentage = data['percentage']
        
        print(f"\n【{lang_name} ({lang})】")
        print(f"  {print_progress_bar(percentage)}")
        print(f"  ✅ 已完成: {completed}/{total}")
        print(f"  ⏳ 待翻译: {total - completed}")
        
        # 显示最近完成的键（前5个）
        if data['completed_keys']:
            recent = data['completed_keys'][:5]
            print(f"  📝 最近完成: {', '.join(recent)}")
            if len(data['completed_keys']) > 5:
                print(f"     （还有 {len(data['completed_keys']) - 5} 个已完成）")
    
    # 总体统计
    print("\n" + "-"*80)
    total_completed = sum(d['completed'] for d in progress.values())
    total_items = sum(d['total'] for d in progress.values())
    avg_percentage = (total_completed / total_items * 100) if total_items > 0 else 0
    
    print(f"📈 总体进度: {total_completed}/{total_items} ({avg_percentage:.1f}%)")
    print(f"📊 平均每种语言: {total_completed // len(progress)}/{progress[list(progress.keys())[0]]['total']}")
    
    # 估算剩余工作量
    remaining = total_items - total_completed
    print(f"\n💡 剩余工作量: {remaining} 个翻译项")
    
    if remaining > 0:
        # 建议分批策略
        batches_50 = (remaining + 49) // 50  # 向上取整
        batches_100 = (remaining + 99) // 100
        
        print(f"   建议分批策略:")
        print(f"   - 每批50个键: 需要 {batches_50} 批")
        print(f"   - 每批100个键: 需要 {batches_100} 批")
    
    print("="*80)


def suggest_next_keys(progress: Dict[str, Dict], batch_size: int = 50) -> List[str]:
    """建议下一批要翻译的键"""
    # 找出所有语言都还没翻译的键
    all_pending = set()
    
    for lang, data in progress.items():
        if not all_pending:
            all_pending = set(data['pending_keys'])
        else:
            all_pending &= set(data['pending_keys'])
    
    return list(all_pending)[:batch_size]


def main():
    print("🔍 正在检查翻译进度...")
    
    try:
        # 加载翻译数据
        translations_data = load_translations()
        
        # 分析进度
        progress = analyze_progress(translations_data)
        
        # 显示进度
        display_progress(progress)
        
        # 建议下一批翻译的键
        next_keys = suggest_next_keys(progress, batch_size=50)
        
        if next_keys:
            print(f"\n💡 建议下一批翻译的键（前10个）:")
            for i, key in enumerate(next_keys[:10], 1):
                print(f"   {i}. {key}")
            
            if len(next_keys) > 10:
                print(f"   ... 还有 {len(next_keys) - 10} 个键")
        else:
            print("\n🎉 恭喜！所有翻译已完成！")
        
        print("\n✅ 进度检查完成")
        
    except FileNotFoundError as e:
        print(f"\n❌ 错误: {e}")
        print("💡 请确保 workflows_translations.json 文件存在")
    except Exception as e:
        print(f"\n❌ 发生错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    main()
