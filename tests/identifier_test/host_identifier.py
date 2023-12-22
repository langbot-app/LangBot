import os
import uuid
import json

# 向 ~/.qchatgpt 写入一个 标识符

if not os.path.exists(os.path.expanduser('~/.qchatgpt')):
    os.mkdir(os.path.expanduser('~/.qchatgpt'))

identifier = {
    "host_id": "host_"+str(uuid.uuid4()),
}

if not os.path.exists(os.path.expanduser('~/.qchatgpt/host.json')):
    print('create ~/.qchatgpt/host.json')
    with open(os.path.expanduser('~/.qchatgpt/host.json'), 'w') as f:
        json.dump(identifier, f)
else:
    print('load ~/.qchatgpt/host.json')
    with open(os.path.expanduser('~/.qchatgpt/host.json'), 'r') as f:
        identifier = json.load(f)

print(identifier)

instance_id = {
    "host_id": identifier['host_id'],
    "instance_id": "instance_"+str(uuid.uuid4()),
}

# 实例 id
if os.path.exists("res/instance_id.json"):
    with open("res/instance_id.json", 'r') as f:
        instance_id = json.load(f)
    
    if instance_id['host_id'] != identifier['host_id']:
        os.remove("res/instance_id.json")

if not os.path.exists("res/instance_id.json"):
    print('create res/instance_id.json')
    with open("res/instance_id.json", 'w') as f:
        json.dump(instance_id, f)

print(instance_id)