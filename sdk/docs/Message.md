# MessageChain 使用指南

`MessageChain` 是一个用于处理消息组件的容器类，它提供了一系列便捷的操作方法来管理消息组件。

## 基本概念

`MessageChain` 是一个消息组件的列表，每个组件都是 `MessageComponent` 的子类。常见的消息组件包括：

- `Plain`: 纯文本消息
- `At`: @某人
- `AtAll`: @所有人
- `Image`: 图片
- `Quote`: 引用消息
- `Source`: 消息源信息
- `Forward`: 合并转发消息

## 创建消息链

`MessageChain` 只能通过 `MessageComponent` 列表创建：

```python
from langbot_plugin.api.entities.builtin.platform.message import MessageChain, Plain, At

# 创建一个包含文本和@的消息链
chain = MessageChain([
    Plain("Hello"),
    At(123456)
])
```

## 基本操作

### 访问元素

```python
# 获取第一个元素
first = chain[0]  # 返回 Plain("Hello")

# 切片操作
part = chain[0:1]  # 返回包含第一个元素的列表
```

### 修改元素

```python
# 修改元素
chain[0] = Plain("Hi")  # 将第一个元素改为 "Hi"

# 删除元素
del chain[0]  # 删除第一个元素
```

### 添加元素

```python
# 在末尾添加元素
chain.append(Plain("World"))

# 在指定位置插入元素
chain.insert(0, AtAll())

# 在末尾添加多个元素
chain.extend([Plain("!"), At(789012)])
```

### 删除元素

```python
# 移除并返回最后一个元素
last = chain.pop()

# 移除指定元素
chain.remove(At(123456))

# 清空消息链
chain.clear()
```

### 连接操作

```python
# 连接两个消息链
chain1 = MessageChain([Plain("Hello")])
chain2 = MessageChain([Plain("World")])
result = chain1 + chain2  # 返回新的消息链

# 原地连接
chain1 += chain2  # 修改 chain1
```

## 序列化和反序列化

```python
# 序列化
serialized = chain.model_dump()

# 反序列化
deserialized = MessageChain.model_validate(serialized)
```

## 注意事项

1. `MessageChain` 只能包含 `MessageComponent` 类型的元素
2. 不能直接传入字符串或其他类型来创建消息链
3. 所有修改操作都会进行类型检查，确保只能操作 `MessageComponent` 类型的元素

## 示例

### 创建一个复杂的消息链

```python
from datetime import datetime
from langbot_plugin.api.entities.builtin.platform.message import (
    MessageChain, Plain, At, AtAll, Image, Source, Quote
)

# 创建一个包含多种组件的消息链
chain = MessageChain([
    Source(id=12345, time=datetime.now()),
    Plain("Hello"),
    At(123456),
    AtAll(),
    Image(image_id="test_image_id", url="http://example.com/image.jpg"),
    Quote(
        id=12345,
        group_id=67890,
        sender_id=11111,
        target_id=22222,
        origin=MessageChain([Plain("Original message")])
    )
])
```

### 处理消息链

```python
# 获取消息链的字符串表示
text = str(chain)  # 例如: "Hello@123456@All[Image]"

# 遍历消息链
for component in chain:
    print(type(component), component)

# 修改消息链
chain[1] = Plain("Hi")  # 修改文本
chain.append(At(789012))  # 添加新的@
``` 