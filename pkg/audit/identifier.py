# 实例 识别码 控制

import os
import uuid
import json
import time


identifier = {
    'host_id': '',
    'instance_id': '',
    'host_create_ts': 0,
    'instance_create_ts': 0,
}

HOST_ID_FILE = os.path.expanduser('~/.qchatgpt/host_id.json')
INSTANCE_ID_FILE = 'res/instance_id.json'

def init():
    global identifier

    if not os.path.exists(os.path.expanduser('~/.qchatgpt')):
        os.mkdir(os.path.expanduser('~/.qchatgpt'))

    if not os.path.exists(HOST_ID_FILE):
        new_host_id = 'host_'+str(uuid.uuid4())
        new_host_create_ts = int(time.time())

        with open(HOST_ID_FILE, 'w') as f:
            json.dump({
                'host_id': new_host_id,
                'host_create_ts': new_host_create_ts
            }, f)

        identifier['host_id'] = new_host_id
        identifier['host_create_ts'] = new_host_create_ts
    else:
        loaded_host_id = ''
        loaded_host_create_ts = 0

        with open(HOST_ID_FILE, 'r') as f:
            file_content = json.load(f)
            loaded_host_id = file_content['host_id']
            loaded_host_create_ts = file_content['host_create_ts']

        identifier['host_id'] = loaded_host_id
        identifier['host_create_ts'] = loaded_host_create_ts

    # 检查实例 id
    if os.path.exists(INSTANCE_ID_FILE):
        instance_id = {}
        with open(INSTANCE_ID_FILE, 'r') as f:
            instance_id = json.load(f)
        
        if instance_id['host_id'] != identifier['host_id']: # 如果实例 id 不是当前主机的，删除
            os.remove(INSTANCE_ID_FILE)

    if not os.path.exists(INSTANCE_ID_FILE):
        new_instance_id = 'instance_'+str(uuid.uuid4())
        new_instance_create_ts = int(time.time())

        with open(INSTANCE_ID_FILE, 'w') as f:
            json.dump({
                'host_id': identifier['host_id'],
                'instance_id': new_instance_id,
                'instance_create_ts': new_instance_create_ts
            }, f)

        identifier['instance_id'] = new_instance_id
        identifier['instance_create_ts'] = new_instance_create_ts
    else:
        loaded_instance_id = ''
        loaded_instance_create_ts = 0

        with open(INSTANCE_ID_FILE, 'r') as f:
            file_content = json.load(f)
            loaded_instance_id = file_content['instance_id']
            loaded_instance_create_ts = file_content['instance_create_ts']

        identifier['instance_id'] = loaded_instance_id
        identifier['instance_create_ts'] = loaded_instance_create_ts

def print_out():
    global identifier
    print(identifier)
