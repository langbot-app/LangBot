#!/usr/bin/env python3
"""检查 ru-RU.ts 文件中的中文字符问题"""
import re
from pathlib import Path

def contains_chinese(text: str) -> bool:
    """检查文本是否包含中文字符"""
    return bool(re.search(r'[\u4e00-\u9fff]', text))

def main():
    ts_file = Path(__file__).parent / "src/i18n/locales/ru-RU.ts"
    
    with open(ts_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    problematic_lines = []
    in_workflows = False
    
    for i, line in enumerate(lines, 1):
        # 检测是否进入 workflows 部分
        if 'workflows:' in line:
            in_workflows = True
        elif in_workflows and line.strip().startswith('}') and line.count('}') > line.count('{'):
            # 可能退出 workflows 部分
            pass
        
        # 检查是否包含中文字符
        if contains_chinese(line):
            # 提取键名
            key_match = re.search(r'(\w+):\s*[\'"]', line)
            key_name = key_match.group(1) if key_match else 'unknown'
            
            problematic_lines.append({
                'line_num': i,
                'key': key_name,
                'content': line.strip(),
                'in_workflows': in_workflows
            })
    
    print(f"发现 {len(problematic_lines)} 行包含中文字符的俄语翻译：\n")
    
    # 只显示 workflows 部分的问题
    workflows_problems = [p for p in problematic_lines if p['in_workflows']]
    
    print(f"workflows 部分问题: {len(workflows_problems)} 行\n")
    
    for item in workflows_problems[:30]:  # 显示前30个
        print(f"行 {item['line_num']}: {item['key']}")
        print(f"  {item['content'][:100]}")
        print()
    
    if len(workflows_problems) > 30:
        print(f"... 还有 {len(workflows_problems) - 30} 个问题行")

if __name__ == '__main__':
    main()
