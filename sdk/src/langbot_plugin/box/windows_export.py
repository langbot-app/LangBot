"""Native Windows operations used by Core's sandbox export scripts."""

import base64
import hashlib
import json
import os
import re
import stat
import sys
import uuid

from .file_io import workspace_relative_path
from .windows_file_io import _info, _path, _regular, _walk, read, write


def _limit(kind, limit, actual, path):
    if actual > limit:
        print(
            "LANGBOT_OUTBOX_LIMIT:"
            + json.dumps(dict(kind=kind, limit=limit, actual=actual, path=path)),
            file=sys.stderr,
        )
        raise SystemExit(73)


def _snapshot(root, virtual):
    relative = workspace_relative_path("/workspace", virtual)
    if not re.fullmatch(
        r"\.langbot-snapshots/[^/]+/\.langbot-export-[0-9a-f]{32}", relative
    ):
        raise ValueError("Invalid export snapshot root")
    return relative


def _selected(root, settings):
    result = []
    total = 0
    snapshot = settings["snapshot_root"]
    if snapshot:
        relative = _snapshot(root, snapshot)
        directory = _path(root, relative, parents=True, missing=True)
        directory.mkdir()
        journal = relative + "/.manifest.json"
        identities = {}
        write(root, journal, b"{}")
    for index, virtual in enumerate(settings["paths"]):
        source = workspace_relative_path("/workspace", virtual)
        path = _path(root, source)
        info = _info(path)
        _regular(info)
        _limit("file_bytes", settings["max_file_bytes"], info.st_size, virtual)
        _limit(
            "collection_bytes",
            settings["max_total_bytes"],
            total + info.st_size,
            virtual,
        )
        data = read(root, source, settings["max_file_bytes"])
        total += len(data)
        _limit("collection_bytes", settings["max_total_bytes"], total, virtual)
        digest = hashlib.sha256(data).hexdigest()
        if settings["cleanup"] is not None:
            if settings["cleanup"].get(virtual) != digest or not os.path.samestat(
                info, _info(_path(root, source))
            ):
                raise ValueError("File changed after acceptance; retained: " + virtual)
            path.unlink()
        elif snapshot:
            name = uuid.uuid4().hex + ".bin"
            write(root, relative + "/" + name, data)
            identity = _info(_path(root, relative + "/" + name))
            identities[name] = [identity.st_dev, identity.st_ino]
            write(root, journal, json.dumps(identities).encode())
            result.append(
                dict(
                    index=index,
                    name=virtual,
                    size=len(data),
                    sha256=digest,
                    snapshot_path=snapshot + "/" + name,
                )
            )
        else:
            result.append(
                dict(name=virtual, b64=base64.b64encode(data).decode("ascii"))
            )
    return result


def export(operation, settings):
    root = os.environ["LANGBOT_BOX_WORKSPACE"]
    if operation == "selected":
        _limit("file_count", 100, len(settings["paths"]), "")
        return _selected(root, settings)
    if operation == "cleanup_snapshot":
        relative = _snapshot(root, settings)
        try:
            directory = _path(root, relative)
        except FileNotFoundError:
            return []
        journal = relative + "/.manifest.json"
        identities = json.loads(read(root, journal, 65536))
        if any(
            not re.fullmatch("[0-9a-f]{32}[.]bin", name) for name in identities
        ) or set(os.listdir(directory)) != {*identities, ".manifest.json"}:
            raise ValueError("Unknown files in export snapshot; retained")
        for name, identity in identities.items():
            info = _info(_path(root, relative + "/" + name))
            if [info.st_dev, info.st_ino] != identity:
                raise ValueError("Export snapshot changed; retained")
        for name in identities:
            _path(root, relative + "/" + name).unlink()
        _path(root, journal).unlink()
        _path(root, relative).rmdir()
        return []
    scope = settings["query"]
    if not scope or "/" in scope or settings["outbox"] != "outbox":
        raise ValueError("Invalid outbox scope")
    relative = "outbox/" + scope
    try:
        directory = _path(root, relative)
    except FileNotFoundError:
        return []
    result = []
    total = directories = 0
    clear = settings["operation"] == "clear"
    entries = []
    for count, (name, info) in enumerate(_walk(directory), 1):
        _limit("entries", 4096 if clear else 512, count, name)
        _limit("depth", 16 if clear else 8, name.count("/"), name)
        if clear:
            entries.append((name, stat.S_ISDIR(info.st_mode)))
        elif stat.S_ISDIR(info.st_mode):
            directories += 1
            _limit("directories", 64, directories, name)
        else:
            _regular(info)
            _limit("file_count", settings["max_files"], len(result) + 1, name)
            _limit("file_bytes", settings["max_file_bytes"], info.st_size, name)
            item = {"name": name}
            size = info.st_size
            if settings["operation"] == "read":
                content = read(directory, name, settings["max_file_bytes"])
                size = len(content)
                item["b64"] = base64.b64encode(content).decode("ascii")
            total += size
            _limit("collection_bytes", settings["max_total_bytes"], total, name)
            result.append(item)
    for name, is_dir in reversed(entries):
        path = _path(root, relative + "/" + name)
        path.rmdir() if is_dir else path.unlink()
    return result
