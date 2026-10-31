# -*- coding: utf-8 -*-
"""Internationalization for the GitHubKit plugin (en_US + zh_Hans)."""

TRANSLATIONS = {
    "en_US": {
        "misc.sep": ", ",
        # errors
        "err.404": "Not found (404). Check the name, or whether it is private (needs a token).",
        "err.rate": "GitHub API rate limit hit. Set github_token in the plugin config to raise the limit.",
        "err.perm": "No permission ({status}): {msg}",
        "err.perm_default": "may need a token.",
        "err.generic": "GitHub API error ({status}): {msg}",
        # repo_info
        "repo.usage": "Usage: !gh repo <owner/repo>",
        "repo.no_desc": "(no description)",
        "repo.dash": "\u2014",
        "repo.body": "\U0001f4e6 {full_name}\n{desc}\n\u2b50 {stars}  \U0001f374 {forks}  \U0001f441 {watchers}  \u26a0 {issues} issues\nLanguage: {lang}  License: {lic}\nDefault branch: {branch}\n\U0001f517 {url}",
        "repo.homepage": "\U0001f3e0 {homepage}",
        # issues
        "issues.usage": "Usage: !gh issues <owner/repo> [open|closed|all]",
        "issues.none": "{repo} has no {state} issues.",
        "issues.header": "\U0001f41b {repo} Issues ({state}, recently updated):",
        "issues.item": "  #{number} {title}{labels}",
        # prs
        "prs.usage": "Usage: !gh prs <owner/repo> [open|closed|all]",
        "prs.none": "{repo} has no {state} pull requests.",
        "prs.header": "\U0001f500 {repo} Pull Requests ({state}, recently updated):",
        "prs.draft": " (draft)",
        "prs.item": "  #{number} {title}{draft}  \u2190 {user}",
        # issue detail
        "issue.usage": "Usage: !gh issue <owner/repo> <number>",
        "issue.bad_number": "Issue/PR number must be numeric.",
        "issue.kind_pr": "PR",
        "issue.kind_issue": "Issue",
        "issue.labels": "\nLabels: {labels}",
        "issue.body": "{emoji} {repo} {kind} #{number} [{state}]\n{title}\nAuthor: {author}  \U0001f4ac {comments}{labels}\n\U0001f517 {url}{body}",
        # releases
        "releases.usage": "Usage: !gh releases <owner/repo>",
        "releases.none": "{repo} has no releases yet.",
        "releases.header": "\U0001f3f7 {repo} latest releases:",
        "releases.prerelease": " (prerelease)",
        "releases.item": "  {tag} {name}{pre}  {date}",
        # user
        "user.usage": "Usage: !gh user <username>",
        "user.body": "\U0001f464 {name} (@{login}){bio}\n\U0001f4e6 {repos} repos  \U0001f465 {followers} followers  following {following}\n\U0001f517 {url}",
        # search
        "search.usage": "Usage: !gh search <keyword>",
        "search.none": "No repositories matched \u300c{query}\u300d.",
        "search.header": "\U0001f50d Search \u300c{query}\u300d (by stars):",
        "search.item": "  \u2b50{stars} {full_name} \u2014 {desc}",
        # subscribe
        "sub.usage": "Usage: !gh sub <owner/repo> [event types...]",
        "sub.all_events": "all events",
        "sub.ok": "\u2705 Subscribed to {repo} event push ({events}).\nNew commits/PRs/issues/releases will be posted here automatically.\nPoll interval ~{interval}s. Unsubscribe: !gh unsub {repo}",
        "unsub.usage": "Usage: !gh unsub <owner/repo>",
        "unsub.not_subbed": "This chat is not subscribed to {repo}.",
        "unsub.ok": "Unsubscribed from {repo} event push.",
        "subs.all": "all",
        "subs.none": "This chat has no subscriptions yet. Subscribe with !gh sub <owner/repo>.",
        "subs.header": "\U0001f4e1 Subscriptions in this chat:",
        "subs.item": "  \u2022 {repo} ({events})",
        # push notification header
        "push.header": "\U0001f514 New activity in {repo}:",
        # event formatters
        "ev.push": "  \U0001f4e4 {actor} pushed {n} commit(s) to {ref}{head}",
        "ev.push_head": ": {msg}",
        "ev.pr_opened": "opened",
        "ev.pr_closed": "closed",
        "ev.pr_merged": "merged",
        "ev.pr_reopened": "reopened",
        "ev.pr": "  \U0001f500 {actor} {action} PR #{num}: {title}",
        "ev.issue_opened": "opened",
        "ev.issue_closed": "closed",
        "ev.issue_reopened": "reopened",
        "ev.issue": "  \U0001f41b {actor} {action} Issue #{num}: {title}",
        "ev.comment": "  \U0001f4ac {actor} commented on #{num}: {title}",
        "ev.release": "  \U0001f3f7 {actor} published Release {tag}",
        "ev.star": "  \u2b50 {actor} starred the repo",
        "ev.fork": "  \U0001f374 {actor} forked the repo",
        "ev.create": "  \u2795 {actor} created {ref_type} {ref}",
        "ev.delete": "  \u2796 {actor} deleted {ref_type} {ref}",
        "ev.review": "  \U0001f440 {actor} reviewed PR #{num}",
        # help (gh.py)
        "help": (
            "\U0001f419 GitHubKit usage:\n"
            "  !gh repo <owner/repo>          Repo info\n"
            "  !gh issues <owner/repo> [state]  Issue list (open|closed|all)\n"
            "  !gh prs <owner/repo> [state]     PR list\n"
            "  !gh issue <owner/repo> <number>  Issue/PR detail\n"
            "  !gh releases <owner/repo>      Release list\n"
            "  !gh user <username>            User info\n"
            "  !gh search <keyword>           Search repos\n"
            "  -- Event push --\n"
            "  !gh sub <owner/repo> [events]  Subscribe events to this chat\n"
            "      events: push/pr/issue/release/star/fork (default all)\n"
            "  !gh unsub <owner/repo>         Unsubscribe\n"
            "  !gh subs                       List this chat's subscriptions\n"
            "  !gh help                       Show help\n"
            "\nTip: set github_token in the plugin config to lift rate limits and access private repos."
        ),
    },
    "zh_Hans": {
        "misc.sep": "\u3001",
        # errors
        "err.404": "\u672a\u627e\u5230\uff08404\uff09\u3002\u8bf7\u68c0\u67e5\u540d\u79f0\u662f\u5426\u6b63\u786e\uff0c\u6216\u8be5\u8d44\u6e90\u662f\u5426\u79c1\u6709\uff08\u9700\u914d\u7f6e token\uff09\u3002",
        "err.rate": "GitHub API \u901f\u7387\u53d7\u9650\u3002\u8bf7\u5728\u63d2\u4ef6\u914d\u7f6e\u91cc\u586b\u5199 github_token \u4ee5\u63d0\u9ad8\u989d\u5ea6\u3002",
        "err.perm": "\u65e0\u6743\u9650\uff08{status}\uff09\uff1a{msg}",
        "err.perm_default": "\u53ef\u80fd\u9700\u8981\u914d\u7f6e token\u3002",
        "err.generic": "GitHub API \u9519\u8bef\uff08{status}\uff09\uff1a{msg}",
        # repo_info
        "repo.usage": "\u7528\u6cd5\uff1a!gh repo <owner/repo>",
        "repo.no_desc": "\uff08\u65e0\u63cf\u8ff0\uff09",
        "repo.dash": "\u2014",
        "repo.body": "\U0001f4e6 {full_name}\n{desc}\n\u2b50 {stars}  \U0001f374 {forks}  \U0001f441 {watchers}  \u26a0 {issues} issues\n\u8bed\u8a00\uff1a{lang}  \u8bb8\u53ef\u8bc1\uff1a{lic}\n\u9ed8\u8ba4\u5206\u652f\uff1a{branch}\n\U0001f517 {url}",
        "repo.homepage": "\U0001f3e0 {homepage}",
        # issues
        "issues.usage": "\u7528\u6cd5\uff1a!gh issues <owner/repo> [open|closed|all]",
        "issues.none": "{repo} \u6ca1\u6709 {state} \u72b6\u6001\u7684 Issue\u3002",
        "issues.header": "\U0001f41b {repo} Issues\uff08{state}\uff0c\u6700\u8fd1\u66f4\u65b0\uff09\uff1a",
        "issues.item": "  #{number} {title}{labels}",
        # prs
        "prs.usage": "\u7528\u6cd5\uff1a!gh prs <owner/repo> [open|closed|all]",
        "prs.none": "{repo} \u6ca1\u6709 {state} \u72b6\u6001\u7684 PR\u3002",
        "prs.header": "\U0001f500 {repo} Pull Requests\uff08{state}\uff0c\u6700\u8fd1\u66f4\u65b0\uff09\uff1a",
        "prs.draft": "\uff08\u8349\u7a3f\uff09",
        "prs.item": "  #{number} {title}{draft}  \u2190 {user}",
        # issue detail
        "issue.usage": "\u7528\u6cd5\uff1a!gh issue <owner/repo> <\u7f16\u53f7>",
        "issue.bad_number": "Issue/PR \u7f16\u53f7\u5fc5\u987b\u662f\u6570\u5b57\u3002",
        "issue.kind_pr": "PR",
        "issue.kind_issue": "Issue",
        "issue.labels": "\n\u6807\u7b7e\uff1a{labels}",
        "issue.body": "{emoji} {repo} {kind} #{number} [{state}]\n{title}\n\u4f5c\u8005\uff1a{author}  \U0001f4ac {comments}{labels}\n\U0001f517 {url}{body}",
        # releases
        "releases.usage": "\u7528\u6cd5\uff1a!gh releases <owner/repo>",
        "releases.none": "{repo} \u8fd8\u6ca1\u6709\u53d1\u5e03 Release\u3002",
        "releases.header": "\U0001f3f7 {repo} \u6700\u65b0 Release\uff1a",
        "releases.prerelease": "\uff08\u9884\u53d1\u5e03\uff09",
        "releases.item": "  {tag} {name}{pre}  {date}",
        # user
        "user.usage": "\u7528\u6cd5\uff1a!gh user <\u7528\u6237\u540d>",
        "user.body": "\U0001f464 {name}\uff08@{login}\uff09{bio}\n\U0001f4e6 {repos} repos  \U0001f465 {followers} followers  following {following}\n\U0001f517 {url}",
        # search
        "search.usage": "\u7528\u6cd5\uff1a!gh search <\u5173\u952e\u8bcd>",
        "search.none": "\u6ca1\u6709\u627e\u5230\u5339\u914d\u300c{query}\u300d\u7684\u4ed3\u5e93\u3002",
        "search.header": "\U0001f50d \u641c\u7d22\u300c{query}\u300d\uff08\u6309 star \u6392\u5e8f\uff09\uff1a",
        "search.item": "  \u2b50{stars} {full_name} \u2014 {desc}",
        # subscribe
        "sub.usage": "\u7528\u6cd5\uff1a!gh sub <owner/repo> [\u4e8b\u4ef6\u7c7b\u578b...]",
        "sub.all_events": "\u5168\u90e8\u4e8b\u4ef6",
        "sub.ok": "\u2705 \u5df2\u8ba2\u9605 {repo} \u7684\u4e8b\u4ef6\u63a8\u9001\uff08{events}\uff09\u3002\n\u65b0\u7684\u63d0\u4ea4/PR/Issue/Release \u7b49\u5c06\u81ea\u52a8\u64ad\u62a5\u5230\u672c\u4f1a\u8bdd\u3002\n\u8f6e\u8be2\u95f4\u9694\u7ea6 {interval} \u79d2\u3002\u9000\u8ba2\uff1a!gh unsub {repo}",
        "unsub.usage": "\u7528\u6cd5\uff1a!gh unsub <owner/repo>",
        "unsub.not_subbed": "\u672c\u4f1a\u8bdd\u6ca1\u6709\u8ba2\u9605 {repo}\u3002",
        "unsub.ok": "\u5df2\u9000\u8ba2 {repo} \u7684\u4e8b\u4ef6\u63a8\u9001\u3002",
        "subs.all": "\u5168\u90e8",
        "subs.none": "\u672c\u4f1a\u8bdd\u8fd8\u6ca1\u6709\u8ba2\u9605\u4efb\u4f55\u4ed3\u5e93\u3002\u7528 !gh sub <owner/repo> \u8ba2\u9605\u3002",
        "subs.header": "\U0001f4e1 \u672c\u4f1a\u8bdd\u7684\u8ba2\u9605\uff1a",
        "subs.item": "  \u2022 {repo}\uff08{events}\uff09",
        # push notification header
        "push.header": "\U0001f514 {repo} \u6709\u65b0\u52a8\u6001\uff1a",
        # event formatters
        "ev.push": "  \U0001f4e4 {actor} \u63a8\u9001\u4e86 {n} \u4e2a\u63d0\u4ea4\u5230 {ref}{head}",
        "ev.push_head": "\uff1a{msg}",
        "ev.pr_opened": "\u5f00\u542f",
        "ev.pr_closed": "\u5173\u95ed",
        "ev.pr_merged": "\u5408\u5e76",
        "ev.pr_reopened": "\u91cd\u65b0\u5f00\u542f",
        "ev.pr": "  \U0001f500 {actor} {action}\u4e86 PR #{num}\uff1a{title}",
        "ev.issue_opened": "\u5f00\u542f",
        "ev.issue_closed": "\u5173\u95ed",
        "ev.issue_reopened": "\u91cd\u65b0\u5f00\u542f",
        "ev.issue": "  \U0001f41b {actor} {action}\u4e86 Issue #{num}\uff1a{title}",
        "ev.comment": "  \U0001f4ac {actor} \u8bc4\u8bba\u4e86 #{num}\uff1a{title}",
        "ev.release": "  \U0001f3f7 {actor} \u53d1\u5e03\u4e86 Release {tag}",
        "ev.star": "  \u2b50 {actor} star \u4e86\u4ed3\u5e93",
        "ev.fork": "  \U0001f374 {actor} fork \u4e86\u4ed3\u5e93",
        "ev.create": "  \u2795 {actor} \u521b\u5efa\u4e86 {ref_type} {ref}",
        "ev.delete": "  \u2796 {actor} \u5220\u9664\u4e86 {ref_type} {ref}",
        "ev.review": "  \U0001f440 {actor} \u5ba1\u67e5\u4e86 PR #{num}",
        # help (gh.py)
        "help": (
            "\U0001f419 GitHub \u5de5\u5177\u7bb1 \u7528\u6cd5\uff1a\n"
            "  !gh repo <owner/repo>          \u4ed3\u5e93\u4fe1\u606f\n"
            "  !gh issues <owner/repo> [\u72b6\u6001]  Issue \u5217\u8868 (open|closed|all)\n"
            "  !gh prs <owner/repo> [\u72b6\u6001]     PR \u5217\u8868\n"
            "  !gh issue <owner/repo> <\u7f16\u53f7>   Issue/PR \u8be6\u60c5\n"
            "  !gh releases <owner/repo>      Release \u5217\u8868\n"
            "  !gh user <\u7528\u6237\u540d>               \u7528\u6237\u4fe1\u606f\n"
            "  !gh search <\u5173\u952e\u8bcd>             \u641c\u7d22\u4ed3\u5e93\n"
            "  \u2500\u2500 \u4e8b\u4ef6\u63a8\u9001 \u2500\u2500\n"
            "  !gh sub <owner/repo> [\u4e8b\u4ef6...]  \u8ba2\u9605\u4e8b\u4ef6\u63a8\u9001\u5230\u672c\u4f1a\u8bdd\n"
            "      \u4e8b\u4ef6\u53ef\u9009\uff1apush/pr/issue/release/star/fork\uff08\u9ed8\u8ba4\u5168\u90e8\uff09\n"
            "  !gh unsub <owner/repo>         \u9000\u8ba2\n"
            "  !gh subs                       \u67e5\u770b\u672c\u4f1a\u8bdd\u8ba2\u9605\n"
            "  !gh help                       \u663e\u793a\u5e2e\u52a9\n"
            "\n\u63d0\u793a\uff1a\u5728\u63d2\u4ef6\u914d\u7f6e\u91cc\u586b github_token \u53ef\u89e3\u9664\u901f\u7387\u9650\u5236\u5e76\u8bbf\u95ee\u79c1\u6709\u4ed3\u5e93\u3002"
        ),
    },
}


def get_text(language: str, key: str, **kwargs) -> str:
    """Return the translated string for (language, key), formatted with kwargs.

    Falls back to en_US when the language or key is missing.
    """
    if language not in TRANSLATIONS:
        language = "en_US"
    text = TRANSLATIONS.get(language, {}).get(key, "")
    if not text:
        text = TRANSLATIONS["en_US"].get(key, key)
    if kwargs:
        try:
            return text.format(**kwargs)
        except Exception:
            return text
    return text
