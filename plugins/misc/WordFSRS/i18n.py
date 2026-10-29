# -*- coding: utf-8 -*-
"""Internationalization for the WordFSRS plugin (en_US + zh_Hans)."""

TRANSLATIONS = {
    "en_US": {
        # add_word
        "add.usage": "Usage: !word add <word> [meaning]",
        "add.updated": "\u300c{word}\u300d already exists; meaning updated to: {meaning}",
        "add.exists": "\u300c{word}\u300d is already in your deck.",
        "add.meaning_line": "Meaning: {meaning}\n",
        "add.ok": "Added \u300c{word}\u300d to your deck \u2705\n{tip}Deck now has {total} word(s).",
        # remove_word
        "del.not_found": "\u300c{word}\u300d is not in your deck.",
        "del.ok": "Deleted \u300c{word}\u300d. Deck now has {total} word(s).",
        # next_due / questions
        "review.empty": "Your deck is empty. Add words with !word add <word> [meaning].",
        "review.new_limit": "Daily new-word limit reached ({limit}).\n{soonest}",
        "review.none_due": "\U0001f389 Nothing to review right now!\n{soonest}",
        "soonest.all_done": "All caught up.",
        "soonest.next": "Next review: {when}.",
        # _fmt_when
        "when.now": "now",
        "when.minutes": "in {n} min",
        "when.hours": "in {h} h",
        "when.days": "in {d} d",
        # _format_question
        "q.kind_review": "Review",
        "q.kind_new": "New",
        "q.body": "[{kind}] {word}\nDo you remember its meaning? When ready:\n  !word grade {word} <1 forgot|2 hard|3 good|4 easy>\n  (or !word show {word} to see the answer)",
        "q.new_meaning": "\n\nThis is a new word. Meaning: {meaning}",
        # show_answer
        "show.no_meaning": "(no meaning recorded)",
        "show.ok": "\u300c{word}\u300d meaning: {meaning}\nAfter reviewing, grade with !word grade {word} <1-4>.",
        # grade
        "grade.not_found": "\u300c{word}\u300d is not in your deck; cannot grade.",
        "grade.invalid": "Invalid rating. Use 1/2/3/4 or again/hard/good/easy:\n  1=forgot  2=hard  3=good  4=easy",
        "grade.rating_again": "forgot",
        "grade.rating_hard": "hard",
        "grade.rating_good": "good",
        "grade.rating_easy": "easy",
        "grade.ok": "Recorded \u300c{word}\u300d{meaning} \u2192 {rating} \u2705\nNext review: {when}.\nContinue: !word review",
        "grade.meaning_paren": " ({meaning})",
        # stats
        "stats.empty": "Your deck is empty. Start with !word add <word> [meaning].",
        "stats.unlimited": "unlimited",
        "stats.body": "\U0001f4ca Vocabulary stats\n  Total: {total}\n  Due now: {due}\n  New (unseen): {new}\n  In review: {learning}\n  Today's new: {intro} / {limit}",
        # list_words
        "list.empty": "Your deck is empty.",
        "list.no_more": "No more.",
        "list.header": "\U0001f4d2 Deck (sorted by next review):",
        "list.status_new": "new",
        "list.item": "  \u2022 {word}{meaning} [{status}]",
        "list.footer": "Page {page}/{total_pages} \u00b7 {count} words",
        # help (word.py)
        "help": (
            "\U0001f4d6 FSRS vocabulary trainer:\n"
            "  !word add <word> [meaning]   Add a word\n"
            "  !word review                 Start/continue review (next due word)\n"
            "  !word show <word>            Show a word's meaning (answer)\n"
            "  !word grade <word> <1-4>     Grade recall 1 forgot/2 hard/3 good/4 easy\n"
            "  !word stats                  Show statistics\n"
            "  !word list [page]            List the deck\n"
            "  !word del <word>             Delete a word\n"
            "  !word help                   Show this help\n"
            "\nScheduling powered by the FSRS algorithm (the model behind Maimemo)."
        ),
        "cmd.add_usage": "Usage: !word add <word> [meaning]",
        "cmd.show_usage": "Usage: !word show <word>",
        "cmd.grade_usage": "Usage: !word grade <word> <1 forgot|2 hard|3 good|4 easy>",
        "cmd.del_usage": "Usage: !word del <word>",
    },
    "zh_Hans": {
        # add_word
        "add.usage": "\u7528\u6cd5\uff1a!word add <\u5355\u8bcd> [\u91ca\u4e49]",
        "add.updated": "\u300c{word}\u300d\u5df2\u5b58\u5728\uff0c\u5df2\u66f4\u65b0\u91ca\u4e49\u4e3a\uff1a{meaning}",
        "add.exists": "\u300c{word}\u300d\u5df2\u5728\u8bcd\u5e93\u4e2d\uff0c\u65e0\u9700\u91cd\u590d\u6dfb\u52a0\u3002",
        "add.meaning_line": "\u91ca\u4e49\uff1a{meaning}\n",
        "add.ok": "\u5df2\u6dfb\u52a0\u300c{word}\u300d\u5230\u8bcd\u5e93 \u2705\n{tip}\u5f53\u524d\u8bcd\u5e93\u5171 {total} \u4e2a\u5355\u8bcd\u3002",
        # remove_word
        "del.not_found": "\u8bcd\u5e93\u91cc\u6ca1\u6709\u300c{word}\u300d\u3002",
        "del.ok": "\u5df2\u5220\u9664\u300c{word}\u300d\u3002\u5f53\u524d\u8bcd\u5e93\u5171 {total} \u4e2a\u5355\u8bcd\u3002",
        # next_due / questions
        "review.empty": "\u8bcd\u5e93\u662f\u7a7a\u7684\uff0c\u5148\u7528 !word add <\u5355\u8bcd> [\u91ca\u4e49] \u6dfb\u52a0\u4e00\u4e9b\u5427\u3002",
        "review.new_limit": "\u4eca\u65e5\u65b0\u8bcd\u5df2\u8fbe\u4e0a\u9650\uff08{limit} \u4e2a\uff09\u3002\n{soonest}",
        "review.none_due": "\U0001f389 \u6682\u65f6\u6ca1\u6709\u9700\u8981\u590d\u4e60\u7684\u5355\u8bcd\uff01\n{soonest}",
        "soonest.all_done": "\u5168\u90e8\u5b66\u5b8c\u5566\u3002",
        "soonest.next": "\u4e0b\u4e00\u6b21\u590d\u4e60\uff1a{when}\u3002",
        # _fmt_when
        "when.now": "\u73b0\u5728\u53ef\u590d\u4e60",
        "when.minutes": "{n} \u5206\u949f\u540e",
        "when.hours": "{h} \u5c0f\u65f6\u540e",
        "when.days": "{d} \u5929\u540e",
        # _format_question
        "q.kind_review": "\u590d\u4e60",
        "q.kind_new": "\u65b0\u8bcd",
        "q.body": "\u3010{kind}\u3011 {word}\n\u4f60\u8fd8\u8bb0\u5f97\u5b83\u7684\u610f\u601d\u5417\uff1f\u60f3\u597d\u540e\u7528\uff1a\n  !word grade {word} <1\u5fd8\u4e86|2\u96be|3\u4f1a|4\u7b80\u5355>\n  \uff08\u4e5f\u53ef\u76f4\u63a5 !word show {word} \u770b\u7b54\u6848\uff09",
        "q.new_meaning": "\n\n\u8fd9\u662f\u4e2a\u65b0\u8bcd\uff0c\u91ca\u4e49\uff1a{meaning}",
        # show_answer
        "show.no_meaning": "\uff08\u672a\u586b\u5199\u91ca\u4e49\uff09",
        "show.ok": "\u300c{word}\u300d\u91ca\u4e49\uff1a{meaning}\n\u590d\u4e60\u540e\u7528 !word grade {word} <1-4> \u8bc4\u5206\u3002",
        # grade
        "grade.not_found": "\u8bcd\u5e93\u91cc\u6ca1\u6709\u300c{word}\u300d\uff0c\u65e0\u6cd5\u8bc4\u5206\u3002",
        "grade.invalid": "\u8bc4\u5206\u65e0\u6548\u3002\u8bf7\u7528 1/2/3/4 \u6216 again/hard/good/easy\uff1a\n  1=\u5fd8\u4e86  2=\u96be  3=\u4f1a  4=\u7b80\u5355",
        "grade.rating_again": "\u5fd8\u4e86",
        "grade.rating_hard": "\u96be",
        "grade.rating_good": "\u4f1a",
        "grade.rating_easy": "\u7b80\u5355",
        "grade.ok": "\u5df2\u8bb0\u5f55\u300c{word}\u300d{meaning} \u2192 {rating} \u2705\n\u4e0b\u6b21\u590d\u4e60\uff1a{when}\u3002\n\u7ee7\u7eed\uff1a!word review",
        "grade.meaning_paren": "\uff08{meaning}\uff09",
        # stats
        "stats.empty": "\u8bcd\u5e93\u662f\u7a7a\u7684\u3002\u7528 !word add <\u5355\u8bcd> [\u91ca\u4e49] \u5f00\u59cb\u5427\u3002",
        "stats.unlimited": "\u4e0d\u9650",
        "stats.body": "\U0001f4ca \u80cc\u5355\u8bcd\u7edf\u8ba1\n  \u603b\u8bcd\u6570\uff1a{total}\n  \u5f85\u590d\u4e60\uff08\u5230\u671f\uff09\uff1a{due}\n  \u65b0\u8bcd\uff08\u672a\u5b66\uff09\uff1a{new}\n  \u5df2\u8fdb\u5165\u590d\u4e60\uff1a{learning}\n  \u4eca\u65e5\u65b0\u8bcd\uff1a{intro} / {limit}",
        # list_words
        "list.empty": "\u8bcd\u5e93\u662f\u7a7a\u7684\u3002",
        "list.no_more": "\u6ca1\u6709\u66f4\u591a\u4e86\u3002",
        "list.header": "\U0001f4d2 \u8bcd\u5e93\uff08\u6309\u4e0b\u6b21\u590d\u4e60\u65f6\u95f4\u6392\u5e8f\uff09\uff1a",
        "list.status_new": "\u65b0\u8bcd",
        "list.item": "  \u2022 {word}{meaning} [{status}]",
        "list.footer": "\u7b2c {page}/{total_pages} \u9875 \u00b7 \u5171 {count} \u8bcd",
        # help (word.py)
        "help": (
            "\U0001f4d6 FSRS \u80cc\u5355\u8bcd \u7528\u6cd5\uff1a\n"
            "  !word add <\u5355\u8bcd> [\u91ca\u4e49]   \u6dfb\u52a0\u5355\u8bcd\n"
            "  !word review              \u5f00\u59cb/\u7ee7\u7eed\u590d\u4e60\uff08\u53d6\u51fa\u4e0b\u4e00\u4e2a\u5230\u671f\u7684\u8bcd\uff09\n"
            "  !word show <\u5355\u8bcd>         \u67e5\u770b\u67d0\u8bcd\u91ca\u4e49\uff08\u770b\u7b54\u6848\uff09\n"
            "  !word grade <\u5355\u8bcd> <1-4>  \u7ed9\u590d\u4e60\u8bc4\u5206 1\u5fd8\u4e86/2\u96be/3\u4f1a/4\u7b80\u5355\n"
            "  !word stats               \u67e5\u770b\u7edf\u8ba1\n"
            "  !word list [\u9875\u7801]         \u5217\u51fa\u8bcd\u5e93\n"
            "  !word del <\u5355\u8bcd>          \u5220\u9664\u5355\u8bcd\n"
            "  !word help                \u663e\u793a\u672c\u5e2e\u52a9\n"
            "\n\u8bb0\u5fc6\u8c03\u5ea6\u57fa\u4e8e FSRS \u7b97\u6cd5\uff08\u58a8\u58a8\u80cc\u5355\u8bcd\u540c\u6b3e\uff09\u3002"
        ),
        "cmd.add_usage": "\u7528\u6cd5\uff1a!word add <\u5355\u8bcd> [\u91ca\u4e49]",
        "cmd.show_usage": "\u7528\u6cd5\uff1a!word show <\u5355\u8bcd>",
        "cmd.grade_usage": "\u7528\u6cd5\uff1a!word grade <\u5355\u8bcd> <1\u5fd8\u4e86|2\u96be|3\u4f1a|4\u7b80\u5355>",
        "cmd.del_usage": "\u7528\u6cd5\uff1a!word del <\u5355\u8bcd>",
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
