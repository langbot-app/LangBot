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
import langbot_plugin.api.entities.builtin.pipeline.query as pipeline_query
import langbot_plugin.api.entities.builtin.platform.message as platform_message


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
                    return base64.b64encode(f.read()).decode('utf-8')
            finally:
                for path in {img_path, compressed_path}:
                    if os.path.exists(path):
                        os.remove(path)

        # Font measurement, image rendering and compression are CPU-bound PIL
        # work and must not block the shared asyncio loop for every tenant.
        image_base64 = await asyncio.to_thread(render)

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
        kv = []
        nums = []
        beforeDatas = re.findall('[\\d]+', path)
        for num in beforeDatas:
            indexV = []
            times = path.count(num)
            if times > 1:
                if num not in nums:
                    indexs = re.finditer(num, path)
                    for index in indexs:
                        iV = []
                        i = index.span()[0]
                        iV.append(num)
                        iV.append(i)
                        kv.append(iV)
                nums.append(num)
            else:
                index = path.find(num)
                indexV.append(num)
                indexV.append(index)
                kv.append(indexV)
        # 根据数字位置排序
        indexSort = []
        resultIndex = []
        for vi in kv:
            indexSort.append(vi[1])
        indexSort.sort()
        for i in indexSort:
            for v in kv:
                if i == v[1]:
                    resultIndex.append(v)
        return resultIndex

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
            im = Image.open(infile)
            im.save(outfile, quality=quality)
            if quality - step < 0:
                break
            quality -= step
            o_size = self.get_size(outfile)
        return outfile, self.get_size(outfile)

    def _split_text_lines(self, text_str: str, text_width: int, font) -> list[str]:
        """Split text while guaranteeing that every loop iteration advances."""

        final_lines: list[str] = []
        text_width = max(int(text_width), 1)
        for line in text_str.replace('\t', '    ').split('\n'):
            line_width = font.getlength(line)
            if not line or line_width < text_width:
                final_lines.append(line)
                continue

            rest_text = line
            while rest_text:
                line_width = max(font.getlength(rest_text), 1)
                point = int(len(rest_text) * (text_width / line_width))
                point = max(1, min(point, len(rest_text)))

                for number, number_index in self.indexNumber(rest_text):
                    if number_index < point < number_index + len(number) and number_index != 0:
                        point = number_index
                        break

                point = max(1, min(point, len(rest_text)))
                final_lines.append(rest_text[:point])
                rest_text = rest_text[point:]
                if rest_text and font.getlength(rest_text) < text_width:
                    final_lines.append(rest_text)
                    break
        return final_lines

    def text_to_image(
        self,
        text_str: str,
        save_as='temp.png',
        width=800,
        query: pipeline_query.Query = None,
    ):
        font = self.get_font(query.pipeline_config['output']['long-text-processing']['font-path'])
        text_width = max(width - 80, 1)
        final_lines = self._split_text_lines(text_str, text_width, font)
        # 准备画布
        img = Image.new('RGBA', (width, max(280, len(final_lines) * 35 + 65)), (255, 255, 255, 255))
        draw = ImageDraw.Draw(img, mode='RGBA')

        self.ap.logger.debug('正在绘制图片...')
        # 绘制正文
        line_number = 0
        offset_x = 20
        offset_y = 30
        for final_line in final_lines:
            draw.text(
                (offset_x, offset_y + 35 * line_number),
                final_line,
                fill=(0, 0, 0),
                font=font,
            )
            # 遍历此行,检查是否有emoji
            idx_in_line = 0
            for ch in final_line:
                # 检查字符占位宽
                char_code = ord(ch)
                if char_code >= 127:
                    idx_in_line += 1
                else:
                    idx_in_line += 0.5

            line_number += 1

        self.ap.logger.debug('正在保存图片...')
        img.save(save_as)

        return save_as
