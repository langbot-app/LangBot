from ..model import site, SiteAdapterBase

from bs4 import BeautifulSoup

import re


# 处理github.com/xxx这种网址，排除有二级路径的网址

@site([
    "https?://github.com/[^/^?]+$",
    "https?://www.github.com/[^/^?]+$",
])
class GithubUserSiteAdapter(SiteAdapterBase):

    @classmethod
    def feed(cls, url: str) -> bool:
        """判断是否适配此网址"""
        exclude_url = [
            "https://github.com/pulls",
            "https://github.com/issues",
            "https://github.com/codespaces",
            "https://github.com/marketplace",
            "https://github.com/explore",
            "https://github.com/topics"
        ]
        return url not in exclude_url

    @classmethod
    def process(cls, url: str, brief_len: int, **kwargs) -> dict:
        """处理网页内容"""
        status_code, raw_html = cls.get_html(url, **kwargs)
        if status_code != 200:
            return cls.make_ret(
                status_code=status_code,
                message="error"
            )

        soup = BeautifulSoup(raw_html, 'html.parser')
        title = soup.title.string

        briefs = []

        raw = soup.get_text()

        # strip每一行
        raw = '\n'.join([line.strip() for line in raw.split('\n')])

        # 删除所有空行或只有空格的行
        raw = re.sub(r'\n\s*\n', '\n', raw)

        delete = """Actions
        Automate any workflow
        Packages
        Host and manage packages
        Security
        Find and fix vulnerabilities
        Codespaces
        Instant dev environments
        Copilot
        Write better code with AI
        Code review
        Manage code changes
        Issues
        Plan and track work
        Discussions
        Collaborate outside of code
        Explore
        All features
        Documentation
        GitHub Skills
        Blog
        Solutions
        For
        Enterprise
        Teams
        Startups
        Education
        By Solution
        CI/CD & Automation"""

        raw = re.sub(delete, '', raw)

        raw = re.sub(r'Stars', '', raw)

        # 删除仅包含月份的行
        month = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'Novermber', 'December', 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nover', 'Dec']
        for i in month:
            raw = re.sub(r'\n'+i+r'\n', '', raw)

        # # itemprop="name"> xxx </span>
        # # 从html中用正则提取
        # briefs = cls.regexp_brief(raw_html, "Name", r'itemprop="name">(.*?)</span>', briefs)

        # # <span class="p-nickname vcard-username d-block" itemprop="additionalName"> xxx </span>
        # # xxx可能包含换行符
        # # 从html中用正则提取
        # briefs = cls.regexp_brief(raw_html, "Nickname", r'<span class="p-nickname vcard-username d-block" itemprop="additionalName">(.*?)</span>', briefs)

        # # itemprop="pronouns">he/him</span>
        # briefs = cls.regexp_brief(raw_html, "Pronouns", r'itemprop="pronouns">(.*?)</span>', briefs)

        # # data-bio-text="xxx">
        # # 从html中用正则提取
        # briefs = cls.regexp_brief(raw_html, "Bio", r'data-bio-text="(.*?)"[\s]*?>', briefs)

        # # class="text-bold color-fg-default">47</span>
        # #  followers
        # # 从html中用正则提取
        # briefs = cls.regexp_brief(raw_html, "Followers", r'class="text-bold color-fg-default">(\d+)</span>[\s]*?followers', briefs)

        # # <span class="text-bold color-fg-default">14</span>
        # #  following
        # # 从html中用正则提取
        # briefs = cls.regexp_brief(raw_html, "Following", r'<span class="text-bold color-fg-default">(\d+)</span>[\s]*?following', briefs)

        # # Home location: Tianjin, China ">
        # # 从html中用正则提取
        # briefs = cls.regexp_brief(raw_html, "Home location", r'Home location:(.*?)">', briefs)

        # # "Email: i@jyunko.cn"
        # # 从html中用正则提取
        # briefs = cls.regexp_brief(raw_html, "Email", r'"Email:(.*?)"', briefs)

        briefs.append("brief raw: "+raw[:brief_len])

        return cls.make_ret(
            status_code=status_code,
            message="ok",
            title=title,
            briefs=briefs
        )
