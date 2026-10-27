#!/usr/bin/env python3
"""Advance only the landing docs gitlink, then sync its production fork."""
import argparse
import json
import os
import urllib.error
import urllib.request

SOURCE = "langbot-app/langbot-docs"
TARGET = "langbot-app/langbot-landing-page"
DEPLOY = "RockChinQ/LangBot-LandingPage-Vue"


def api(method, path, data=None):
    token = os.environ["GH_TOKEN"]
    request = urllib.request.Request(
        "https://api.github.com/repos/" + path,
        data=None if data is None else json.dumps(data).encode(),
        headers={"Authorization": "Bea" + "rer " + token,
                 "Accept": "application/vnd.github+json",
                 "Content-Type": "application/json"},
        method=method,
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def head(call, repo):
    return call("GET", repo + "/git/ref/heads/main")["object"]["sha"]


def sync(call=api, dry_run=False):
    for attempt in range(5):
        source = head(call, SOURCE)  # Coalesce queued events onto current main.
        parent = head(call, TARGET)
        commit = call("GET", TARGET + "/git/commits/" + parent)
        tree = call("GET", TARGET + "/git/trees/" + commit["tree"]["sha"])
        entry = next(item for item in tree["tree"] if item["path"] == "docs")
        if entry["mode"] != "160000" or entry["type"] != "commit":
            raise RuntimeError("Landing docs is not a submodule")
        if entry["sha"] == source:
            print("Landing docs already at " + source)
            break
        comparison = call("GET", SOURCE + "/compare/" + entry["sha"] + "..." + source)
        if comparison["status"] != "ahead":
            raise RuntimeError("Refusing a docs rewind or divergent history")
        print("Updating landing docs: " + entry["sha"] + " -> " + source)
        if dry_run:
            return
        updated = call("POST", TARGET + "/git/trees", {
            "base_tree": commit["tree"]["sha"],
            "tree": [{"path": "docs", "mode": "160000", "type": "commit", "sha": source}],
        })
        candidate = call("POST", TARGET + "/git/commits", {
            "message": "docs: sync langbot-docs@" + source[:12],
            "tree": updated["sha"], "parents": [parent],
            "author": {"name": "github-actions[bot]", "email": "41898282+github-actions[bot]@users.noreply.github.com"},
        })
        try:
            call("PATCH", TARGET + "/git/refs/heads/main", {"sha": candidate["sha"], "force": False})
        except urllib.error.HTTPError as error:
            if error.code in (409, 422) and attempt < 4:
                continue  # Rebuild atop current target; never force-push.
            raise
        actual = call("GET", TARGET + "/contents/docs?ref=main")
        if actual["sha"] != source:
            raise RuntimeError("Landing submodule readback mismatch")
        print("Published landing commit " + candidate["sha"])
        break
    else:
        raise RuntimeError("Landing branch kept changing")
    if dry_run:
        return
    # Also retry this on no-op runs, so failed deployment sync is recoverable.
    call("POST", DEPLOY + "/merge-upstream", {"branch": "main"})
    if head(call, DEPLOY) != head(call, TARGET):
        raise RuntimeError("Production fork readback mismatch")
    print("Production fork matches landing main")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    sync(dry_run=parser.parse_args().dry_run)
