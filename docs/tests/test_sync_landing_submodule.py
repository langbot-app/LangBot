"""Offline API-contract tests; the workflow run verifies real GitHub writes."""
import importlib.util
from pathlib import Path
import unittest
from urllib.error import HTTPError

spec = importlib.util.spec_from_file_location("sync_landing", Path(__file__).resolve().parents[1] / "scripts/sync-landing-submodule.py")
sync = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sync)


class FakeAPI:
    def __init__(self, already=False, conflict=False, status="ahead"):
        self.calls = []
        self.pin = "new-docs" if already else "old-docs"
        self.landing = "landing-parent"
        self.deploy = "old-deploy"
        self.conflict = conflict
        self.status = status

    def __call__(self, method, path, data=None):
        self.calls.append((method, path, data))
        if path.endswith("/git/ref/heads/main"):
            sha = "new-docs" if path.startswith(sync.SOURCE + "/") else self.deploy if path.startswith(sync.DEPLOY + "/") else self.landing
            return {"object": {"sha": sha}}
        if method == "GET" and "/git/commits/" in path:
            return {"tree": {"sha": "old-tree"}}
        if method == "GET" and "/git/trees/" in path:
            return {"tree": [{"path": "docs", "mode": "160000", "type": "commit", "sha": self.pin}]}
        if "/compare/" in path:
            return {"status": self.status}
        if method == "POST" and path.endswith("/git/trees"):
            return {"sha": "new-tree"}
        if method == "POST" and path.endswith("/git/commits"):
            return {"sha": "new-landing"}
        if method == "PATCH":
            if self.conflict:
                self.conflict = False
                self.landing = "concurrent-landing"
                raise HTTPError(path, 422, "not fast forward", {}, None)
            self.landing = data["sha"]
            self.pin = "new-docs"
            return {}
        if "/contents/docs" in path:
            return {"sha": self.pin}
        if path.endswith("/merge-upstream"):
            self.deploy = self.landing
            return {}
        raise AssertionError((method, path, data))


class SyncTests(unittest.TestCase):
    def test_updates_only_gitlink_and_preserves_parent(self):
        api = FakeAPI()
        sync.sync(api)
        tree = next(d for m, p, d in api.calls if m == "POST" and p.endswith("/git/trees"))
        self.assertEqual(tree, {"base_tree": "old-tree", "tree": [{"path": "docs", "mode": "160000", "type": "commit", "sha": "new-docs"}]})
        commit = next(d for m, p, d in api.calls if m == "POST" and p.endswith("/git/commits"))
        self.assertEqual(commit["parents"], ["landing-parent"])
        self.assertEqual(api.deploy, api.landing)
        self.assertTrue(all(d["force"] is False for m, p, d in api.calls if m == "PATCH"))

    def test_noop_still_repairs_deploy_fork(self):
        api = FakeAPI(already=True)
        sync.sync(api)
        self.assertFalse(any(m == "PATCH" for m, p, d in api.calls))
        self.assertEqual(api.deploy, api.landing)

    def test_race_retries_on_new_parent(self):
        api = FakeAPI(conflict=True)
        sync.sync(api)
        commits = [d for m, p, d in api.calls if m == "POST" and p.endswith("/git/commits")]
        self.assertEqual(commits[-1]["parents"], ["concurrent-landing"])

    def test_dry_run_has_no_writes(self):
        api = FakeAPI()
        sync.sync(api, dry_run=True)
        self.assertTrue(all(m == "GET" for m, p, d in api.calls))

    def test_rewind_or_divergence_is_rejected(self):
        for status in ["behind", "diverged"]:
            api = FakeAPI(status=status)
            with self.assertRaises(RuntimeError):
                sync.sync(api)
            self.assertTrue(all(m == "GET" for m, p, d in api.calls))
