from __future__ import annotations

import asyncio
import json
import os
import uuid

from langbot_plugin.api.definition.plugin import BasePlugin

STORAGE_KEY = 'faq_entries'

# Process-cache slot used when no installation binding is available (dedicated
# placement). It maps to the legacy storage key so existing dedicated installs
# keep reading their own rows.
DEDICATED_SCOPE = 'dedicated'

# Written by the SDK worker launcher. A shared worker must always carry a trusted
# invocation binding; without one it must refuse to touch tenant state instead of
# falling back to a binding-less scope shared by every installation.
RUNTIME_PROFILE_ENV = 'LANGBOT_PLUGIN_RUNTIME_PROFILE'


def installation_scope(binding) -> str:
    """Return the stable scope token for one installation binding.

    Only the installation identity triple is used. ``runtime_revision`` changes on
    every worker upgrade, so including it would orphan the tenant's persisted rows
    after a restart of the loader.
    """

    return f'{binding.instance_uuid}:{binding.workspace_uuid}:{binding.installation_uuid}'


def storage_key(scope: str) -> str:
    """Return the plugin-storage key for one scope.

    Host rows are keyed by ``[instance, workspace, owner_type, owner, key]`` with no
    installation dimension, so the installation scope has to live in the plugin's
    own key. The binding-less dedicated scope keeps the legacy key unchanged.
    """

    if scope == DEDICATED_SCOPE:
        return STORAGE_KEY
    return f'{STORAGE_KEY}:{scope}'


class _InstallationState:
    """Process-local FAQ data belonging to exactly one installation binding.

    The same plugin object serves every installation of the artifact, so entries
    are cached per binding and dropped in ``on_installation_revoked``.
    """

    __slots__ = ('scope', 'entries', 'lock', 'loaded')

    def __init__(self, scope: str) -> None:
        self.scope = scope
        self.entries: list[dict[str, str]] = []
        self.lock = asyncio.Lock()
        self.loaded = False


class FAQManagerPlugin(BasePlugin):
    """FAQ Manager — maintain a set of question-answer pairs.

    Data is persisted via plugin storage so it survives restarts. The Page
    component provides a CRUD UI; the Tool component lets the LLM search entries
    during conversations.

    Entries are held per installation binding (the Page, Tool and EventListener
    components all share this plugin object) and stored under
    ``faq_entries:<instance>:<workspace>:<installation>`` so two installations of
    this artifact can never read each other's rows. A dedicated, binding-less
    worker keeps the legacy ``faq_entries`` key.
    """

    def __init__(self):
        super().__init__()
        self._states: dict[str, _InstallationState] = {}

    # ----------------------------------------------------------------- lifecycle

    async def initialize(self) -> None:
        """Process-wide initialization only.

        Under shared placement this runs once per worker with an empty config and
        no installation context, so tenant entries are loaded lazily per
        invocation (and per binding) instead.
        """

        return None

    async def on_installation_revoked(self, binding) -> None:
        """Drop the cache of the revoked installation; no Host API is available."""

        self._states.pop(installation_scope(binding), None)

    # --------------------------------------------------------------- state scope

    def _current_scope(self) -> str:
        binding = self.get_installation_binding()
        if binding is not None:
            return installation_scope(binding)
        if os.environ.get(RUNTIME_PROFILE_ENV) == 'shared':
            raise RuntimeError(
                'shared invocation has no trusted installation binding; '
                'refusing to read or write tenant state'
            )
        return DEDICATED_SCOPE

    async def _state(self) -> _InstallationState:
        """Return the invoking installation's state, loading it on first use."""

        scope = self._current_scope()
        st = self._states.get(scope)
        if st is None:
            st = _InstallationState(scope)
            self._states[scope] = st
        if not st.loaded:
            async with st.lock:
                if not st.loaded:
                    await self._load(st)
                    st.loaded = True
        return st

    async def _load(self, st: _InstallationState) -> None:
        try:
            raw = await self.get_plugin_storage(storage_key(st.scope))
            st.entries = json.loads(raw.decode('utf-8'))
            print(
                f'[FAQManager] Loaded {len(st.entries)} entries from storage for scope {st.scope}',
                flush=True,
            )
        except Exception as e:
            print(f'[FAQManager] Failed to load storage for scope {st.scope}: {e}', flush=True)
            st.entries = []

    async def persist(self) -> None:
        """Persist the invoking installation's entries."""

        await self._persist(await self._state())

    async def _persist(self, st: _InstallationState) -> None:
        await self.set_plugin_storage(
            storage_key(st.scope),
            json.dumps(st.entries, ensure_ascii=False).encode('utf-8'),
        )

    # -------------------------------------------------------------------- tenant

    async def get_entries(self) -> list[dict[str, str]]:
        """Return the invoking installation's FAQ entries."""

        return (await self._state()).entries

    async def search(self, query: str) -> list[dict[str, str]]:
        """Simple keyword search across questions and answers."""
        st = await self._state()
        q = query.lower()
        return [
            e for e in st.entries
            if q in e['question'].lower() or q in e['answer'].lower()
        ]

    async def add_entry(self, question: str, answer: str) -> dict[str, str]:
        st = await self._state()
        entry = {
            'id': uuid.uuid4().hex[:8],
            'question': question,
            'answer': answer,
        }
        st.entries.append(entry)
        return entry

    async def update_entry(self, entry_id: str, question: str | None, answer: str | None) -> dict[str, str] | None:
        st = await self._state()
        for entry in st.entries:
            if entry['id'] == entry_id:
                if question is not None:
                    entry['question'] = question.strip()
                if answer is not None:
                    entry['answer'] = answer.strip()
                return entry
        return None

    async def delete_entry(self, entry_id: str) -> bool:
        st = await self._state()
        before = len(st.entries)
        st.entries = [e for e in st.entries if e['id'] != entry_id]
        return len(st.entries) < before
