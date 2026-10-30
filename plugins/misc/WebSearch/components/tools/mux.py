import re
import logging

from .sites import model


def process(url: str, brief_len: int, **kwargs) -> str:
    """处理网页内容"""

    brief_len = model.clamp_brief_len(brief_len)

    adapter_cls: model.SiteAdapterBase = model.SiteAdapterBase

    found = False
    for adapter in model.__site_adapters__:
        for regexp in adapter['regexp']:
            if re.match(regexp, url):
                if not adapter['cls'].feed(url):
                    # 匹中了这个适配器，但适配器不接受这个链接
                    # 则直接检查下一个适配器
                    break
                adapter_cls = adapter['cls']
                found = True
                break
        if found:
            break

    logging.debug("site adapter: {}".format(adapter_cls))

    processed: dict = adapter_cls.process(url, brief_len, **kwargs)

    logging.debug("site adapter ret: {}".format(processed))

    # 处理成纯文本

    text: str = ""

    if processed.get('status', 200) == 200:
        if 'content' not in processed:
            text = processed.get('message', "nothing found")
        else:
            text += ('title: '+processed['content']['title']+"\n") if 'title' in processed['content'] else ''
            text += '\n'.join(processed['content'].get('briefs', []))
    else:
        raise Exception(processed.get('message', "error"))

    return text
