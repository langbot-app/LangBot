"""WO-LINE-05 多模態／Flex Message 测试（boxed 无 SDK 依赖）。

跑法（repo 环境，据 WO-LINE-02 selftest 惯例）：
    cd <repo>/src/langbot
    python -m pkg.platform.adapters.line.test_multimodal_flex

覆盖：
  - send_api 纯量构筑（Bubble / Carousel / 按钮 / flex 物件）—— 恒测（无框架）。
  - message_converter.target2yiri image.received（download_message_content）
    —— repo 框架就位时才测。
  - message_converter.yiri2target flex PlatformComponent → 单一 flex 讯息。
  - adapter.get_supported_events / get_supported_apis 宣告 image.received / flex.send。
"""

import importlib
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_results = []


def check(name, cond, detail=""):
    _results.append((name, bool(cond)))
    print(f"[{'PASS' if cond else 'FAIL'}] {name}" + (f"  :: {detail}" if detail else ""))


def _summary():
    passed = sum(1 for _, ok in _results if ok)
    total = len(_results)
    print(f"\n===== WO-LINE-05 測試摘要：{passed}/{total} PASS =====")
    return passed == total


# ==========================================================================
# 1）send_api 純量構築（恒测：本檔无 framework 依赖，直接按档载入）
# ==========================================================================
def _load_standalone(modname):
    path = os.path.join(_HERE, modname + ".py")
    spec = importlib.util.spec_from_file_location(f"line_staged_{modname}", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


send_api = _load_standalone("send_api")

body = send_api.FlexBox(
    "vertical",
    [
        send_api.FlexText("標題", weight="bold", size="lg"),
        send_api.FlexText("內文"),
    ],
    spacing="md",
)
bubble = send_api.FlexBubble(body=body)
check("bubble_type", bubble.get("type") == "bubble", str(bubble.get("type")))
check("bubble_has_body", "body" in bubble)
check("bubble_has_contents", "contents" in bubble["body"])

carousel = send_api.FlexCarousel([bubble, send_api.FlexBubble(body=send_api.FlexBox("vertical", [send_api.FlexText("B")]))])
check("carousel_type", carousel.get("type") == "carousel")
check("carousel_contents_len", len(carousel["contents"]) == 2, str(len(carousel["contents"])))

fb = send_api.FlexButton(
    send_api.FlexPostbackAction("確定", "action=confirm", display_text="你點了確定"),
    style="primary",
)
check("button_type", fb["type"] == "button")
check("postback_action", fb["action"]["type"] == "postback" and fb["action"]["data"] == "action=confirm")

mb = send_api.FlexButton(send_api.FlexMessageAction("選取", "選取"))
check("message_action", mb["action"]["type"] == "message" and mb["action"]["text"] == "選取")

img = send_api.FlexImage("https://example.com/a.jpg", aspect_ratio="1:1")
check("image_component", img["type"] == "image" and img.get("aspectRatio") == "1:1")

obj = send_api.flex_message_object(bubble)
check("flex_message_type", obj.get("type") == "flex", str(obj.get("type")))
check("flex_content_type", obj.get("contentType") == "application/json")
check("flex_data", obj.get("data") is bubble)
check("flex_list_len", len(send_api.flex_message_list(bubble)) == 1)

# ==========================================================================
# 2）message_converter / adapter（据 repo 环境决定测或不测）
# ==========================================================================
linemod = adapter_mod = platform_message_cls = adapter_cls = None
try:
    linemod = importlib.import_module("pkg.platform.adapters.line.message_converter")
    adapter_mod = importlib.import_module("pkg.platform.adapters.line.adapter")
    adapter_cls = adapter_mod.LineAdapter
    platform_message_cls = linemod.platform_message
except Exception as exc:  # repo 框架未就位 → 跳过
    print(f"[SKIP] message_converter/adapter（repo 框架未就位：{exc!r}）")


if linemod is not None:
    import asyncio

    class _FakeContentProvider:
        def get(self, message_id, *a, **k):
            return b"fake-image-bytes"

    async def _run_image():
        lc = linemod.LineMessageConverter()
        return await lc.target2yiri(
            {"type": "image", "id": "msg-123", "timestamp": "1700000000000"},
            content_provider=_FakeContentProvider(),
        )

    try:
        chain = asyncio.run(_run_image())
        imgs = [c for c in chain if type(c).__name__ == "Image"]
        check("image_received_len", len(imgs) == 1, f"imgs={len(imgs)}")
        check("image_data_uri", bool(imgs) and imgs[0].base64.startswith("data:image/jpeg;base64,"),
              imgs[0].base64[:40] if imgs else "")
    except Exception as exc:
        check("image_received", False, repr(exc))

    # flex：MessageChain 含 flex PlatformComponent → 单一 flex 讯息
    try:
        flex_comp = platform_message_cls.PlatformComponent(
            platform="line", component_type="flex", data=bubble
        )
        chain2 = asyncio.run(linemod.LineMessageConverter().target2yiri(
            platform_message_cls.MessageChain([flex_comp])
        ))
        check("yiri2target_flex_len", len(chain2) == 1, str(len(chain2)))
        check("yiri2target_flex_type", bool(chain2) and chain2[0].get("type") == "flex")
    except Exception as exc:
        check("yiri2target_flex", False, repr(exc))

if adapter_cls is not None:
    try:
        # bypass __init__（ heavyweight super()），仅验宣告方法
        adp = adapter_cls.__new__(adapter_cls)
        events = adp.get_supported_events()
        apis = adp.get_supported_apis()
        check("event_image_received", "image.received" in events, str(events))
        check("api_flex_send", "flex.send" in apis, str(apis))
    except Exception as exc:
        check("capabilities", False, repr(exc))

sys.exit(0 if _summary() else 1)
