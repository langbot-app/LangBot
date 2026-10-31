from __future__ import annotations

import asyncio
import os
import base64
import time
import re
import uuid

from PIL import Image, ImageDraw, ImageFont

import functools

from .. import strategy as strategy_model
from .forward import ForwardComponentStrategy
import langbot_plugin.api.entities.builtin.pipeline.query as pipeline_query
import langbot_plugin.api.entities.builtin.platform.message as platform_message


_MAX_TEXT_TO_IMAGE_CHARS = 100000
_MAX_TEXT_TO_IMAGE_LINES = 256
_MAX_TEXT_TO_IMAGE_PIXELS = 8_000_000
_MAX_RENDERED_IMAGE_BYTES = 10 * 1024 * 1024


class _TextToImageCapacityError(ValueError):
    """The requested image would exceed a deterministic resource boundary."""


@strategy_model.strategy_class('image')
class Text2ImageStrategy(strategy_model.LongTextStrategy):
    async def initialize(self):
        pass

    @functools.lru_cache(maxsize=16)
    def get_font(self, font_path: str):
        return ImageFont.truetype(
            font_path,
            32,
            encoding='utf-8',
        )

    async def process(self, message: str, query: pipeline_query.Query) -> list[platform_message.MessageComponent]:
        if len(message) > _MAX_TEXT_TO_IMAGE_CHARS:
            self.ap.logger.warning(
                f'Text-to-image input exceeds {_MAX_TEXT_TO_IMAGE_CHARS} characters; using forward message'
            )
            return await ForwardComponentStrategy(self.ap).process(message, query)

        def render() -> str:
            render_id = f'{int(time.time())}-{uuid.uuid4().hex}'
            img_path = f'temp/{render_id}.png'
            compressed_path = f'temp/{render_id}-compressed.png'
            try:
                self.text_to_image(
                    text_str=message,
                    save_as=img_path,
                    query=query,
                )
                compressed_path, _ = self.compress_image(
                    img_path,
                    outfile=compressed_path,
                )
                with open(compressed_path, 'rb') as f:
                    image_bytes = f.read(_MAX_RENDERED_IMAGE_BYTES + 1)
                if len(image_bytes) > _MAX_RENDERED_IMAGE_BYTES:
                    raise _TextToImageCapacityError(
                        f'Rendered image exceeds the {_MAX_RENDERED_IMAGE_BYTES}-byte limit'
                    )
                return base64.b64encode(image_bytes).decode('utf-8')
            finally:
                for path in {img_path, compressed_path}:
                    if os.path.exists(path):
                        os.remove(path)

        # Font measurement, image rendering and compression are CPU-bound PIL
        # work and must not block the shared asyncio loop for every tenant.
        try:
            image_base64 = await asyncio.to_thread(render)
        except _TextToImageCapacityError as exc:
            self.ap.logger.warning(f'{exc}; using forward message')
            return await ForwardComponentStrategy(self.ap).process(message, query)

        return [
            platform_message.Image(
                base64=image_base64,
            )
        ]

    def indexNumber(self, path=''):
        """
        查找字符串中数字所在串中的位置
        :param path:目标字符串
        :return:<class 'list'>: <class 'list'>: [['1', 16], ['2', 35], ['1', 51]]
        """
        return [[match.group(0), match.start()] for match in re.finditer(r'\d+', path)]

    def get_size(self, file):
        # 获取文件大小:KB
        size = os.path.getsize(file)
        return size / 1024

    def get_outfile(self, infile, outfile):
        if outfile:
            return outfile
        dir, suffix = os.path.splitext(infile)
        outfile = '{}-out{}'.format(dir, suffix)
        return outfile

    def compress_image(self, infile, outfile='', kb=100, step=20, quality=90):
        """不改变图片尺寸压缩到指定大小
        :param infile: 压缩源文件
        :param outfile: 压缩文件保存地址
        :param mb: 压缩目标,KB
        :param step: 每次调整的压缩比率
        :param quality: 初始压缩比率
        :return: 压缩文件地址，压缩文件大小
        """
        o_size = self.get_size(infile)
        if o_size <= kb:
            return infile, o_size
        outfile = self.get_outfile(infile, outfile)
        while o_size > kb:
            with Image.open(infile) as im:
                im.save(outfile, quality=quality)
            if step <= 0 or quality - step < 0:
                break
            quality -= step
            o_size = self.get_size(outfile)
        return outfile, self.get_size(outfile)

    def _split_text_lines(self, text_str: str, text_width: int, font) -> list[str]:
        """Split text while guaranteeing that every loop iteration advances."""

        if len(text_str) > _MAX_TEXT_TO_IMAGE_CHARS:
            raise _TextToImageCapacityError(f'Text-to-image input exceeds {_MAX_TEXT_TO_IMAGE_CHARS} characters')

        final_lines: list[str] = []

        def append_line(value: str) -> None:
            if len(final_lines) >= _MAX_TEXT_TO_IMAGE_LINES:
                raise _TextToImageCapacityError(f'Text-to-image output exceeds {_MAX_TEXT_TO_IMAGE_LINES} lines')
            final_lines.append(value)

        text_width = max(int(text_width), 1)
        for line in text_str.replace('\t', '    ').split('\n'):
            line_width = font.getlength(line)
            if not line or line_width < text_width:
                append_line(line)
                continue

            rest_text = line
            while rest_text:
                line_width = max(font.getlength(rest_text), 1)
                point = int(len(rest_text) * (text_width / line_width))
                point = max(1, min(point, len(rest_text)))

                if 0 < point < len(rest_text) and rest_text[point - 1].isdigit() and rest_text[point].isdigit():
                    number_start = point - 1
                    while number_start > 0 and rest_text[number_start - 1].isdigit():
                        number_start -= 1
                    if number_start > 0:
                        point = number_start

                point = max(1, min(point, len(rest_text)))
                append_line(rest_text[:point])
                rest_text = rest_text[point:]
                if rest_text and font.getlength(rest_text) < text_width:
                    append_line(rest_text)
                    break
        return final_lines

    def text_to_image(
        self,
        text_str: str,
        save_as='temp.png',
        width=800,
        query: pipeline_query.Query = None,
    ):
        width = int(width)
        if width < 1:
            raise _TextToImageCapacityError('Text-to-image width must be positive')
        font = self.get_font(query.pipeline_config['output']['long-text-processing']['font-path'])
        text_width = max(width - 80, 1)
        final_lines = self._split_text_lines(text_str, text_width, font)
        image_height = max(280, len(final_lines) * 35 + 65)
        if width * image_height > _MAX_TEXT_TO_IMAGE_PIXELS:
            raise _TextToImageCapacityError(f'Text-to-image canvas exceeds the {_MAX_TEXT_TO_IMAGE_PIXELS}-pixel limit')
        # 准备画布
        img = Image.new('RGBA', (width, image_height), (255, 255, 255, 255))
        try:
            draw = ImageDraw.Draw(img, mode='RGBA')

            self.ap.logger.debug('正在绘制图片...')
            offset_x = 20
            offset_y = 30
            for line_number, final_line in enumerate(final_lines):
                draw.text(
                    (offset_x, offset_y + 35 * line_number),
                    final_line,
                    fill=(0, 0, 0),
                    font=font,
                )

            self.ap.logger.debug('正在保存图片...')
            img.save(save_as)
        finally:
            img.close()

        return save_as
