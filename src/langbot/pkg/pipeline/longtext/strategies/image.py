from __future__ import annotations

import os
import base64
import time
import re

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
        img_path = self.text_to_image(
            text_str=message,
            save_as='temp/{}.png'.format(int(time.time())),
            query=query,
        )

        compressed_path, size = self.compress_image(img_path, outfile='temp/{}_compressed.png'.format(int(time.time())))

        with open(compressed_path, 'rb') as f:
            img = f.read()

        b64 = base64.b64encode(img)

        # 删除图片
        os.remove(img_path)

        if os.path.exists(compressed_path):
            os.remove(compressed_path)

        return [
            platform_message.Image(
                base64=b64.decode('utf-8'),
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

    def text_to_image(
        self,
        text_str: str,
        save_as='temp.png',
        width=800,
        query: pipeline_query.Query = None,
    ):
        text_str = text_str.replace('\t', '    ')

        # 分行
        lines = text_str.split('\n')

        # 计算并分割
        final_lines = []

        text_width = width - 80

        self.ap.logger.debug('lines: {}, text_width: {}'.format(lines, text_width))
        for line in lines:
            # 如果长了就分割
            line_width = self.get_font(query.pipeline_config['output']['long-text-processing']['font-path']).getlength(
                line
            )
            self.ap.logger.debug('line_width: {}'.format(line_width))
            if line_width < text_width:
                final_lines.append(line)
                continue
            else:
                rest_text = line
                while True:
                    # 分割最前面的一行
                    point = int(len(rest_text) * (text_width / line_width))

                    # 检查断点是否在数字中间
                    numbers = self.indexNumber(rest_text)

                    for number in numbers:
                        if number[1] < point < number[1] + len(number[0]) and number[1] != 0:
                            point = number[1]
                            break

                    final_lines.append(rest_text[:point])
                    rest_text = rest_text[point:]
                    line_width = self.get_font(
                        query.pipeline_config['output']['long-text-processing']['font-path']
                    ).getlength(rest_text)
                    if line_width < text_width:
                        final_lines.append(rest_text)
                        break
                    else:
                        continue
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
                font=self.get_font(query.pipeline_config['output']['long-text-processing']['font-path']),
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
