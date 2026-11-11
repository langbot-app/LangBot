"""Agent input entity as defined in Protocol v1."""

from __future__ import annotations

import pydantic

from langbot_plugin.api.entities.builtin.runner.interaction import InteractionSubmission
from langbot_plugin.api.entities.builtin.provider.message import ContentElement


class InputAttachment(pydantic.BaseModel):
    """Metadata for a current-event attachment.

    Each attachment describes one media component of the current message, in
    order of appearance. Read its bytes with ``RunnerContext.read_input_attachment``
    or import it into a Box with ``import_box_attachments``; both use ``ref``.
    """

    ref: str | None = None
    """Host-issued reference, such as ``att-1``.

    The same ref appears as ``[attachment att-1: ...]`` in the input text at the
    position of the media.
    """

    type: str | None = None
    """Attachment type, such as image, file, or voice."""

    mime_type: str | None = None
    """MIME type."""

    size: int | None = None
    """Size in bytes."""

    name: str | None = None
    """File name, if available."""

    source: str | None = None
    """Where the media appeared: ``message`` for the current message, or
    ``quote`` for a message quoted by it. Older Hosts used transport names
    such as url, base64 or message_chain."""

    url: str | None = None
    """External URL when the attachment is backed by a URL."""

    path: str | None = None
    """Sandbox/workspace path when Host has staged the attachment as a file."""

    content: str | None = None
    """Deprecated inline base64 content; current Hosts leave it empty.

    Use ``RunnerContext.read_input_attachment`` instead.
    """

    id: str | None = None
    """Platform-native attachment identifier when available."""

    model_config = pydantic.ConfigDict(extra="forbid")


class InputAttachmentData(pydantic.BaseModel):
    """Bytes of one current-event attachment, read by ref from the Host."""

    ref: str
    """Attachment ref that was read."""

    name: str | None = None
    """File name, if available."""

    mime_type: str | None = None
    """MIME type, if known."""

    data: bytes
    """Attachment bytes."""

    @property
    def size(self) -> int:
        return len(self.data)


class AgentInput(pydantic.BaseModel):
    """Input for an agent run.

    Contains the user's input in multiple formats for convenience.
    Protocol v1: input is required; attachments are lightweight metadata.
    """

    text: str | None = None
    """Plain text input."""

    contents: list[ContentElement] = pydantic.Field(default_factory=list)
    """Structured content elements (text, images, files, etc.)."""

    attachments: list[InputAttachment] = pydantic.Field(default_factory=list)
    """Current-event attachment metadata."""

    interaction: InteractionSubmission | None = None
    """Host-validated interaction submission for the current event."""

    def to_text(self) -> str:
        """Extract plain text from input.

        Returns text if available, otherwise concatenates text content elements.
        """
        if self.text is not None:
            return self.text

        text_parts = []
        for content in self.contents:
            if content.type == "text" and content.text:
                text_parts.append(content.text)

        return " ".join(text_parts)
