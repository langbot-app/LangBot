"""Bounded local transfers for Windows host workspaces."""

import io
import os
import stat
import tempfile
import zipfile
from pathlib import Path, PureWindowsPath


def _info(path):
    info = os.lstat(path)
    if (
        stat.S_ISLNK(info.st_mode)
        or getattr(info, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT
    ):
        raise ValueError("Workspace contains a link or reparse point")
    return info


def _path(root, relative="", *, parents=False, missing=False):
    root = Path(root)
    for ancestor in (*reversed(root.parents), root):
        _info(ancestor)
    path = root
    parts = relative.split("/") if relative else []
    for index, part in enumerate(parts):
        if (
            not part
            or part.endswith((".", " "))
            or any(c in part for c in '\\:<>"|?*')
            or PureWindowsPath(part).is_reserved()
        ):
            raise ValueError("Invalid Windows workspace path")
        path = path / part
        try:
            _info(path)
        except FileNotFoundError:
            if parents and index < len(parts) - 1:
                path.mkdir()
                _info(path)
            elif not (missing and index == len(parts) - 1):
                raise
        if os.path.commonpath(
            [os.path.realpath(path), os.path.realpath(root)]
        ) != os.path.realpath(root):
            raise ValueError("Path escapes workspace")
    return path


def _regular(info):
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
        raise ValueError("Workspace transfer requires a regular file with one link")


def read(root, relative, max_bytes):
    if max_bytes < 0:
        raise ValueError("Invalid transfer size limit")
    path = _path(root, relative)
    expected = _info(path)
    _regular(expected)
    with path.open("rb") as source:
        info = os.fstat(source.fileno())
        _regular(info)
        if not os.path.samestat(expected, info) or info.st_size > max_bytes:
            raise ValueError(
                "Workspace file changed or exceeds the transfer size limit"
            )
        data = source.read(max_bytes + 1)
        if len(data) > max_bytes:
            raise ValueError("Workspace file exceeds the transfer size limit")
        return data


def write(root, relative, content):
    path = _path(root, relative, parents=True, missing=True)
    try:
        _regular(_info(path))
    except FileNotFoundError:
        pass
    fd, temp = tempfile.mkstemp(dir=path.parent, prefix=".langbot-transfer-")
    try:
        with os.fdopen(fd, "wb") as target:
            target.write(content)
            target.flush()
            os.fsync(target.fileno())
        os.replace(temp, _path(root, relative, missing=True))
    finally:
        Path(temp).unlink(missing_ok=True)


def _walk(root, relative=""):
    with os.scandir(_path(root, relative)) as children:
        for child in children:
            name = relative + "/" + child.name if relative else child.name
            info = _info(_path(root, name))
            yield name, info
            if stat.S_ISDIR(info.st_mode):
                yield from _walk(root, name)


def usage(root, stop_after_bytes, max_entries):
    total = count = 0
    for _, info in _walk(root):
        count += 1
        if count > max_entries:
            return total, count, True
        if not stat.S_ISDIR(info.st_mode):
            total += info.st_size
        if total > stop_after_bytes:
            break
    return total, count, False


def archive_directory(root, relative, limit):
    class BoundedArchive(io.BytesIO):
        def write(self, data):
            if self.tell() + len(data) > limit:
                raise ValueError("Directory archive exceeds the transfer size limit")
            return super().write(data)

    directory = _path(root, relative)
    total = 0
    with BoundedArchive() as output:
        with zipfile.ZipFile(output, "w", allowZip64=False) as archive:
            for count, (name, info) in enumerate(_walk(directory), 1):
                if count > 512 or name.count("/") > 16:
                    raise ValueError(
                        "Directory archive exceeds the entry or depth limit"
                    )
                if stat.S_ISDIR(info.st_mode):
                    archive.writestr(name + "/", b"")
                else:
                    data = read(directory, name, min(limit, 16 * 1024 * 1024))
                    total += len(data)
                    if total > 64 * 1024 * 1024:
                        raise ValueError(
                            "Directory archive exceeds the expanded size limit"
                        )
                    archive.writestr(name, data)
        return output.getvalue()


def _owned(owner):
    root, dev, ino = owner
    path = _path(root)
    info = _info(path)
    if not stat.S_ISDIR(info.st_mode) or (info.st_dev, info.st_ino) != (dev, ino):
        raise ValueError("Runtime workspace ownership changed during cleanup")
    return path


def _clear_tree(root, relative, count):
    path = _path(root, relative)
    with os.scandir(path) as children:
        for child in children:
            count += 1
            if count > 100_000:
                raise ValueError("Workspace cleanup exceeds the entry limit")
            name = relative + "/" + child.name if relative else child.name
            target = _path(root, name)
            if stat.S_ISDIR(_info(target).st_mode):
                count = _clear_tree(root, name, count)
                _path(root, name).rmdir()
            else:
                target.unlink()
    return count


def clear(owner):
    _clear_tree(_owned(owner), "", 0)


def remove_owned(owner, empty_only):
    try:
        _owned(owner)
    except FileNotFoundError:
        return
    if not empty_only:
        clear(owner)
    _owned(owner).rmdir()


def run_files(owner, scope, remove=False):
    root = _owned(owner)
    count = 0
    for prefix in ("inbox", "outbox", ".langbot-snapshots"):
        relative = prefix + "/" + scope
        try:
            path = _path(root, relative)
        except FileNotFoundError:
            continue
        if not remove:
            return True
        if stat.S_ISDIR(_info(path).st_mode):
            count = _clear_tree(root, relative, count)
            _path(root, relative).rmdir()
        else:
            path.unlink()
    return False
