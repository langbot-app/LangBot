# WordFSRS - Spaced-repetition vocabulary plugin for LangBot.
# Memory scheduling powered by py-fsrs (the FSRS algorithm, the same memory
# model behind Maimemo / 墨墨背单词).
from __future__ import annotations

import os
import sys
import json
import time
import asyncio
import datetime
from typing import TYPE_CHECKING, Any, Optional

from langbot_plugin.api.definition.plugin import BasePlugin

from fsrs import Scheduler, Card, Rating

if TYPE_CHECKING:
    from langbot_plugin.entities.io.context import InstallationBinding

# Allow importing the plugin-level i18n module.
sys.path.insert(0, os.path.dirname(__file__))
from i18n import get_text  # noqa: E402

# Manifest defaults, used when an invocation carries no explicit value.
DEFAULT_LANGUAGE = "en_US"
DEFAULT_DAILY_NEW_LIMIT = 20
DEFAULT_DESIRED_RETENTION = 0.9
RETENTION_MIN = 0.7
RETENTION_MAX = 0.97

# Scope token used when no installation binding is available (dedicated or
# binding-less placement). It maps to the legacy deck key so those workers keep
# reading their own historical rows.
DEDICATED_SCOPE = "dedicated"


def installation_scope(binding: "InstallationBinding") -> str:
    """Return the stable scope token for one installation binding.

    Host storage rows are keyed by ``[instance, workspace, owner_type, owner,
    key]`` with no installation dimension, so the installation scope has to live
    in the plugin's own key. ``runtime_revision`` is deliberately excluded: it
    changes on every worker upgrade and would orphan the tenant's decks.
    """

    return (
        f"{binding.instance_uuid}:{binding.workspace_uuid}:"
        f"{binding.installation_uuid}"
    )


def deck_storage_key(scope: str, session_id: str) -> str:
    """Return the plugin-storage key for one installation scope and session."""

    if scope == DEDICATED_SCOPE:
        return f"deck:{session_id}"
    return f"deck:{scope}:{session_id}"


# Rating aliases users can type after `!word grade <word>`.
RATING_ALIASES: dict[str, Rating] = {
    "1": Rating.Again,
    "again": Rating.Again,
    "wrong": Rating.Again,
    "no": Rating.Again,
    "忘了": Rating.Again,
    "不会": Rating.Again,
    "2": Rating.Hard,
    "hard": Rating.Hard,
    "难": Rating.Hard,
    "模糊": Rating.Hard,
    "3": Rating.Good,
    "good": Rating.Good,
    "ok": Rating.Good,
    "会": Rating.Good,
    "记得": Rating.Good,
    "4": Rating.Easy,
    "easy": Rating.Easy,
    "简单": Rating.Easy,
    "秒了": Rating.Easy,
}


def _now() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


class WordFSRSPlugin(BasePlugin):
    """Entry point and shared state for the WordFSRS plugin.

    One object graph serves every installation of this artifact, so tenant
    settings (language / daily new-card limit / desired retention) are read
    from the *current invocation* config on every use; ``initialize()`` never
    captures them (shared placement initializes it with an empty config).

    All persistent vocabulary data is scoped per *session*
    (``{launcher_type}:{launcher_id}``) so private chats and groups each keep
    their own deck. State is stored as JSON via the plugin KV storage under
    ``deck:{instance}:{workspace}:{installation}:{session}`` because Host rows
    carry no installation dimension; only binding-less (dedicated) workers use
    the legacy ``deck:{session}`` row.
    """

    def __init__(self) -> None:
        super().__init__()
        # Read-modify-write guards, one per installation binding, so a deck
        # load/modify/save sequence cannot interleave with another command of
        # the same installation and lose cards. Released in
        # on_installation_revoked().
        self._deck_locks: dict[str, asyncio.Lock] = {}

    # ---------------------------------------------------------- tenant config

    def _invocation_config(self) -> dict[str, Any]:
        """Settings of the active invocation (or the dedicated worker config)."""
        return self.get_config() or {}

    def get_language(self) -> str:
        return self._invocation_config().get("language") or DEFAULT_LANGUAGE

    def t(self, key: str, **kwargs) -> str:
        return get_text(self.get_language(), key, **kwargs)

    def _daily_new_limit(self) -> int:
        raw = self._invocation_config().get("daily_new_limit")
        if raw is None or raw == "":
            return DEFAULT_DAILY_NEW_LIMIT
        try:
            return max(0, int(raw))
        except (TypeError, ValueError):
            return DEFAULT_DAILY_NEW_LIMIT

    def _desired_retention(self) -> float:
        raw = self._invocation_config().get("desired_retention")
        if raw is None or raw == "":
            return DEFAULT_DESIRED_RETENTION
        try:
            value = float(raw)
        except (TypeError, ValueError):
            return DEFAULT_DESIRED_RETENTION
        return min(RETENTION_MAX, max(RETENTION_MIN, value))

    def _scheduler(self) -> Scheduler:
        """Build a scheduler from the current invocation's retention."""
        return Scheduler(desired_retention=self._desired_retention())

    # -------------------------------------------------------- revocation hook

    def _current_scope(self) -> str:
        """Scope token of the active invocation, or the binding-less scope."""
        binding = self.get_installation_binding()
        return installation_scope(binding) if binding is not None else DEDICATED_SCOPE

    def _deck_lock(self) -> asyncio.Lock:
        key = self._current_scope()
        lock = self._deck_locks.get(key)
        if lock is None:
            lock = asyncio.Lock()
            self._deck_locks[key] = lock
        return lock

    async def on_installation_revoked(self, binding: InstallationBinding) -> None:
        """Release the revoked installation's read-modify-write guard."""
        self._deck_locks.pop(installation_scope(binding), None)

    # ---------------------------------------------------------------- storage

    async def _load_deck(self, session_id: str) -> dict[str, Any]:
        """Load the current installation's deck for one session."""
        key = deck_storage_key(self._current_scope(), session_id)
        try:
            raw = await self.get_plugin_storage(key)
        except Exception:
            raw = None
        if not raw:
            return {"cards": {}, "new_intro": {}}
        try:
            data = json.loads(raw.decode("utf-8") if isinstance(raw, bytes) else raw)
        except Exception:
            return {"cards": {}, "new_intro": {}}
        data.setdefault("cards", {})
        data.setdefault("new_intro", {})  # {date_str: count} of new cards introduced
        return data

    async def _save_deck(self, session_id: str, deck: dict[str, Any]) -> None:
        payload = json.dumps(deck, ensure_ascii=False).encode("utf-8")
        await self.set_plugin_storage(
            deck_storage_key(self._current_scope(), session_id), payload
        )

    # ----------------------------------------------------------------- helpers

    @staticmethod
    def _due_dt(card_entry: dict[str, Any]) -> datetime.datetime:
        card = Card.from_dict(card_entry["fsrs"])
        due = card.due
        if due.tzinfo is None:
            due = due.replace(tzinfo=datetime.timezone.utc)
        return due

    def _is_due(self, card_entry: dict[str, Any], at: datetime.datetime) -> bool:
        return self._due_dt(card_entry) <= at

    def _fmt_when(self, due: datetime.datetime) -> str:
        """Human-friendly 'due in ...' string (localized)."""
        delta = due - _now()
        secs = delta.total_seconds()
        if secs <= 0:
            return self.t("when.now")
        mins = secs / 60
        if mins < 60:
            return self.t("when.minutes", n=int(round(mins)))
        hours = mins / 60
        if hours < 24:
            return self.t("when.hours", h=f"{hours:.1f}")
        days = hours / 24
        return self.t("when.days", d=f"{days:.1f}")

    # ----------------------------------------------------------------- actions

    async def add_word(
        self, session_id: str, word: str, meaning: str = ""
    ) -> tuple[bool, str]:
        """Add a new vocabulary card. Returns (created, message)."""
        word = word.strip()
        if not word:
            return False, self.t("add.usage")
        async with self._deck_lock():
            deck = await self._load_deck(session_id)
            key = word.lower()
            if key in deck["cards"]:
                entry = deck["cards"][key]
                if meaning:
                    entry["meaning"] = meaning
                    await self._save_deck(session_id, deck)
                    return False, self.t("add.updated", word=word, meaning=meaning)
                return False, self.t("add.exists", word=word)
            card = Card()
            deck["cards"][key] = {
                "word": word,
                "meaning": meaning,
                "fsrs": card.to_dict(),
                "added_at": time.time(),
                "reviews": 0,
            }
            await self._save_deck(session_id, deck)
            total = len(deck["cards"])
            tip = self.t("add.meaning_line", meaning=meaning) if meaning else ""
            return True, self.t("add.ok", word=word, tip=tip, total=total)

    async def remove_word(self, session_id: str, word: str) -> str:
        async with self._deck_lock():
            deck = await self._load_deck(session_id)
            key = word.strip().lower()
            if key not in deck["cards"]:
                return self.t("del.not_found", word=word)
            del deck["cards"][key]
            await self._save_deck(session_id, deck)
            return self.t("del.ok", word=word, total=len(deck["cards"]))

    async def next_due(self, session_id: str) -> tuple[Optional[str], str]:
        """Pick the next card to review.

        Priority: cards already due (earliest due first). If none are due but the
        daily new-card budget allows, introduce a brand-new card. Returns
        (card_key, message).
        """
        deck = await self._load_deck(session_id)
        cards = deck["cards"]
        if not cards:
            return None, self.t("review.empty")

        now = _now()
        due_items = []
        new_items = []
        for k, e in cards.items():
            is_new = e.get("reviews", 0) == 0
            if is_new:
                new_items.append((k, e))
            elif self._is_due(e, now):
                due_items.append((k, self._due_dt(e), e))

        if due_items:
            due_items.sort(key=lambda x: x[1])
            k, _, e = due_items[0]
            return k, self._format_question(e, deck, session_id, kind="review")

        if new_items:
            today = now.date().isoformat()
            introduced_today = deck["new_intro"].get(today, 0)
            limit = self._daily_new_limit()
            if limit == 0 or introduced_today < limit:
                k, e = new_items[0]
                return k, self._format_question(e, deck, session_id, kind="new")
            else:
                soonest = self._soonest_msg(cards, now)
                return None, self.t(
                    "review.new_limit", limit=limit, soonest=soonest
                )

        soonest = self._soonest_msg(cards, now)
        return None, self.t("review.none_due", soonest=soonest)

    def _soonest_msg(self, cards: dict, now: datetime.datetime) -> str:
        future = [
            self._due_dt(e)
            for e in cards.values()
            if e.get("reviews", 0) > 0
        ]
        if not future:
            return self.t("soonest.all_done")
        nxt = min(future)
        return self.t("soonest.next", when=self._fmt_when(nxt))

    def _format_question(
        self, entry: dict, deck: dict, session_id: str, kind: str
    ) -> str:
        word = entry["word"]
        kind_label = self.t("q.kind_new") if kind == "new" else self.t("q.kind_review")
        body = self.t("q.body", kind=kind_label, word=word)
        if kind == "new":
            meaning = entry.get("meaning", "")
            if meaning:
                body += self.t("q.new_meaning", meaning=meaning)
        return body

    async def show_answer(self, session_id: str, word: str) -> str:
        deck = await self._load_deck(session_id)
        key = word.strip().lower()
        e = deck["cards"].get(key)
        if not e:
            return self.t("del.not_found", word=word)
        meaning = e.get("meaning") or self.t("show.no_meaning")
        return self.t("show.ok", word=e["word"], meaning=meaning)

    async def grade(
        self, session_id: str, word: str, rating_token: str
    ) -> str:
        async with self._deck_lock():
            deck = await self._load_deck(session_id)
            key = word.strip().lower()
            e = deck["cards"].get(key)
            if not e:
                return self.t("grade.not_found", word=word)
            rating = RATING_ALIASES.get(rating_token.strip().lower())
            if rating is None:
                return self.t("grade.invalid")
            was_new = e.get("reviews", 0) == 0
            card = Card.from_dict(e["fsrs"])
            card, _log = self._scheduler().review_card(card, rating)
            e["fsrs"] = card.to_dict()
            e["reviews"] = e.get("reviews", 0) + 1
            e["last_rating"] = int(rating)

            if was_new:
                today = _now().date().isoformat()
                deck["new_intro"][today] = deck["new_intro"].get(today, 0) + 1

            await self._save_deck(session_id, deck)
        due = card.due
        if due.tzinfo is None:
            due = due.replace(tzinfo=datetime.timezone.utc)
        rating_key = {
            1: "grade.rating_again",
            2: "grade.rating_hard",
            3: "grade.rating_good",
            4: "grade.rating_easy",
        }[int(rating)]
        rating_label = self.t(rating_key)
        meaning = e.get("meaning")
        meaning_line = self.t("grade.meaning_paren", meaning=meaning) if meaning else ""
        return self.t(
            "grade.ok",
            word=e["word"],
            meaning=meaning_line,
            rating=rating_label,
            when=self._fmt_when(due),
        )

    async def stats(self, session_id: str) -> str:
        deck = await self._load_deck(session_id)
        cards = deck["cards"]
        if not cards:
            return self.t("stats.empty")
        now = _now()
        total = len(cards)
        new_cnt = sum(1 for e in cards.values() if e.get("reviews", 0) == 0)
        due_cnt = sum(
            1
            for e in cards.values()
            if e.get("reviews", 0) > 0 and self._is_due(e, now)
        )
        learning = total - new_cnt
        today = now.date().isoformat()
        intro_today = deck["new_intro"].get(today, 0)
        limit = self._daily_new_limit()
        limit_str = self.t("stats.unlimited") if limit == 0 else str(limit)
        return self.t(
            "stats.body",
            total=total,
            due=due_cnt,
            new=new_cnt,
            learning=learning,
            intro=intro_today,
            limit=limit_str,
        )

    async def list_words(self, session_id: str, page: int = 1) -> str:
        deck = await self._load_deck(session_id)
        cards = list(deck["cards"].values())
        if not cards:
            return self.t("list.empty")
        cards.sort(key=lambda e: self._due_dt(e))
        per = 15
        page = max(1, page)
        start = (page - 1) * per
        chunk = cards[start : start + per]
        if not chunk:
            return self.t("list.no_more")
        lines = [self.t("list.header")]
        for e in chunk:
            meaning = e.get("meaning", "")
            mtxt = f" \u2014 {meaning}" if meaning else ""
            if e.get("reviews", 0) == 0:
                status = self.t("list.status_new")
            else:
                status = self._fmt_when(self._due_dt(e))
            lines.append(self.t("list.item", word=e["word"], meaning=mtxt, status=status))
        total_pages = (len(cards) + per - 1) // per
        lines.append(
            self.t("list.footer", page=page, total_pages=total_pages, count=len(cards))
        )
        return "\n".join(lines)

    def __del__(self) -> None:
        pass
