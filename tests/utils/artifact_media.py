"""Deterministic media whose expected markers exist only in readable content."""

from dataclasses import dataclass
from hashlib import sha256
from io import BytesIO

from PIL import Image, ImageDraw, ImageFont
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject, NumberObject


@dataclass(frozen=True)
class MediaFixture:
    kind: str
    filename: str
    mime_type: str
    data: bytes
    marker: str

    @property
    def sha256(self) -> str:
        return sha256(self.data).hexdigest()

    @property
    def size(self) -> int:
        return len(self.data)


def _image(marker: str) -> Image.Image:
    image = Image.new('RGB', (480, 160), '#fcfaf0')
    draw = ImageDraw.Draw(image)
    draw.rectangle((8, 8, 472, 152), outline='#182c4c', width=4)
    font = ImageFont.load_default(size=32)
    draw.text((240, 80), marker, fill='#182c4c', font=font, anchor='mm')
    return image


def _finish_pdf(writer: PdfWriter) -> bytes:
    output = BytesIO()
    writer.write(output)
    return output.getvalue()


def text_pdf(*lines: str) -> bytes:
    """Make a selectable-text PDF with one line per page and no marker metadata."""
    writer = PdfWriter()
    for line in lines:
        page = writer.add_blank_page(width=480, height=160)
        font = DictionaryObject(
            {
                NameObject('/Type'): NameObject('/Font'),
                NameObject('/Subtype'): NameObject('/Type1'),
                NameObject('/BaseFont'): NameObject('/Helvetica-Bold'),
            }
        )
        page[NameObject('/Resources')] = DictionaryObject(
            {NameObject('/Font'): DictionaryObject({NameObject('/F1'): writer._add_object(font)})}
        )
        literal = line.replace('\\', '\\\\').replace('(', '\\(').replace(')', '\\)')
        body = DecodedStreamObject()
        body.set_data(f'BT /F1 32 Tf 80 72 Td ({literal}) Tj ET'.encode('ascii'))
        page[NameObject('/Contents')] = writer._add_object(body.flate_encode())
    return _finish_pdf(writer)


def _scanned_pdf(image: Image.Image) -> bytes:
    writer = PdfWriter()
    page = writer.add_blank_page(width=image.width, height=image.height)
    xobject = DecodedStreamObject()
    xobject.set_data(image.tobytes())
    xobject.update(
        {
            NameObject('/Type'): NameObject('/XObject'),
            NameObject('/Subtype'): NameObject('/Image'),
            NameObject('/Width'): NumberObject(image.width),
            NameObject('/Height'): NumberObject(image.height),
            NameObject('/ColorSpace'): NameObject('/DeviceRGB'),
            NameObject('/BitsPerComponent'): NumberObject(8),
        }
    )
    page[NameObject('/Resources')] = DictionaryObject(
        {NameObject('/XObject'): DictionaryObject({NameObject('/Im1'): writer._add_object(xobject.flate_encode())})}
    )
    body = DecodedStreamObject()
    body.set_data(f'q {image.width} 0 0 {image.height} 0 0 cm /Im1 Do Q'.encode('ascii'))
    page[NameObject('/Contents')] = writer._add_object(body)
    return _finish_pdf(writer)


def make_artifact_media(session: str, *, seed: int = 3063) -> tuple[MediaFixture, ...]:
    """Stable per-session fixtures. Identical inputs intentionally repeat the exact bytes."""
    fixtures = []
    for kind, filename, mime_type in (
        ('png', 'image.png', 'image/png'),
        ('jpeg', 'image.jpg', 'image/jpeg'),
        ('text_pdf', 'reference.pdf', 'application/pdf'),
        ('scanned_pdf', 'scan.pdf', 'application/pdf'),
    ):
        digest = sha256(f'{seed}\0{session}\0{kind}'.encode()).hexdigest()
        marker = 'MEDIA-' + digest[:12].upper()
        if kind == 'text_pdf':
            data = text_pdf(marker)
        elif kind == 'scanned_pdf':
            data = _scanned_pdf(_image(marker))
        else:
            output = BytesIO()
            _image(marker).save(output, format='PNG' if kind == 'png' else 'JPEG')
            data = output.getvalue()
        fixtures.append(MediaFixture(kind, filename, mime_type, data, marker))
    return tuple(fixtures)
