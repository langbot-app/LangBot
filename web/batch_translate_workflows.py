#!/usr/bin/env python3
"""
批量翻译workflows的多语言文件
支持：西班牙语(es-ES)、俄语(ru-RU)、泰语(th-TH)、越南语(vi-VN)
"""

import json
import os
from pathlib import Path
from typing import Dict

# 翻译映射表 - 基于中文原文的专业翻译
TRANSLATIONS = {
    # 基础UI文本
    "title": {
        "es-ES": "Conversación de Flujo de Trabajo",
        "ru-RU": "Диалог Рабочего Процесса",
        "th-TH": "การสนทนาเวิร์กโฟลว์",
        "vi-VN": "Hội thoại Quy trình"
    },
    "description": {
        "es-ES": "Descripción",
        "ru-RU": "Описание",
        "th-TH": "คำอธิบาย",
        "vi-VN": "Mô tả"
    },
    "createWorkflow": {
        "es-ES": "Crear Flujo de Trabajo",
        "ru-RU": "Создать Рабочий Процесс",
        "th-TH": "สร้างเวิร์กโฟลว์",
        "vi-VN": "Tạo Quy trình"
    },
    "selectFromSidebar": {
        "es-ES": "Seleccione un flujo de trabajo de la barra lateral",
        "ru-RU": "Выберите рабочий процесс из боковой панели",
        "th-TH": "เลือกเวิร์กโฟลว์จากแถบด้านข้าง",
        "vi-VN": "Chọn một quy trình từ thanh bên"
    },
    "editWorkflow": {
        "es-ES": "Editar Flujo de Trabajo",
        "ru-RU": "Редактировать Рабочий Процесс",
        "th-TH": "แก้ไขเวิร์กโฟลว์",
        "vi-VN": "Chỉnh sửa Quy trình"
    },
    "newWorkflow": {
        "es-ES": "Nuevo Flujo de Trabajo",
        "ru-RU": "Новый Рабочий Процесс",
        "th-TH": "เวิร์กโฟลว์ใหม่",
        "vi-VN": "Quy trình Mới"
    },
    "getWorkflowListError": {
        "es-ES": "Error al obtener la lista de flujos de trabajo:",
        "ru-RU": "Ошибка получения списка рабочих процессов:",
        "th-TH": "ไม่สามารถรับรายการเวิร์กโฟลว์:",
        "vi-VN": "Lỗi khi lấy danh sách quy trình:"
    },
    "workflowName": {
        "es-ES": "Nombre del Flujo de Trabajo",
        "ru-RU": "Название Рабочего Процесса",
        "th-TH": "ชื่อเวิร์กโฟลว์",
        "vi-VN": "Tên Quy trình"
    },
    "workflowDescription": {
        "es-ES": "Descripción del Flujo de Trabajo",
        "ru-RU": "Описание Рабочего Процесса",
        "th-TH": "คำอธิบายเวิร์กโฟลว์",
        "vi-VN": "Mô tả Quy trình"
    },
}


def load_translations_json():
    """加载翻译JSON文件"""
    json_path = Path(__file__).parent / 'workflows_translations.json'
    
    if not json_path.exists():
        raise FileNotFoundError(f"找不到翻译文件: {json_path}")
    
    with open(json_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_translations_json(data):
    """保存翻译JSON文件"""
    json_path = Path(__file__).parent / 'workflows_translations.json'
    
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def translate_text(text: str, target_lang: str) -> str:
    """
    翻译文本到目标语言
    使用规则和模式匹配进行翻译
    """
    # 如果有预定义翻译，直接使用
    if text in TRANSLATIONS and target_lang in TRANSLATIONS[text]:
        return TRANSLATIONS[text][target_lang]
    
    # 通用翻译规则
    common_translations = {
        "es-ES": {
            # 常用词汇
            "工作流": "Flujo de Trabajo",
            "节点": "Nodo",
            "触发器": "Disparador",
            "执行": "Ejecutar",
            "调试": "Depurar",
            "配置": "Configuración",
            "变量": "Variable",
            "条件": "Condición",
            "循环": "Bucle",
            "等待": "Esperar",
            "结束": "Fin",
            "开始": "Inicio",
            "消息": "Mensaje",
            "发送": "Enviar",
            "接收": "Recibir",
            "错误": "Error",
            "成功": "Éxito",
            "失败": "Fallo",
            "保存": "Guardar",
            "取消": "Cancelar",
            "删除": "Eliminar",
            "编辑": "Editar",
            "添加": "Agregar",
            "创建": "Crear",
            "名称": "Nombre",
            "描述": "Descripción",
            "类型": "Tipo",
            "值": "Valor",
            "参数": "Parámetro",
            "输入": "Entrada",
            "输出": "Salida",
            "请": "Por favor",
            "选择": "Seleccionar",
            "确认": "Confirmar",
            "提示": "Aviso",
            "警告": "Advertencia",
            "信息": "Información",
        },
        "ru-RU": {
            "工作流": "Рабочий Процесс",
            "节点": "Узел",
            "触发器": "Триггер",
            "执行": "Выполнить",
            "调试": "Отладка",
            "配置": "Конфигурация",
            "变量": "Переменная",
            "条件": "Условие",
            "循环": "Цикл",
            "等待": "Ожидание",
            "结束": "Конец",
            "开始": "Начало",
            "消息": "Сообщение",
            "发送": "Отправить",
            "接收": "Получить",
            "错误": "Ошибка",
            "成功": "Успех",
            "失败": "Неудача",
            "保存": "Сохранить",
            "取消": "Отмена",
            "删除": "Удалить",
            "编辑": "Редактировать",
            "添加": "Добавить",
            "创建": "Создать",
            "名称": "Название",
            "描述": "Описание",
            "类型": "Тип",
            "值": "Значение",
            "参数": "Параметр",
            "输入": "Вход",
            "输出": "Выход",
            "请": "Пожалуйста",
            "选择": "Выбрать",
            "确认": "Подтвердить",
            "提示": "Подсказка",
            "警告": "Предупреждение",
            "信息": "Информация",
        },
        "th-TH": {
            "工作流": "เวิร์กโฟลว์",
            "节点": "โหนด",
            "触发器": "ทริกเกอร์",
            "执行": "ดำเนินการ",
            "调试": "ดีบัก",
            "配置": "การกำหนดค่า",
            "变量": "ตัวแปร",
            "条件": "เงื่อนไข",
            "循环": "วนซ้ำ",
            "等待": "รอ",
            "结束": "สิ้นสุด",
            "开始": "เริ่มต้น",
            "消息": "ข้อความ",
            "发送": "ส่ง",
            "接收": "รับ",
            "错误": "ข้อผิดพลาด",
            "成功": "สำเร็จ",
            "失败": "ล้มเหลว",
            "保存": "บันทึก",
            "取消": "ยกเลิก",
            "删除": "ลบ",
            "编辑": "แก้ไข",
            "添加": "เพิ่ม",
            "创建": "สร้าง",
            "名称": "ชื่อ",
            "描述": "คำอธิบาย",
            "类型": "ประเภท",
            "值": "ค่า",
            "参数": "พารามิเตอร์",
            "输入": "อินพุต",
            "输出": "เอาต์พุต",
            "请": "กรุณา",
            "选择": "เลือก",
            "确认": "ยืนยัน",
            "提示": "คำแนะนำ",
            "警告": "คำเตือน",
            "信息": "ข้อมูล",
        },
        "vi-VN": {
            "工作流": "Quy trình",
            "节点": "Nút",
            "触发器": "Trình kích hoạt",
            "执行": "Thực thi",
            "调试": "Gỡ lỗi",
            "配置": "Cấu hình",
            "变量": "Biến",
            "条件": "Điều kiện",
            "循环": "Vòng lặp",
            "等待": "Chờ",
            "结束": "Kết thúc",
            "开始": "Bắt đầu",
            "消息": "Tin nhắn",
            "发送": "Gửi",
            "接收": "Nhận",
            "错误": "Lỗi",
            "成功": "Thành công",
            "失败": "Thất bại",
            "保存": "Lưu",
            "取消": "Hủy",
            "删除": "Xóa",
            "编辑": "Chỉnh sửa",
            "添加": "Thêm",
            "创建": "Tạo",
            "名称": "Tên",
            "描述": "Mô tả",
            "类型": "Loại",
            "值": "Giá trị",
            "参数": "Tham số",
            "输入": "Đầu vào",
            "输出": "Đầu ra",
            "请": "Vui lòng",
            "选择": "Chọn",
            "确认": "Xác nhận",
            "提示": "Gợi ý",
            "警告": "Cảnh báo",
            "信息": "Thông tin",
        }
    }
    
    # 尝试使用通用翻译规则
    if target_lang in common_translations:
        result = text
        for zh, translation in common_translations[target_lang].items():
            result = result.replace(zh, translation)
        if result != text:
            return result
    
    # 如果没有匹配的翻译规则，返回原文
    return text


def batch_translate():
    """批量翻译所有TODO项"""
    print("🚀 开始批量翻译workflows...")
    print("=" * 80)
    
    # 加载翻译数据
    data = load_translations_json()
    translations = data.get('translations', {})
    
    target_languages = ['es-ES', 'ru-RU', 'th-TH', 'vi-VN']
    
    stats = {lang: {'total': 0, 'translated': 0} for lang in target_languages}
    
    # 遍历所有键进行翻译
    for key, values in translations.items():
        zh_hans = values.get('zh-Hans', '')
        
        if not zh_hans or zh_hans == 'TODO':
            continue
        
        for lang in target_languages:
            stats[lang]['total'] += 1
            
            current_value = values.get(lang, 'TODO')
            
            # 如果已经翻译过，跳过
            if current_value != 'TODO' and current_value.strip():
                stats[lang]['translated'] += 1
                continue
            
            # 执行翻译
            translated = translate_text(zh_hans, lang)
            
            # 更新翻译
            if translated and translated != zh_hans:
                values[lang] = translated
                stats[lang]['translated'] += 1
                print(f"✅ [{lang}] {key}: {zh_hans} -> {translated}")
    
    # 保存更新后的数据
    save_translations_json(data)
    
    # 显示统计信息
    print("\n" + "=" * 80)
    print("📊 翻译统计:")
    print("=" * 80)
    
    for lang in target_languages:
        total = stats[lang]['total']
        translated = stats[lang]['translated']
        percentage = (translated / total * 100) if total > 0 else 0
        
        lang_names = {
            'es-ES': '西班牙语',
            'ru-RU': '俄语',
            'th-TH': '泰语',
            'vi-VN': '越南语'
        }
        
        print(f"\n【{lang_names[lang]} ({lang})】")
        print(f"  总计: {total}")
        print(f"  已翻译: {translated}")
        print(f"  完成度: {percentage:.1f}%")
    
    print("\n" + "=" * 80)
    print("✅ 批量翻译完成！")
    print("\n💡 下一步:")
    print("   1. 运行 python3 check_translation_progress.py 查看进度")
    print("   2. 运行 python3 apply_workflows_translations.py 应用翻译")
    print("=" * 80)


if __name__ == '__main__':
    try:
        batch_translate()
    except Exception as e:
        print(f"\n❌ 错误: {e}")
        import traceback
        traceback.print_exc()
