# 输出工作路径
import os
import time
import json

print('工作路径: ' + os.getcwd())
announcement = input('请输入公告内容: ')

# 读取现有的公告文件 res/announcement.json
with open('res/announcement.json', 'r', encoding='utf-8') as f:
    announcement_json = json.load(f)

# 将公告内容写入公告文件

# 当前自然时间
now = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())

# 获取最后一个公告的id
last_id = announcement_json[-1]['id'] if len(announcement_json) > 0 else -1

announcement = {
    'id': last_id + 1,
    'time': now,
    'timestamp': int(time.time()),
    'content': announcement,
}

announcement_json.append(announcement)

# 将公告写入公告文件
with open('res/announcement.json', 'w', encoding='utf-8') as f:
    json.dump(announcement_json, f, indent=4, ensure_ascii=False)
