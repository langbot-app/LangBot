#!/usr/bin/env python3
"""
将英文翻译键翻译成对应的目标语言
"""

from pathlib import Path
import re

# 翻译映射表
TRANSLATIONS = {
    'ja-JP': {  # 日文
        'Sender': '送信者',
        'Output': '出力',
        'Result': '結果',
        'Data': 'データ',
        'Error Message': 'エラーメッセージ',
        'Success Status': '成功ステータス',
        'Event': 'イベント',
        'Trigger Time': 'トリガー時刻',
        'Logs': 'ログ',
        'Scores': 'スコア',
        'Missing Parameters': '不足パラメータ',
        'Parsed Result': '解析結果',
        'Text Chunks': 'テキストチャンク',
        'Text Content': 'テキスト内容',
        'Case 1 Output': 'ケース1出力',
        'Case 2 Output': 'ケース2出力',
        'Branch 1 Output': 'ブランチ1出力',
        'Branch 2 Output': 'ブランチ2出力',
        'Count': 'カウント',
        'Execution ID': '実行ID',
        'Notification ID': '通知ID',
        'Suggestions': '提案',
        'Embedding Vector': '埋め込みベクトル',
        'Vector Dimensions': 'ベクトル次元',
        'Intent': '意図',
        'Entities': 'エンティティ',
        'Payload': 'ペイロード',
        'Input Value': '入力値',
        'Conversation ID': '会話ID',
    },
    'zh-Hant': {  # 繁体中文
        'Sender': '發送者',
        'Output': '輸出',
        'Result': '結果',
        'Data': '數據',
        'Error Message': '錯誤訊息',
        'Success Status': '成功狀態',
        'Event': '事件',
        'Trigger Time': '觸發時間',
        'Logs': '日誌',
        'Scores': '分數',
        'Missing Parameters': '缺失參數',
        'Parsed Result': '解析結果',
        'Text Chunks': '文本塊',
        'Text Content': '文本內容',
        'Case 1 Output': '情況1輸出',
        'Case 2 Output': '情況2輸出',
        'Branch 1 Output': '分支1輸出',
        'Branch 2 Output': '分支2輸出',
        'Count': '計數',
        'Execution ID': '執行ID',
        'Notification ID': '通知ID',
        'Suggestions': '建議',
        'Embedding Vector': '嵌入向量',
        'Vector Dimensions': '向量維度',
        'Intent': '意圖',
        'Entities': '實體',
        'Payload': '負載',
        'Input Value': '輸入值',
        'Conversation ID': '對話ID',
    },
    'es-ES': {  # 西班牙语
        'Sender': 'Remitente',
        'Output': 'Salida',
        'Result': 'Resultado',
        'Data': 'Datos',
        'Error Message': 'Mensaje de Error',
        'Success Status': 'Estado de Éxito',
        'Event': 'Evento',
        'Trigger Time': 'Hora de Activación',
        'Logs': 'Registros',
        'Scores': 'Puntuaciones',
        'Missing Parameters': 'Parámetros Faltantes',
        'Parsed Result': 'Resultado Analizado',
        'Text Chunks': 'Fragmentos de Texto',
        'Text Content': 'Contenido de Texto',
        'Case 1 Output': 'Salida Caso 1',
        'Case 2 Output': 'Salida Caso 2',
        'Branch 1 Output': 'Salida Rama 1',
        'Branch 2 Output': 'Salida Rama 2',
        'Count': 'Conteo',
        'Execution ID': 'ID de Ejecución',
        'Notification ID': 'ID de Notificación',
        'Suggestions': 'Sugerencias',
        'Embedding Vector': 'Vector de Incrustación',
        'Vector Dimensions': 'Dimensiones del Vector',
        'Intent': 'Intención',
        'Entities': 'Entidades',
        'Payload': 'Carga Útil',
        'Input Value': 'Valor de Entrada',
        'Conversation ID': 'ID de Conversación',
    },
    'ru-RU': {  # 俄语
        'Sender': 'Отправитель',
        'Output': 'Вывод',
        'Result': 'Результат',
        'Data': 'Данные',
        'Error Message': 'Сообщение об Ошибке',
        'Success Status': 'Статус Успеха',
        'Event': 'Событие',
        'Trigger Time': 'Время Триггера',
        'Logs': 'Журналы',
        'Scores': 'Оценки',
        'Missing Parameters': 'Отсутствующие Параметры',
        'Parsed Result': 'Разобранный Результат',
        'Text Chunks': 'Фрагменты Текста',
        'Text Content': 'Текстовое Содержимое',
        'Case 1 Output': 'Вывод Случая 1',
        'Case 2 Output': 'Вывод Случая 2',
        'Branch 1 Output': 'Вывод Ветви 1',
        'Branch 2 Output': 'Вывод Ветви 2',
        'Count': 'Количество',
        'Execution ID': 'ID Выполнения',
        'Notification ID': 'ID Уведомления',
        'Suggestions': 'Предложения',
        'Embedding Vector': 'Вектор Встраивания',
        'Vector Dimensions': 'Размерности Вектора',
        'Intent': 'Намерение',
        'Entities': 'Сущности',
        'Payload': 'Полезная Нагрузка',
        'Input Value': 'Входное Значение',
        'Conversation ID': 'ID Разговора',
    },
    'th-TH': {  # 泰语
        'Sender': 'ผู้ส่ง',
        'Output': 'ผลลัพธ์',
        'Result': 'ผลลัพธ์',
        'Data': 'ข้อมูล',
        'Error Message': 'ข้อความข้อผิดพลาด',
        'Success Status': 'สถานะความสำเร็จ',
        'Event': 'เหตุการณ์',
        'Trigger Time': 'เวลาทริกเกอร์',
        'Logs': 'บันทึก',
        'Scores': 'คะแนน',
        'Missing Parameters': 'พารามิเตอร์ที่ขาดหายไป',
        'Parsed Result': 'ผลการแยกวิเคราะห์',
        'Text Chunks': 'ส่วนข้อความ',
        'Text Content': 'เนื้อหาข้อความ',
        'Case 1 Output': 'ผลลัพธ์กรณีที่ 1',
        'Case 2 Output': 'ผลลัพธ์กรณีที่ 2',
        'Branch 1 Output': 'ผลลัพธ์สาขา 1',
        'Branch 2 Output': 'ผลลัพธ์สาขา 2',
        'Count': 'จำนวน',
        'Execution ID': 'ID การดำเนินการ',
        'Notification ID': 'ID การแจ้งเตือน',
        'Suggestions': 'คำแนะนำ',
        'Embedding Vector': 'เวกเตอร์ฝังตัว',
        'Vector Dimensions': 'มิติเวกเตอร์',
        'Intent': 'เจตนา',
        'Entities': 'เอนทิตี',
        'Payload': 'เพย์โหลด',
        'Input Value': 'ค่าอินพุต',
        'Conversation ID': 'ID การสนทนา',
    },
    'vi-VN': {  # 越南语
        'Sender': 'Người gửi',
        'Output': 'Đầu ra',
        'Result': 'Kết quả',
        'Data': 'Dữ liệu',
        'Error Message': 'Thông báo Lỗi',
        'Success Status': 'Trạng thái Thành công',
        'Event': 'Sự kiện',
        'Trigger Time': 'Thời gian Kích hoạt',
        'Logs': 'Nhật ký',
        'Scores': 'Điểm số',
        'Missing Parameters': 'Tham số Thiếu',
        'Parsed Result': 'Kết quả Phân tích',
        'Text Chunks': 'Đoạn Văn bản',
        'Text Content': 'Nội dung Văn bản',
        'Case 1 Output': 'Đầu ra Trường hợp 1',
        'Case 2 Output': 'Đầu ra Trường hợp 2',
        'Branch 1 Output': 'Đầu ra Nhánh 1',
        'Branch 2 Output': 'Đầu ra Nhánh 2',
        'Count': 'Số lượng',
        'Execution ID': 'ID Thực thi',
        'Notification ID': 'ID Thông báo',
        'Suggestions': 'Gợi ý',
        'Embedding Vector': 'Vector Nhúng',
        'Vector Dimensions': 'Kích thước Vector',
        'Intent': 'Ý định',
        'Entities': 'Thực thể',
        'Payload': 'Tải trọng',
        'Input Value': 'Giá trị Đầu vào',
        'Conversation ID': 'ID Hội thoại',
    },
}

def translate_file(file_path: Path, lang_code: str):
    """翻译指定语言文件"""
    print(f"\n处理文件: {file_path.name}")
    
    if lang_code not in TRANSLATIONS:
        print(f"  ⚠️  没有 {lang_code} 的翻译映射")
        return
    
    translations = TRANSLATIONS[lang_code]
    
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    modified = False
    translated_count = 0
    
    # 替换翻译
    for english, translated in translations.items():
        # 匹配格式: key: 'English Text',
        pattern = rf"(\s+\w+:\s+)'{re.escape(english)}',"
        if re.search(pattern, content):
            content = re.sub(pattern, rf"\1'{translated}',", content)
            translated_count += 1
            modified = True
            print(f"  ✓ 翻译: '{english}' -> '{translated}'")
    
    if modified:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"  ✅ 已更新 {file_path.name}，共翻译 {translated_count} 个键")
    else:
        print(f"  - {file_path.name} 无需翻译")

def main():
    """主函数"""
    locales_dir = Path(__file__).parent / 'src' / 'i18n' / 'locales'
    
    print("=" * 60)
    print("开始翻译多语言 i18n 文件")
    print("=" * 60)
    
    language_files = {
        'ja-JP.ts': 'ja-JP',
        'zh-Hant.ts': 'zh-Hant',
        'es-ES.ts': 'es-ES',
        'ru-RU.ts': 'ru-RU',
        'th-TH.ts': 'th-TH',
        'vi-VN.ts': 'vi-VN',
    }
    
    total_translated = 0
    for filename, lang_code in language_files.items():
        file_path = locales_dir / filename
        if file_path.exists():
            translate_file(file_path, lang_code)
            total_translated += 1
        else:
            print(f"\n警告: 文件不存在 - {filename}")
    
    print("\n" + "=" * 60)
    print("翻译完成！")
    print("=" * 60)
    print(f"\n已处理 {total_translated} 个语言文件")
    print(f"每个文件最多翻译 {len(TRANSLATIONS['ja-JP'])} 个键")

if __name__ == '__main__':
    main()
