#!/usr/bin/env python3
"""
从 en-US.ts 提取 workflows 部分，生成干净的俄语翻译
策略：直接替换整个 workflows 部分
"""
import re
from pathlib import Path

def extract_workflows_section(file_path: Path) -> tuple[str, int, int]:
    """提取 workflows 部分的内容和行号范围"""
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    start_line = None
    end_line = None
    brace_count = 0
    
    for i, line in enumerate(lines):
        if 'workflows:' in line and '{' in line:
            start_line = i
            brace_count = line.count('{') - line.count('}')
            continue
        
        if start_line is not None:
            brace_count += line.count('{') - line.count('}')
            if brace_count == 0:
                end_line = i
                break
    
    if start_line is not None and end_line is not None:
        section = ''.join(lines[start_line:end_line+1])
        return section, start_line, end_line
    
    return '', -1, -1

def translate_en_to_ru(text: str) -> str:
    """简单的英译俄映射"""
    translations = {
        # 基础词汇
        'Workflow': 'Рабочий процесс',
        'workflow': 'рабочий процесс',
        'Node': 'Узел',
        'node': 'узел',
        'nodes': 'узлы',
        'Nodes': 'Узлы',
        'Success': 'Успех',
        'success': 'успех',
        'Failed': 'Не удалось',
        'failed': 'не удалось',
        'Error': 'Ошибка',
        'error': 'ошибка',
        'Loading': 'Загрузка',
        'loading': 'загрузка',
        'Save': 'Сохранить',
        'save': 'сохранить',
        'Delete': 'Удалить',
        'delete': 'удалить',
        'Edit': 'Редактировать',
        'edit': 'редактировать',
        'Create': 'Создать',
        'create': 'создать',
        'Copy': 'Копировать',
        'copy': 'копировать',
        'Paste': 'Вставить',
        'paste': 'вставить',
        'Copied': 'Скопировано',
        'copied': 'скопировано',
        'Pasted': 'Вставлено',
        'pasted': 'вставлено',
        'Configuration': 'Конфигурация',
        'configuration': 'конфигурация',
        'Execution': 'Выполнение',
        'execution': 'выполнение',
        'executions': 'выполнения',
        'Executions': 'Выполнения',
        'Record': 'Запись',
        'record': 'запись',
        'records': 'записи',
        'Records': 'Записи',
        'Status': 'Статус',
        'status': 'статус',
        'All': 'Все',
        'all': 'все',
        'Duration': 'Продолжительность',
        'duration': 'продолжительность',
        'Time': 'Время',
        'time': 'время',
        'Rate': 'Коэффициент',
        'rate': 'коэффициент',
        'Average': 'Средний',
        'average': 'средний',
        'Total': 'Всего',
        'total': 'всего',
        'Last': 'Последний',
        'last': 'последний',
        'Condition': 'Условие',
        'condition': 'условие',
        'Branch': 'Ветвь',
        'branch': 'ветвь',
        'Variable': 'Переменная',
        'variable': 'переменная',
        'Context': 'Контекст',
        'context': 'контекст',
        'Debug': 'Отладка',
        'debug': 'отладка',
        'Message': 'Сообщение',
        'message': 'сообщение',
        'Request': 'Запрос',
        'request': 'запрос',
        'Body': 'Тело',
        'body': 'тело',
        'Empty': 'Пусто',
        'empty': 'пусто',
        'Clipboard': 'Буфер обмена',
        'clipboard': 'буфер обмена',
        'Search': 'Поиск',
        'search': 'поиск',
        'Type': 'Тип',
        'type': 'тип',
        'Found': 'Найдено',
        'found': 'найдено',
        'Drag': 'Перетащить',
        'drag': 'перетащить',
        'Canvas': 'Холст',
        'canvas': 'холст',
        'Select': 'Выбрать',
        'select': 'выбрать',
        'Edge': 'Соединение',
        'edge': 'соединение',
        'Click': 'Нажать',
        'click': 'нажать',
        'View': 'Просмотреть',
        'view': 'просмотреть',
        'Properties': 'Свойства',
        'properties': 'свойства',
        'Configured': 'Настроено',
        'configured': 'настроено',
        'Expression': 'Выражение',
        'expression': 'выражение',
        'Enter': 'Введите',
        'enter': 'введите',
        'When': 'Когда',
        'when': 'когда',
        'Will': 'Будет',
        'will': 'будет',
        'Always': 'Всегда',
        'always': 'всегда',
        'Executed': 'Выполнено',
        'executed': 'выполнено',
        'Support': 'Поддержка',
        'support': 'поддержка',
        'Reference': 'Ссылка',
        'reference': 'ссылка',
        'Confirm': 'Подтвердить',
        'confirm': 'подтвердить',
        'After': 'После',
        'after': 'после',
        'Removed': 'Удалено',
        'removed': 'удалено',
        'Permanently': 'Навсегда',
        'permanently': 'навсегда',
        'Label': 'Метка',
        'label': 'метка',
        'Display': 'Отображение',
        'display': 'отображение',
        'Name': 'Имя',
        'name': 'имя',
        'Simulate': 'Имитировать',
        'simulate': 'имитировать',
        'Options': 'Параметры',
        'options': 'параметры',
        'No': 'Нет',
        'no': 'нет',
        'Unsaved': 'Несохраненные',
        'unsaved': 'несохраненные',
        'Changes': 'Изменения',
        'changes': 'изменения',
        'Nothing': 'Ничего',
        'nothing': 'ничего',
        'Selected': 'Выбрано',
        'selected': 'выбрано',
        'Matching': 'Совпадающие',
        'matching': 'совпадающие',
        'Add': 'Добавить',
        'add': 'добавить',
        'Connection': 'Соединение',
        'connection': 'соединение',
    }
    
    result = text
    for en, ru in translations.items():
        result = result.replace(f"'{en}'", f"'{ru}'")
        result = result.replace(f'"{en}"', f'"{ru}"')
    
    return result

def main():
    base_dir = Path(__file__).parent
    en_us_file = base_dir / "src/i18n/locales/en-US.ts"
    ru_ru_file = base_dir / "src/i18n/locales/ru-RU.ts"
    
    print("📖 从 en-US.ts 提取 workflows 部分...")
    en_workflows, en_start, en_end = extract_workflows_section(en_us_file)
    
    if not en_workflows:
        print("❌ 无法提取 en-US.ts 的 workflows 部分")
        return
    
    print(f"✓ 提取了 {en_end - en_start + 1} 行")
    
    print("\n🔄 翻译成俄语...")
    ru_workflows = translate_en_to_ru(en_workflows)
    
    print("\n📝 读取 ru-RU.ts 文件...")
    with open(ru_ru_file, 'r', encoding='utf-8') as f:
        ru_lines = f.readlines()
    
    # 找到 ru-RU.ts 中的 workflows 部分
    print("🔍 定位 ru-RU.ts 中的 workflows 部分...")
    _, ru_start, ru_end = extract_workflows_section(ru_ru_file)
    
    if ru_start == -1:
        print("❌ 无法找到 ru-RU.ts 的 workflows 部分")
        return
    
    print(f"✓ 找到位置: 行 {ru_start+1} 到 {ru_end+1}")
    
    # 替换
    print("\n✏️  替换 workflows 部分...")
    new_lines = ru_lines[:ru_start] + [ru_workflows] + ru_lines[ru_end+1:]
    
    # 写回文件
    with open(ru_ru_file, 'w', encoding='utf-8') as f:
        f.writelines(new_lines)
    
    print(f"✅ 已更新 {ru_ru_file}")
    
    # 验证
    print("\n🔍 验证结果...")
    with open(ru_ru_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    chinese_count = len(re.findall(r'[\u4e00-\u9fff]', content))
    if chinese_count == 0:
        print("✅ 验证通过：没有中文字符！")
    else:
        print(f"⚠️  仍有 {chinese_count} 个中文字符")

if __name__ == '__main__':
    main()
