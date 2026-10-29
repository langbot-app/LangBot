#!/usr/bin/env python3
"""WebSocket test client for LangBot GroupChatSummary plugin debugging."""

import asyncio
import json
import sys
import time

try:
    import websockets
except ImportError:
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "websockets", "-q"])
    import websockets


LB_HOST = "us-ca-cloudcone-04.rockchin.top"
LB_PORT = 5310
PIPELINE_UUID = "48963ec3-5f45-4078-a81e-ce0c569566fd"
WS_URL = f"ws://{LB_HOST}:{LB_PORT}/api/v1/pipelines/{PIPELINE_UUID}/ws/connect"


async def test_group_chat_summary():
    """Test the GroupChatSummary plugin by simulating group chat messages."""
    
    # Connect as group session
    url = f"{WS_URL}?session_type=group"
    print(f"Connecting to {url}")
    
    async with websockets.connect(url) as ws:
        # Wait for connected message
        msg = await asyncio.wait_for(ws.recv(), timeout=10)
        data = json.loads(msg)
        print(f"[RECV] {json.dumps(data, indent=2)}")
        
        if data.get("type") != "connected":
            print(f"ERROR: Expected 'connected', got '{data.get('type')}'")
            return
        
        connection_id = data.get("connection_id")
        print(f"Connected! ID: {connection_id}\n")
        
        # Simulate group chat messages from different users
        test_messages = [
            {"sender": "Alice", "text": "大家好，今天的会议几点开始？"},
            {"sender": "Bob", "text": "下午3点，讨论新版本的发布计划"},
            {"sender": "Charlie", "text": "好的，我准备了性能测试报告"},
            {"sender": "Alice", "text": "Bob你那边CI/CD流程改好了吗"},
            {"sender": "Bob", "text": "改好了，现在自动部署到staging了"},
            {"sender": "David", "text": "我觉得我们应该先修复那个内存泄漏的问题"},
            {"sender": "Charlie", "text": "同意，内存泄漏在高并发下会导致OOM"},
            {"sender": "Alice", "text": "那就优先级调高，这个版本必须修"},
            {"sender": "Bob", "text": "我来负责修这个，预计需要两天"},
            {"sender": "David", "text": "我可以帮忙review代码"},
        ]
        
        for i, msg_data in enumerate(test_messages):
            message = {
                "type": "message",
                "content": msg_data["text"],
                "sender_name": msg_data["sender"],
            }
            await ws.send(json.dumps(message))
            print(f"[SENT] [{msg_data['sender']}]: {msg_data['text']}")
            
            # Receive any responses
            try:
                while True:
                    resp = await asyncio.wait_for(ws.recv(), timeout=2)
                    resp_data = json.loads(resp)
                    print(f"  [RECV] {json.dumps(resp_data, ensure_ascii=False)[:200]}")
            except asyncio.TimeoutError:
                pass
            
            await asyncio.sleep(0.5)
        
        print("\n--- Sending summary command ---")
        # Try the !summary command
        summary_msg = {
            "type": "message",
            "content": "!summary",
        }
        await ws.send(json.dumps(summary_msg))
        print(f"[SENT] !summary")
        
        # Wait for summary response
        try:
            while True:
                resp = await asyncio.wait_for(ws.recv(), timeout=30)
                resp_data = json.loads(resp)
                print(f"  [RECV] {json.dumps(resp_data, ensure_ascii=False)[:500]}")
        except asyncio.TimeoutError:
            print("  [TIMEOUT] No more responses")
        
        print("\n--- Sending natural language summary request ---")
        # Try asking for summary via normal message (tool call)
        nl_msg = {
            "type": "message",
            "content": "请帮我总结一下刚才群聊的内容",
        }
        await ws.send(json.dumps(nl_msg))
        print(f"[SENT] 请帮我总结一下刚才群聊的内容")
        
        try:
            while True:
                resp = await asyncio.wait_for(ws.recv(), timeout=30)
                resp_data = json.loads(resp)
                print(f"  [RECV] {json.dumps(resp_data, ensure_ascii=False)[:500]}")
        except asyncio.TimeoutError:
            print("  [TIMEOUT] No more responses")
        
        print("\nDone!")


if __name__ == "__main__":
    asyncio.run(test_group_chat_summary())
