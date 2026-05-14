#!/usr/bin/env python3
"""直接修复 ru-RU.ts 文件中包含中文字符的翻译
从 en-US.ts 提取英文原文，然后替换 ru-RU.ts 中的混合文本
"""
import re
from pathlib import Path
from typing import Dict, List, Tuple

def contains_chinese(text: str) -> bool:
    """检查文本是否包含中文字符"""
    return bool(re.search(r'[\u4e00-\u9fff]', text))

def extract_key_value_pairs(file_path: Path, section_name: str = 'workflows') -> Dict[str, str]:
    """从 .ts 文件中提取指定部分的键值对"""
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    result = {}
    in_section = False
    brace_count = 0
    
    for line in lines:
        # 检测进入目标部分
        if f'{section_name}:' in line and '{' in line:
            in_section = True
            brace_count = line.count('{') - line.count('}')
            continue
        
        if not in_section:
            continue
        
        # 更新括号计数
        brace_count += line.count('{') - line.count('}')
        
        # 提取键值对
        match = re.match(r'\s*(\w+):\s*[\'"]([^\'"]*(?:\\.[^\'"]*)*)[\'"],?\s*(?://.*)?$', line)
        if match:
            key = match.group(1)
            value = match.group(2)
            # 处理转义字符
            value = value.replace("\\'", "'").replace('\\"', '"').replace('\\n', '\n')
            result[key] = value
        
        # 检测退出部分
        if brace_count == 0:
            break
    
    return result

def find_problematic_lines(file_path: Path) -> List[Tuple[int, str, str]]:
    """找出包含中文字符的行"""
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    problematic = []
    in_workflows = False
    
    for i, line in enumerate(lines):
        if 'workflows:' in line:
            in_workflows = True
            continue
        
        if in_workflows and contains_chinese(line):
            # 提取键名
            match = re.match(r'\s*(\w+):\s*[\'"]', line)
            if match:
                key = match.group(1)
                problematic.append((i, key, line))
    
    return problematic

# 手动翻译映射 - 基于常见的中俄混合模式
MANUAL_TRANSLATIONS = {
    # 率 -> процент/коэффициент
    '成功率': 'Процент успеха',
    '失败率': 'Процент неудач',
    
    # 次数 -> количество/раз
    '失败次数': 'Количество неудач',
    '执行次数': 'Количество выполнений',
    '成功次数': 'Количество успехов',
    
    # 状态 -> статус
    '全部状态': 'Все статусы',
    '运行状态': 'Статус выполнения',
    
    # 时间 -> время
    '等待时间': 'Время ожидания',
    '执行时间': 'Время выполнения',
    '创建时间': 'Время создания',
    '更新时间': 'Время обновления',
    
    # 记录 -> запись
    '执行记录': 'Записи выполнения',
    '节点执行记录': 'Записи выполнения узлов',
    
    # 节点 -> узел
    '节点': 'Узел',
    '节点类型': 'Тип узла',
    '节点名称': 'Название узла',
    '选中节点': 'Выбранный узел',
    '搜索节点': 'Поиск узлов',
    '没有选中节点可复制': 'Нет выбранных узлов для копирования',
    '已复制节点': 'Узлы скопированы',
    '已粘贴节点': 'Узлы вставлены',
    '未找到匹配节点': 'Совпадающие узлы не найдены',
    '拖拽节点到画布添加': 'Перетащите узел на холст для добавления',
    '选择节点或连线': 'Выберите узел или соединение',
    '点击画布中节点或连线来查看和编辑其属性': 'Нажмите на узел или соединение на холсте, чтобы просмотреть и изменить его свойства',
    '该节点类型暂无配置选项': 'Для этого типа узла пока нет параметров конфигурации',
    '确定删除此节点': 'Вы уверены, что хотите удалить этот узел?',
    '删除后，该节点及其所有连线将被永久移除': 'После удаления узел и все его соединения будут удалены навсегда',
    '节点显示名称': 'Отображаемое имя узла',
    
    # 工作流 -> рабочий процесс
    '工作流': 'Рабочий процесс',
    '工作流名称': 'Название рабочего процесса',
    '输入工作流名称': 'Введите название рабочего процесса',
    
    # 变量 -> переменная
    '变量': 'Переменная',
    '变量名': 'Имя переменной',
    '上下文变量': 'Контекстная переменная',
    
    # 条件 -> условие
    '条件': 'Условие',
    '条件分支': 'Условная ветвь',
    '输入条件表达式': 'Введите условное выражение',
    '条件为空时': 'Когда условие пусто',
    '条件为空时，该连线将始终被执行': 'Когда условие пусто, это соединение всегда будет выполняться',
    
    # 其他常见词汇
    '已配置': 'Настроено',
    '未保存': 'Не сохранено',
    '有未保存更改': 'Есть несохраненные изменения',
    '剪贴板为空': 'Буфер обмена пуст',
    '正在加载节点类型': 'Загрузка типов узлов',
    '模拟消息': 'Имитация сообщения',
    '调试上下文': 'Контекст отладки',
    '请求体': 'Тело запроса',
    '确定删除此连线': 'Вы уверены, что хотите удалить это соединение?',
    '删除后，该连线将被永久移除': 'После удаления соединение будет удалено навсегда',
}

def create_translation_dict() -> Dict[str, str]:
    """创建完整的翻译字典，包括部分匹配"""
    translations = {}
    
    # 添加手动翻译
    for zh, ru in MANUAL_TRANSLATIONS.items():
        translations[zh] = ru
    
    return translations

def fix_mixed_text(text: str, translations: Dict[str, str]) -> str:
    """修复混合中俄文本"""
    # 首先尝试完全匹配
    for zh, ru in translations.items():
        if zh in text:
            text = text.replace(zh, ru)
    
    # 移除剩余的中文字符（如果还有的话）
    # 这是最后的手段，用俄语占位符替换
    if contains_chinese(text):
        # 提取中文部分并尝试翻译
        chinese_parts = re.findall(r'[\u4e00-\u9fff]+', text)
        for part in chinese_parts:
            if part in translations:
                text = text.replace(part, translations[part])
    
    return text

def main():
    base_dir = Path(__file__).parent
    en_us_file = base_dir / "src/i18n/locales/en-US.ts"
    ru_ru_file = base_dir / "src/i18n/locales/ru-RU.ts"
    
    print("🔍 正在分析 ru-RU.ts 文件...")
    
    # 找出有问题的行
    problematic_lines = find_problematic_lines(ru_ru_file)
    print(f"发现 {len(problematic_lines)} 行包含中文字符")
    
    if not problematic_lines:
        print("✅ 没有需要修复的翻译！")
        return
    
    # 读取整个文件
    with open(ru_ru_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    # 创建翻译字典
    translations = create_translation_dict()
    
    # 修复每一行
    fixed_count = 0
    for line_num, key, original_line in problematic_lines:
        # 提取当前值
        match = re.match(r'(\s*)(\w+):\s*[\'"]([^\'"]*(?:\\.[^\'"]*)*)[\'"],?(\s*(?://.*)?)\s*$', original_line)
        if not match:
            continue
        
        indent, key_name, value, comment = match.groups()
        
        # 修复值
        fixed_value = fix_mixed_text(value, translations)
        
        if fixed_value != value and not contains_chinese(fixed_value):
            # 重建行
            new_line = f"{indent}{key_name}: '{fixed_value}',{comment}\n"
            lines[line_num] = new_line
            fixed_count += 1
            print(f"✓ 修复 {key_name}: {value[:50]}... -> {fixed_value[:50]}...")
    
    # 写回文件
    if fixed_count > 0:
        with open(ru_ru_file, 'w', encoding='utf-8') as f:
            f.writelines(lines)
        print(f"\n✅ 成功修复 {fixed_count} 行翻译")
        print(f"📝 已更新文件: {ru_ru_file}")
    else:
        print("\n⚠️  没有成功修复任何翻译")
        print("可能需要手动检查或添加更多翻译映射")
    
    # 再次检查
    print("\n🔍 验证修复结果...")
    remaining_problems = find_problematic_lines(ru_ru_file)
    if remaining_problems:
        print(f"⚠️  仍有 {len(remaining_problems)} 行包含中文字符")
        print("\n前10个未修复的键:")
        for i, (_, key, line) in enumerate(remaining_problems[:10], 1):
            print(f"  {i}. {key}: {line.strip()[:80]}")
    else:
        print("✅ 所有中文字符已清除！")

if __name__ == '__main__':
    main()
