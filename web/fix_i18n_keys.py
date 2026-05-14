#!/usr/bin/env python3
"""
自动修复所有语言文件中缺失的 nodeOutputs 和 nodeInputs 键
"""

import re
from pathlib import Path

# 需要添加的 nodeOutputs 键（使用英文作为临时翻译）
MISSING_NODE_OUTPUTS = {
    'sender': 'Sender',
    'output': 'Output',
    'result': 'Result',
    'data': 'Data',
    'error': 'Error Message',
    'success': 'Success Status',
    'event': 'Event',
    'trigger_time': 'Trigger Time',
    'logs': 'Logs',
    'scores': 'Scores',
    'missing': 'Missing Parameters',
    'parsed': 'Parsed Result',
    'chunks': 'Text Chunks',
    'text': 'Text Content',
    'case_1': 'Case 1 Output',
    'case_2': 'Case 2 Output',
    'branch_1': 'Branch 1 Output',
    'branch_2': 'Branch 2 Output',
    'count': 'Count',
    'execution_id': 'Execution ID',
    'notification_id': 'Notification ID',
    'suggestions': 'Suggestions',
    'embedding': 'Embedding Vector',
    'dimensions': 'Vector Dimensions',
    'intent': 'Intent',
    'entities': 'Entities',
}

# 需要添加的 nodeInputs 键
MISSING_NODE_INPUTS = {
    'payload': 'Payload',
    'input_value': 'Input Value',
    'conversation_id': 'Conversation ID',
}

# 需要修复的语言文件
LANGUAGE_FILES = [
    'ja-JP.ts',
    'zh-Hant.ts',
    'es-ES.ts',
    'ru-RU.ts',
    'th-TH.ts',
    'vi-VN.ts',
]

def find_insertion_point(content: str, section: str) -> tuple[int, str]:
    """
    找到插入点的位置
    section: 'nodeOutputs' 或 'nodeInputs'
    返回: (插入位置的行号, 缩进字符串)
    """
    lines = content.split('\n')
    in_section = False
    last_key_line = -1
    indent = '      '
    
    for i, line in enumerate(lines):
        if f'{section}:' in line and '{' in line:
            in_section = True
            continue
        
        if in_section:
            # 检测缩进
            if line.strip() and not line.strip().startswith('//'):
                match = re.match(r'^(\s+)', line)
                if match:
                    indent = match.group(1)
            
            # 找到最后一个键值对
            if ':' in line and not line.strip().startswith('//'):
                last_key_line = i
            
            # 遇到闭合括号，说明section结束
            if '},' in line and last_key_line > 0:
                return last_key_line, indent
    
    return -1, indent

def add_missing_keys(file_path: Path):
    """为指定的语言文件添加缺失的键"""
    print(f"\n处理文件: {file_path.name}")
    
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    lines = content.split('\n')
    modified = False
    
    # 处理 nodeOutputs
    for key, value in MISSING_NODE_OUTPUTS.items():
        if f"      {key}:" not in content:
            print(f"  添加 nodeOutputs.{key}")
            
            # 找到插入点
            insert_line, indent = find_insertion_point(content, 'nodeOutputs')
            if insert_line > 0:
                # 在最后一个键之后插入
                new_line = f"{indent}{key}: '{value}',"
                lines.insert(insert_line + 1, new_line)
                content = '\n'.join(lines)
                lines = content.split('\n')
                modified = True
    
    # 处理 nodeInputs
    for key, value in MISSING_NODE_INPUTS.items():
        if f"      {key}:" not in content:
            print(f"  添加 nodeInputs.{key}")
            
            # 找到插入点
            insert_line, indent = find_insertion_point(content, 'nodeInputs')
            if insert_line > 0:
                # 在最后一个键之后插入
                new_line = f"{indent}{key}: '{value}',"
                lines.insert(insert_line + 1, new_line)
                content = '\n'.join(lines)
                lines = content.split('\n')
                modified = True
    
    if modified:
        # 写回文件
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))
        print(f"  ✓ 已更新 {file_path.name}")
    else:
        print(f"  - {file_path.name} 无需更新")

def main():
    """主函数"""
    locales_dir = Path(__file__).parent / 'src' / 'i18n' / 'locales'
    
    print("=" * 60)
    print("开始修复多语言 i18n 文件")
    print("=" * 60)
    
    for lang_file in LANGUAGE_FILES:
        file_path = locales_dir / lang_file
        if file_path.exists():
            add_missing_keys(file_path)
        else:
            print(f"\n警告: 文件不存在 - {lang_file}")
    
    print("\n" + "=" * 60)
    print("修复完成！")
    print("=" * 60)
    print(f"\n已处理 {len(LANGUAGE_FILES)} 个语言文件")
    print(f"添加了 {len(MISSING_NODE_OUTPUTS)} 个 nodeOutputs 键")
    print(f"添加了 {len(MISSING_NODE_INPUTS)} 个 nodeInputs 键")

if __name__ == '__main__':
    main()
