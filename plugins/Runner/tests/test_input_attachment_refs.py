"""Runners read input attachments by ref from Hosts that serve them."""

from __future__ import annotations

import asyncio
import base64
from types import SimpleNamespace

import pytest

from tests.test_native_parity_external import ctx, load_runner

IMAGE = b"\x89PNG image bytes"
REPORT = b"%PDF report bytes"


class HostContext:
    """A RunnerContext from a Host with ``input_attachments`` and a newer SDK."""

    def __init__(self, base, files):
        self._base = base
        self.files = files
        self.reads = []
        self.context = SimpleNamespace(available_apis=SimpleNamespace(input_attachments=True))

    def __getattr__(self, name):
        return getattr(self._base, name)

    async def read_input_attachment(self, attachment):
        self.reads.append(attachment.ref)
        if attachment.ref not in self.files:
            raise RuntimeError("cannot be read")
        name, mime_type, data = self.files[attachment.ref]
        return SimpleNamespace(ref=attachment.ref, name=name, mime_type=mime_type, data=data)


def host_context(*, with_report=True):
    from langbot_plugin.api.entities.builtin.provider.message import ContentElement
    from langbot_plugin.api.entities.builtin.runner.input import InputAttachment

    base = ctx(text="look [attachment att-1: image] and [attachment att-2: file report.pdf]")
    image_data_url = "data:image/png;base64," + base64.b64encode(IMAGE).decode()
    # Contents still carry the image for the model; attachments are metadata only.
    base.input.contents = [ContentElement.from_text("look"), ContentElement.from_image_base64(image_data_url)]
    base.input.attachments = [
        InputAttachment(ref="att-1", type="image", source="message", mime_type="image/png"),
        InputAttachment(ref="att-3", type="image", source="quote"),
    ]
    files = {"att-1": (None, "image/png", IMAGE)}
    if with_report:
        base.input.attachments.insert(1, InputAttachment(ref="att-2", type="file", source="message", name="report.pdf"))
        files["att-2"] = ("report.pdf", "application/pdf", REPORT)
    return HostContext(base, files)


def test_dify_uploads_each_attachment_once_named_by_ref():
    with load_runner("dify-agent") as (m, runner):
        client = object.__new__(m.AsyncDifyClient)
        uploads = []

        async def upload(name, data, mime, user):
            uploads.append((name, data, mime))
            return {"id": f"upload-{len(uploads)}"}

        client.upload_file = upload
        context = host_context()
        files = asyncio.run(runner._upload_input_files(context, client, "user"))

    # The unreadable quoted image is skipped instead of failing the run.
    assert context.reads == ["att-1", "att-2", "att-3"]
    assert uploads == [
        ("att-1_image.png", IMAGE, "image/png"),
        ("att-2_report.pdf", REPORT, "application/pdf"),
    ]
    assert [item["type"] for item in files] == ["image", "document"]


@pytest.mark.parametrize(
    "plugin,method,client_name",
    [
        ("coze-agent", "_build_additional_messages", "AsyncCozeClient"),
        ("tbox-agent", "_upload_input_files", "AsyncTboxClient"),
    ],
)
def test_coze_and_tbox_upload_host_bytes_once(plugin, method, client_name):
    with load_runner(plugin) as (m, runner):
        client = object.__new__(getattr(m, client_name))
        uploads = []

        async def upload(data, name):
            uploads.append((name, data))
            return "provider-upload"

        client.upload_file = upload
        # Tbox accepts images only; keep the input to the image it supports.
        context = host_context(with_report=plugin == "coze-agent")
        asyncio.run(getattr(runner, method)(context, client))

    expected = [("att-1_image.png", IMAGE)]
    if plugin == "coze-agent":
        expected.append(("att-2_report.pdf", REPORT))
    assert uploads == expected


def test_deerflow_takes_images_from_contents_only():
    with load_runner("deerflow-agent") as (_, runner):
        context = host_context()
        context._base.input.attachments[0].url = "https://example.invalid/image.png"
        urls = runner._extract_image_urls(context)

    assert urls == ["data:image/png;base64," + base64.b64encode(IMAGE).decode()]


def test_n8n_payload_describes_attachments_by_ref():
    with load_runner("n8n-agent") as (_, runner):
        context = host_context()
        payload = runner._build_payload(context, context.input.to_text(), "conversation", "session")

    assert payload["attachments"] == [
        {"ref": "att-1", "type": "image", "source": "message", "mime_type": "image/png"},
        {"ref": "att-2", "type": "file", "source": "message", "name": "report.pdf"},
        {"ref": "att-3", "type": "image", "source": "quote"},
    ]
    assert "[attachment att-2: file report.pdf]" in payload["chatInput"]


def test_acp_hydrates_attachment_content_from_host():
    with load_runner("acp-agent-runner") as (m, _):
        context = host_context()
        asyncio.run(m._hydrate_input_attachments(context))

    image, report, quoted = context.input.attachments
    assert image.content == "data:image/png;base64," + base64.b64encode(IMAGE).decode()
    assert report.content == "data:application/pdf;base64," + base64.b64encode(REPORT).decode()
    assert report.mime_type == "application/pdf"
    assert quoted.content is None
