#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI翻译工作流i18n - 使用完整短语翻译而非词汇替换
"""

import json
import re
from typing import Dict, List

def has_chinese(text: str) -> bool:
    """检查文本是否包含中文字符"""
    return bool(re.search(r'[\u4e00-\u9fff]', text))

def load_translations() -> Dict:
    """加载翻译文件"""
    with open('workflows_translations.json', 'r', encoding='utf-8') as f:
        return json.load(f)

def save_translations(data: Dict):
    """保存翻译文件"""
    with open('workflows_translations.json', 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# 完整短语翻译字典 - 第一批（基础UI和操作）
TRANSLATIONS_BATCH_1 = {
    # 基础操作
    "工作流": {"es-ES": "Flujo de trabajo", "ru-RU": "Рабочий процесс", "th-TH": "เวิร์กโฟลว์", "vi-VN": "Quy trình làm việc"},
    "节点": {"es-ES": "Nodo", "ru-RU": "Узел", "th-TH": "โหนด", "vi-VN": "Nút"},
    "创建工作流": {"es-ES": "Crear flujo de trabajo", "ru-RU": "Создать рабочий процесс", "th-TH": "สร้างเวิร์กโฟลว์", "vi-VN": "Tạo quy trình làm việc"},
    "从侧边栏选择": {"es-ES": "Seleccionar desde la barra lateral", "ru-RU": "Выбрать из боковой панели", "th-TH": "เลือกจากแถบด้านข้าง", "vi-VN": "Chọn từ thanh bên"},
    "编辑工作流": {"es-ES": "Editar flujo de trabajo", "ru-RU": "Редактировать рабочий процесс", "th-TH": "แก้ไขเวิร์กโฟลว์", "vi-VN": "Chỉnh sửa quy trình làm việc"},
    "新建工作流": {"es-ES": "Nuevo flujo de trabajo", "ru-RU": "Новый рабочий процесс", "th-TH": "เวิร์กโฟลว์ใหม่", "vi-VN": "Quy trình làm việc mới"},
    "获取工作流列表失败": {"es-ES": "Error al obtener la lista de flujos de trabajo", "ru-RU": "Не удалось получить список рабочих процессов", "th-TH": "ไม่สามารถรับรายการเวิร์กโฟลว์", "vi-VN": "Không thể lấy danh sách quy trình làm việc"},
    "工作流名称": {"es-ES": "Nombre del flujo de trabajo", "ru-RU": "Название рабочего процесса", "th-TH": "ชื่อเวิร์กโฟลว์", "vi-VN": "Tên quy trình làm việc"},
    "工作流描述": {"es-ES": "Descripción del flujo de trabajo", "ru-RU": "Описание рабочего процесса", "th-TH": "คำอธิบายเวิร์กโฟลว์", "vi-VN": "Mô tả quy trình làm việc"},
    "工作流名称不能为空": {"es-ES": "El nombre del flujo de trabajo no puede estar vacío", "ru-RU": "Название рабочего процесса не может быть пустым", "th-TH": "ชื่อเวิร์กโฟลว์ไม่สามารถว่างเปล่า", "vi-VN": "Tên quy trình làm việc không được để trống"},
    "默认工作流描述": {"es-ES": "Descripción predeterminada del flujo de trabajo", "ru-RU": "Описание рабочего процесса по умолчанию", "th-TH": "คำอธิบายเวิร์กโฟลว์เริ่มต้น", "vi-VN": "Mô tả quy trình làm việc mặc định"},
    
    # 成功/失败消息
    "保存成功": {"es-ES": "Guardado exitosamente", "ru-RU": "Успешно сохранено", "th-TH": "บันทึกสำเร็จ", "vi-VN": "Lưu thành công"},
    "保存失败": {"es-ES": "Error al guardar", "ru-RU": "Не удалось сохранить", "th-TH": "บันทึกล้มเหลว", "vi-VN": "Lưu thất bại"},
    "创建成功": {"es-ES": "Creado exitosamente", "ru-RU": "Успешно создано", "th-TH": "สร้างสำเร็จ", "vi-VN": "Tạo thành công"},
    "创建失败": {"es-ES": "Error al crear", "ru-RU": "Не удалось создать", "th-TH": "สร้างล้มเหลว", "vi-VN": "Tạo thất bại"},
    "删除成功": {"es-ES": "Eliminado exitosamente", "ru-RU": "Успешно удалено", "th-TH": "ลบสำเร็จ", "vi-VN": "Xóa thành công"},
    "删除失败": {"es-ES": "Error al eliminar", "ru-RU": "Не удалось удалить", "th-TH": "ลบล้มเหลว", "vi-VN": "Xóa thất bại"},
    "复制成功": {"es-ES": "Copiado exitosamente", "ru-RU": "Успешно скопировано", "th-TH": "คัดลอกสำเร็จ", "vi-VN": "Sao chép thành công"},
    "复制失败": {"es-ES": "Error al copiar", "ru-RU": "Не удалось скопировать", "th-TH": "คัดลอกล้มเหลว", "vi-VN": "Sao chép thất bại"},
    "导出成功": {"es-ES": "Exportado exitosamente", "ru-RU": "Успешно экспортировано", "th-TH": "ส่งออกสำเร็จ", "vi-VN": "Xuất thành công"},
    "导入成功": {"es-ES": "Importado exitosamente", "ru-RU": "Успешно импортировано", "th-TH": "นำเข้าสำเร็จ", "vi-VN": "Nhập thành công"},
    "导入失败": {"es-ES": "Error al importar", "ru-RU": "Не удалось импортировать", "th-TH": "นำเข้าล้มเหลว", "vi-VN": "Nhập thất bại"},
    "发布成功": {"es-ES": "Publicado exitosamente", "ru-RU": "Успешно опубликовано", "th-TH": "เผยแพร่สำเร็จ", "vi-VN": "Xuất bản thành công"},
    "发布失败": {"es-ES": "Error al publicar", "ru-RU": "Не удалось опубликовать", "th-TH": "เผยแพร่ล้มเหลว", "vi-VN": "Xuất bản thất bại"},
    "获取工作流失败": {"es-ES": "Error al obtener el flujo de trabajo", "ru-RU": "Не удалось получить рабочий процесс", "th-TH": "ไม่สามารถรับเวิร์กโฟลว์", "vi-VN": "Không thể lấy quy trình làm việc"},
    "加载失败": {"es-ES": "Error al cargar", "ru-RU": "Не удалось загрузить", "th-TH": "โหลดล้มเหลว", "vi-VN": "Tải thất bại"},
    
    # 确认对话框
    "确认删除": {"es-ES": "Confirmar eliminación", "ru-RU": "Подтвердить удаление", "th-TH": "ยืนยันการลบ", "vi-VN": "Xác nhận xóa"},
    "确认删除此工作流吗？": {"es-ES": "¿Confirmar la eliminación de este flujo de trabajo?", "ru-RU": "Подтвердить удаление этого рабочего процесса?", "th-TH": "ยืนยันการลบเวิร์กโฟลว์นี้หรือไม่?", "vi-VN": "Xác nhận xóa quy trình làm việc này?"},
    
    # 基本操作
    "导出": {"es-ES": "Exportar", "ru-RU": "Экспорт", "th-TH": "ส่งออก", "vi-VN": "Xuất"},
    "导入": {"es-ES": "Importar", "ru-RU": "Импорт", "th-TH": "นำเข้า", "vi-VN": "Nhập"},
    "发布": {"es-ES": "Publicar", "ru-RU": "Опубликовать", "th-TH": "เผยแพร่", "vi-VN": "Xuất bản"},
    "配置": {"es-ES": "Configuración", "ru-RU": "Конфигурация", "th-TH": "การกำหนดค่า", "vi-VN": "Cấu hình"},
    "执行记录": {"es-ES": "Registros de ejecución", "ru-RU": "Записи выполнения", "th-TH": "บันทึกการดำเนินการ", "vi-VN": "Bản ghi thực thi"},
    "编辑器": {"es-ES": "Editor", "ru-RU": "Редактор", "th-TH": "ตัวแก้ไข", "vi-VN": "Trình chỉnh sửa"},
    "调试聊天": {"es-ES": "Chat de depuración", "ru-RU": "Отладочный чат", "th-TH": "แชทดีบัก", "vi-VN": "Chat gỡ lỗi"},
    
    # 配置部分
    "基本信息": {"es-ES": "Información básica", "ru-RU": "Основная информация", "th-TH": "ข้อมูลพื้นฐาน", "vi-VN": "Thông tin cơ bản"},
    "基本信息描述": {"es-ES": "Descripción de información básica", "ru-RU": "Описание основной информации", "th-TH": "คำอธิบายข้อมูลพื้นฐาน", "vi-VN": "Mô tả thông tin cơ bản"},
    "危险区域": {"es-ES": "Zona peligrosa", "ru-RU": "Опасная зона", "th-TH": "พื้นที่อันตราย", "vi-VN": "Khu vực nguy hiểm"},
    "危险区域描述": {"es-ES": "Descripción de zona peligrosa", "ru-RU": "Описание опасной зоны", "th-TH": "คำอธิบายพื้นที่อันตราย", "vi-VN": "Mô tả khu vực nguy hiểm"},
    "删除工作流操作": {"es-ES": "Eliminar operación de flujo de trabajo", "ru-RU": "Удалить операцию рабочего процесса", "th-TH": "ลบการดำเนินการเวิร์กโฟลว์", "vi-VN": "Xóa thao tác quy trình làm việc"},
    "删除工作流提示": {"es-ES": "Sugerencia de eliminación de flujo de trabajo", "ru-RU": "Подсказка удаления рабочего процесса", "th-TH": "คำแนะนำการลบเวิร์กโฟลว์", "vi-VN": "Gợi ý xóa quy trình làm việc"},
    "删除工作流": {"es-ES": "Eliminar flujo de trabajo", "ru-RU": "Удалить рабочий процесс", "th-TH": "ลบเวิร์กโฟลว์", "vi-VN": "Xóa quy trình làm việc"},
    "删除确认描述": {"es-ES": "Descripción de confirmación de eliminación", "ru-RU": "Описание подтверждения удаления", "th-TH": "คำอธิบายการยืนยันการลบ", "vi-VN": "Mô tả xác nhận xóa"},
    
    # 表单字段
    "名称": {"es-ES": "Nombre", "ru-RU": "Название", "th-TH": "ชื่อ", "vi-VN": "Tên"},
    "名称占位符": {"es-ES": "Marcador de posición de nombre", "ru-RU": "Заполнитель имени", "th-TH": "ตัวยึดตำแหน่งชื่อ", "vi-VN": "Trình giữ chỗ tên"},
    "描述占位符": {"es-ES": "Marcador de posición de descripción", "ru-RU": "Заполнитель описания", "th-TH": "ตัวยึดตำแหน่งคำอธิบาย", "vi-VN": "Trình giữ chỗ mô tả"},
    "已启用": {"es-ES": "Habilitado", "ru-RU": "Включено", "th-TH": "เปิดใช้งาน", "vi-VN": "Đã bật"},
    "已启用描述": {"es-ES": "Descripción habilitada", "ru-RU": "Описание включено", "th-TH": "คำอธิบายเปิดใช้งาน", "vi-VN": "Mô tả đã bật"},
    "加载中": {"es-ES": "Cargando", "ru-RU": "Загрузка", "th-TH": "กำลังโหลด", "vi-VN": "Đang tải"},
    "信息": {"es-ES": "Información", "ru-RU": "Информация", "th-TH": "ข้อมูล", "vi-VN": "Thông tin"},
    
    # 统计信息
    "版本": {"es-ES": "Versión", "ru-RU": "Версия", "th-TH": "เวอร์ชัน", "vi-VN": "Phiên bản"},
    "创建时间": {"es-ES": "Tiempo de creación", "ru-RU": "Время создания", "th-TH": "เวลาสร้าง", "vi-VN": "Thời gian tạo"},
    "更新时间": {"es-ES": "Tiempo de actualización", "ru-RU": "Время обновления", "th-TH": "เวลาอัปเดต", "vi-VN": "Thời gian cập nhật"},
    "总执行次数": {"es-ES": "Total de ejecuciones", "ru-RU": "Всего выполнений", "th-TH": "จำนวนการดำเนินการทั้งหมด", "vi-VN": "Tổng số lần thực thi"},
    "统计": {"es-ES": "Estadísticas", "ru-RU": "Статистика", "th-TH": "สถิติ", "vi-VN": "Thống kê"},
    "成功次数": {"es-ES": "Número de éxitos", "ru-RU": "Количество успехов", "th-TH": "จำนวนความสำเร็จ", "vi-VN": "Số lần thành công"},
    "成功率": {"es-ES": "Tasa de éxito", "ru-RU": "Процент успеха", "th-TH": "อัตราความสำเร็จ", "vi-VN": "Tỷ lệ thành công"},
    "平均耗时": {"es-ES": "Duración promedio", "ru-RU": "Средняя продолжительность", "th-TH": "ระยะเวลาเฉลี่ย", "vi-VN": "Thời gian trung bình"},
    "每次执行": {"es-ES": "Por ejecución", "ru-RU": "За выполнение", "th-TH": "ต่อการดำเนินการ", "vi-VN": "Mỗi lần thực thi"},
    "失败的执行": {"es-ES": "Ejecuciones fallidas", "ru-RU": "Неудачные выполнения", "th-TH": "การดำเนินการที่ล้มเหลว", "vi-VN": "Các lần thực thi thất bại"},
    "最后执行": {"es-ES": "Última ejecución", "ru-RU": "Последнее выполнение", "th-TH": "การดำเนินการล่าสุด", "vi-VN": "Lần thực thi cuối"},
}

def translate_batch(data: Dict, translations: Dict[str, Dict[str, str]]):
    """应用一批翻译"""
    count = 0
    for key, trans_obj in data['translations'].items():
        zh_text = trans_obj.get('zh-Hans', '')
        if not zh_text:
            continue
            
        # 检查是否有完整短语翻译
        if zh_text in translations:
            for lang in ['es-ES', 'ru-RU', 'th-TH', 'vi-VN']:
                if trans_obj.get(lang) == 'TODO':
                    trans_obj[lang] = translations[zh_text][lang]
                    count += 1
    
    return count

def main():
    print("🚀 开始AI翻译工作流i18n...")
    
    # 加载数据
    data = load_translations()
    
    # 应用第一批翻译
    print("\n📝 应用第一批翻译（基础UI和操作）...")
    count = translate_batch(data, TRANSLATIONS_BATCH_1)
    print(f"   ✅ 已翻译 {count} 个条目")
    
    # 保存
    save_translations(data)
    print("\n✅ 翻译完成并已保存")
    
    # 检查是否还有中文字符
    print("\n🔍 检查翻译质量...")
    problem_count = 0
    for key, trans_obj in data['translations'].items():
        for lang in ['es-ES', 'ru-RU', 'th-TH', 'vi-VN']:
            text = trans_obj.get(lang, '')
            if text != 'TODO' and has_chinese(text):
                problem_count += 1
                print(f"   ⚠️  {key} ({lang}): {text}")
    
    if problem_count == 0:
        print("   ✅ 所有翻译都不包含中文字符")
    else:
        print(f"   ⚠️  发现 {problem_count} 个翻译仍包含中文字符")

if __name__ == '__main__':
    main()
