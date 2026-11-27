import json

import httpx
import pytest  # type: ignore
from datetime import datetime
from langbot_plugin.api.entities.builtin.platform.message import (
    MessageChain,
    Plain,
    At,
    AtAll,
    Image,
    Face,
    Source,
    Quote,
    Forward,
    ForwardMessageNode,
    ForwardMessageDiaplay,
    _read_httpx_body_limited,
)


def test_message_chain_creation():
    """测试消息链的创建"""
    # 测试从组件列表创建
    chain = MessageChain([Plain(text="Hello"), At(target=123456)])
    assert len(chain) == 2
    assert isinstance(chain[0], Plain)
    assert isinstance(chain[1], At)
    assert chain[0].text == "Hello"
    assert chain[1].target == 123456

    # 测试无效输入
    with pytest.raises(ValueError):
        MessageChain("Hello")  # 不能直接传入字符串

    with pytest.raises(ValueError):
        MessageChain([123])  # 不能传入非 MessageComponent 类型


def test_message_chain_operations():
    """测试消息链的操作"""
    chain = MessageChain([Plain(text="Hello"), At(target=123456)])

    # 测试字符串表示
    assert str(chain) == "Hello@123456"

    # 测试索引访问
    assert isinstance(chain[0], Plain)
    assert isinstance(chain[1], At)

    # 测试切片
    sliced = chain[0:1]
    assert len(sliced) == 1
    assert isinstance(sliced[0], Plain)

    # 测试修改元素
    chain[0] = Plain(text="Hi")
    assert chain[0].text == "Hi"

    # 测试删除元素
    del chain[0]
    assert len(chain) == 1
    assert isinstance(chain[0], At)


def test_message_chain_list_operations():
    """测试消息链的列表操作"""
    chain = MessageChain([Plain(text="Hello")])

    # 测试 append
    chain.append(At(target=123456))
    assert len(chain) == 2
    assert isinstance(chain[1], At)

    # 测试 insert
    chain.insert(0, AtAll())
    assert len(chain) == 3
    assert isinstance(chain[0], AtAll)

    # 测试 extend
    chain.extend([Plain(text="World"), At(target=789012)])
    assert len(chain) == 5
    assert isinstance(chain[3], Plain)
    assert isinstance(chain[4], At)

    # 测试 pop
    component = chain.pop()
    assert isinstance(component, At)
    assert component.target == 789012

    # 测试 remove
    chain.remove(At(target=123456))
    assert len(chain) == 3

    # 测试 clear
    chain.clear()
    assert len(chain) == 0


def test_message_chain_concatenation():
    """测试消息链的连接操作"""
    chain1 = MessageChain([Plain(text="Hello")])
    chain2 = MessageChain([Plain(text="World")])

    # 测试加法操作
    result = chain1 + chain2
    assert len(result) == 2
    assert str(result) == "HelloWorld"

    # 测试原地加法操作
    chain1 += chain2
    assert len(chain1) == 2
    assert str(chain1) == "HelloWorld"


def test_quote_str():
    quote = Quote(id="1", origin=MessageChain([Plain(text="x")]))

    assert str(quote) == ""


@pytest.mark.parametrize("quote_first", [False, True])
@pytest.mark.parametrize("origin_text", [None, "quoted content"])
def test_message_chain_str_with_quote(quote_first, origin_text):
    origin = MessageChain([] if origin_text is None else [Plain(text=origin_text)])
    quote = Quote(id="1", origin=origin)
    plain = Plain(text="!help")
    chain = MessageChain([quote, plain] if quote_first else [plain, quote])

    assert str(chain) == "!help"


def test_quote_serialization():
    quote = Quote(
        id="1",
        group_id="group",
        sender_id="sender",
        target_id="target",
        origin=MessageChain([Plain(text="x")]),
    )
    expected = {
        "type": "Quote",
        "id": "1",
        "group_id": "group",
        "sender_id": "sender",
        "target_id": "target",
        "origin": [{"type": "Plain", "text": "x"}],
    }

    assert str(quote) == ""
    assert quote.model_dump() == expected
    assert json.loads(quote.model_dump_json()) == expected
    chain = MessageChain([quote])
    assert chain.model_dump() == [expected]
    assert json.loads(chain.model_dump_json()) == [expected]
    restored = MessageChain.model_validate(chain.model_dump())
    assert restored[0] == quote
    assert restored[0].origin[0].text == "x"


def test_message_chain_serialization():
    """测试消息链的序列化和反序列化"""
    # 创建一个包含多种组件的消息链
    current_time = datetime.now()
    original_chain = MessageChain(
        [
            Source(id=12345, time=current_time),
            Plain(text="Hello"),
            At(target=123456),
            AtAll(),
            Image(image_id="test_image_id", url="http://example.com/image.jpg"),
            Face(face_id=14, face_name="smile"),
            Quote(
                id=12345,
                group_id=67890,
                sender_id=11111,
                target_id=22222,
                origin=MessageChain([Plain(text="Original message")]),
            ),
        ]
    )

    # 序列化消息链
    serialized = original_chain.model_dump()

    # 反序列化消息链
    deserialized_chain = MessageChain.model_validate(serialized)

    # 验证反序列化后的消息链
    assert len(deserialized_chain) == len(original_chain)

    # 验证每个组件的类型和属性
    assert isinstance(deserialized_chain[0], Source)
    assert deserialized_chain[0].id == 12345
    assert isinstance(deserialized_chain[0].time, datetime)

    assert isinstance(deserialized_chain[1], Plain)
    assert deserialized_chain[1].text == "Hello"

    assert isinstance(deserialized_chain[2], At)
    assert deserialized_chain[2].target == 123456

    assert isinstance(deserialized_chain[3], AtAll)

    assert isinstance(deserialized_chain[4], Image)
    assert deserialized_chain[4].image_id == "test_image_id"
    assert str(deserialized_chain[4].url) == "http://example.com/image.jpg"

    assert isinstance(deserialized_chain[5], Face)
    assert deserialized_chain[5].face_id == 14

    assert isinstance(deserialized_chain[6], Quote)
    assert deserialized_chain[6].id == 12345
    assert deserialized_chain[6].group_id == 67890
    assert deserialized_chain[6].sender_id == 11111
    assert deserialized_chain[6].target_id == 22222
    assert isinstance(deserialized_chain[6].origin, MessageChain)
    assert deserialized_chain[6].origin[0].text == "Original message"


def test_message_chain_contains():
    """测试消息链的包含操作"""
    chain = MessageChain([Plain(text="Hello"), At(target=123456), AtAll()])

    # 测试类型检查
    assert Plain in chain
    assert At in chain
    assert AtAll in chain

    # 测试组件检查
    assert Plain(text="Hello") in chain
    assert At(target=123456) in chain
    assert At(target=789012) not in chain


def test_message_chain_with_source():
    """测试带源信息的消息链"""
    source = Source(id=12345, time=datetime.now())
    chain = MessageChain([source, Plain(text="Hello")])

    assert chain.source is not None
    assert chain.source.id == 12345
    assert chain.message_id == 12345


def test_message_chain_with_quote():
    """测试带引用的消息链"""
    quote = Quote(
        id=12345,
        group_id=67890,
        sender_id=11111,
        target_id=22222,
        origin=MessageChain([Plain(text="Original message")]),
    )
    chain = MessageChain([quote, Plain(text="Reply")])

    assert len(chain) == 2
    assert isinstance(chain[0], Quote)
    assert chain[0].id == 12345


def test_message_chain_with_forward():
    """测试带转发的消息链"""
    display = ForwardMessageDiaplay(
        title="Test Forward",
        brief="[Forward]",
        source="Test",
        preview=["Message 1", "Message 2"],
        summary="View 2 forwarded messages",
    )
    node = ForwardMessageNode(
        sender_id=12345,
        sender_name="Test User",
        message_chain=MessageChain([Plain(text="Test message")]),
        time=datetime.now(),
    )
    forward = Forward(display=display, node_list=[node])
    chain = MessageChain([forward])

    assert len(chain) == 1
    assert isinstance(chain[0], Forward)
    assert chain[0].display.title == "Test Forward"


def test_forward_message_chain_deserialization():
    """测试 Forward 消息的 node_list 中 message_chain 的反序列化"""
    # Simulate raw dict data as it would come over the wire (e.g. from plugin runtime)
    raw = [
        {
            "type": "Forward",
            "display": {
                "title": "Chat history",
                "brief": "[Chat history]",
                "source": "Chat history",
                "preview": [],
                "summary": "View 2 forwarded messages",
            },
            "node_list": [
                {
                    "sender_id": "111",
                    "sender_name": "Alice",
                    "message_chain": [
                        {"type": "Plain", "text": "Hello from Alice"},
                        {"type": "Image", "url": "http://example.com/a.png"},
                    ],
                    "message_id": 1,
                },
                {
                    "sender_id": "222",
                    "sender_name": "Bob",
                    "message_chain": [
                        {"type": "Plain", "text": "Hello from Bob"},
                    ],
                    "message_id": 2,
                },
            ],
        }
    ]

    chain = MessageChain.model_validate(raw)
    assert len(chain) == 1
    fwd = chain[0]
    assert isinstance(fwd, Forward)
    assert len(fwd.node_list) == 2

    # Verify nested message_chain is a proper MessageChain with typed components
    alice_mc = fwd.node_list[0].message_chain
    assert isinstance(alice_mc, MessageChain)
    assert len(alice_mc) == 2
    assert isinstance(alice_mc[0], Plain)
    assert alice_mc[0].text == "Hello from Alice"
    assert isinstance(alice_mc[1], Image)
    assert alice_mc[1].url == "http://example.com/a.png"

    bob_mc = fwd.node_list[1].message_chain
    assert isinstance(bob_mc, MessageChain)
    assert isinstance(bob_mc[0], Plain)
    assert bob_mc[0].text == "Hello from Bob"


def test_forward_roundtrip_serialization():
    """测试 Forward 消息的序列化/反序列化往返"""
    original = MessageChain(
        [
            Forward(
                display=ForwardMessageDiaplay(title="Test"),
                node_list=[
                    ForwardMessageNode(
                        sender_id="123",
                        sender_name="User",
                        message_chain=MessageChain([Plain(text="nested msg")]),
                    ),
                ],
            )
        ]
    )

    serialized = original.model_dump()
    deserialized = MessageChain.model_validate(serialized)

    fwd = deserialized[0]
    assert isinstance(fwd, Forward)
    assert isinstance(fwd.node_list[0].message_chain, MessageChain)
    assert isinstance(fwd.node_list[0].message_chain[0], Plain)
    assert fwd.node_list[0].message_chain[0].text == "nested msg"


def test_message_chain_with_image():
    """测试带图片的消息链"""
    image = Image(image_id="test_image_id", url="http://example.com/image.jpg")
    chain = MessageChain([image, Plain(text="Image description")])

    assert len(chain) == 2
    assert isinstance(chain[0], Image)
    assert chain[0].image_id == "test_image_id"


@pytest.mark.asyncio
async def test_image_remote_body_is_bounded():
    response = httpx.Response(200, content=b"oversized")

    with pytest.raises(ValueError, match="exceeds"):
        await _read_httpx_body_limited(response, max_bytes=4)


def test_message_chain_validation():
    """测试消息链的验证"""
    # 测试空消息链
    chain = MessageChain([])
    assert len(chain) == 0

    # 测试无效组件类型
    with pytest.raises(ValueError):
        MessageChain([123])  # 整数不是有效的消息组件


def test_person_message_received_serialization():
    """测试 PersonMessageReceived 事件的自动序列化"""
    from langbot_plugin.api.entities.events import PersonMessageReceived
    from langbot_plugin.api.entities.builtin.platform.message import (
        MessageChain,
        Plain,
        At,
    )
    from langbot_plugin.api.entities.builtin.platform.events import FriendMessage
    from langbot_plugin.api.entities.builtin.platform.entities import Friend

    # 创建一个消息链
    message_chain = MessageChain([Plain(text="Hello"), At(target=123456)])

    # 创建 PersonMessageReceived 事件
    event = PersonMessageReceived(
        launcher_type="person",
        launcher_id="123456",
        sender_id="789012",
        message_chain=message_chain,
        message_event=FriendMessage(
            sender=Friend(id="789012", nickname="Test", remark=""),
            message_chain=message_chain,
        ),
    )

    # 测试自动序列化
    serialized = event.model_dump()

    # 验证序列化结果
    assert serialized["launcher_type"] == "person"
    assert serialized["launcher_id"] == "123456"
    assert serialized["sender_id"] == "789012"
    assert "message_chain" in serialized

    # 验证 message_chain 被正确序列化
    message_chain_data = serialized["message_chain"]
    assert isinstance(message_chain_data, list)
    assert len(message_chain_data) == 2

    # 验证 Plain 组件
    assert message_chain_data[0]["type"] == "Plain"
    assert message_chain_data[0]["text"] == "Hello"

    # 验证 At 组件
    assert message_chain_data[1]["type"] == "At"
    assert message_chain_data[1]["target"] == 123456


def test_source_time_serialization():
    """测试 Source 组件的 time 字段序列化"""
    from langbot_plugin.api.entities.builtin.platform.message import (
        Source,
        MessageChain,
        Plain,
    )
    from datetime import datetime

    # 创建一个带时间的 Source 组件
    current_time = datetime.now()
    source = Source(id=12345, time=current_time)

    # 测试 Source 组件的序列化
    source_data = source.model_dump()

    # 验证 time 字段被正确序列化
    assert "timestamp" in source_data  # 使用 serialization_alias
    assert source_data["timestamp"] == int(current_time.timestamp())  # 使用整数时间戳

    # 测试在 MessageChain 中的序列化
    chain = MessageChain([source, Plain(text="Hello")])
    chain_data = chain.model_dump()

    # 验证 MessageChain 中的 Source 组件 time 字段被正确序列化
    assert len(chain_data) == 2
    assert chain_data[0]["type"] == "Source"
    assert "timestamp" in chain_data[0]
    assert chain_data[0]["timestamp"] == int(current_time.timestamp())  # 使用整数时间戳

    # 测试反序列化
    deserialized_source = Source.model_validate(source_data)
    # 由于时间戳转换可能损失精度，我们比较整数时间戳
    assert int(deserialized_source.time.timestamp()) == int(current_time.timestamp())


def test_person_message_received_with_source():
    """测试 PersonMessageReceived 事件中带有 Source 的 message_chain 的序列化和反序列化"""
    from langbot_plugin.api.entities.events import PersonMessageReceived
    from langbot_plugin.api.entities.builtin.platform.message import (
        MessageChain,
        Plain,
        Source,
    )
    from langbot_plugin.api.entities.builtin.platform.events import FriendMessage
    from langbot_plugin.api.entities.builtin.platform.entities import Friend
    from datetime import datetime

    current_time = datetime.now()
    source = Source(id=12345, time=current_time)
    message_chain = MessageChain([source, Plain(text="Hello")])

    event = PersonMessageReceived(
        launcher_type="person",
        launcher_id="123456",
        sender_id="789012",
        message_chain=message_chain,
        message_event=FriendMessage(
            sender=Friend(id="789012", nickname="Test", remark=""),
            message_chain=message_chain,
        ),
    )

    # 序列化
    serialized = event.model_dump()
    assert "message_chain" in serialized
    chain_data = serialized["message_chain"]
    assert isinstance(chain_data, list)
    assert chain_data[0]["type"] == "Source"
    assert chain_data[0]["timestamp"] == int(current_time.timestamp())
    assert chain_data[1]["type"] == "Plain"
    assert chain_data[1]["text"] == "Hello"

    # 反序列化
    from langbot_plugin.api.entities.events import PersonMessageReceived as PRcv

    deserialized_event = PRcv.model_validate(serialized)
    assert isinstance(deserialized_event.message_chain, MessageChain)
    assert isinstance(deserialized_event.message_chain[0], Source)
    assert int(deserialized_event.message_chain[0].time.timestamp()) == int(
        current_time.timestamp()
    )
    assert isinstance(deserialized_event.message_chain[1], Plain)
    assert deserialized_event.message_chain[1].text == "Hello"
