"""Explicit file selection inside a sandbox, with no symlink traversal."""

import textwrap


_SNAPSHOT_HELPERS = textwrap.dedent("""\
    import contextlib, os, stat, json, re
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    def open_parent(path, create=False):
        parts = path.split('/')
        if not path.startswith('/') or '\\\\' in path or '\\x00' in path or any(p in ('', '.', '..') for p in parts[1:]):
            raise ValueError('Expected a normalized absolute sandbox file path: ' + path)
        fd = os.open('/', flags)
        try:
            for part in parts[1:-1]:
                if create:
                    try:
                        os.mkdir(part, mode=0o700, dir_fd=fd)
                    except FileExistsError:
                        pass
                child = os.open(part, flags, dir_fd=fd)
                os.close(fd)
                fd = child
            return fd, parts[-1]
        except BaseException:
            os.close(fd)
            raise

    def snapshot_parent(root, create=False):
        if not re.fullmatch(r'[.]langbot-export-[0-9a-f]{32}', root.rsplit('/', 1)[-1]):
            raise ValueError('Invalid export snapshot root')
        return open_parent(root, create=create)

    def regular_identity(directory, name):
        info = os.stat(name, dir_fd=directory, follow_symlinks=False)
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise ValueError('Unsafe export snapshot file: ' + name)
        return [info.st_dev, info.st_ino]

    def cleanup_snapshot(parent, name, directory, expected, root_identity=None):
        root_info = os.fstat(directory)
        if root_identity is not None and [root_info.st_dev, root_info.st_ino] != root_identity:
            raise ValueError('Export snapshot root changed; retained')
        present = set(os.listdir(directory))
        if present - set(expected):
            raise ValueError('Unknown files in export snapshot; retained')
        for filename in present:
            identity = regular_identity(directory, filename)
            if expected[filename] is not None and identity != expected[filename]:
                raise ValueError('Export snapshot file changed; retained')
        deletion_order = sorted(present, key=lambda filename: filename == '.manifest.jsonl')
        for filename in deletion_order:
            identity = regular_identity(directory, filename)
            if expected[filename] is not None and identity != expected[filename]:
                raise ValueError('Export snapshot file changed; retained')
            os.unlink(filename, dir_fd=directory)
        current = os.stat(name, dir_fd=parent, follow_symlinks=False)
        if (current.st_dev, current.st_ino) != (root_info.st_dev, root_info.st_ino):
            raise ValueError('Export snapshot root changed; retained')
        os.rmdir(name, dir_fd=parent)
    """)


def selected_files_script(paths, *, max_file_bytes, max_total_bytes, cleanup=None, snapshot_root=None):
    if cleanup is not None and snapshot_root is not None:
        raise ValueError('Snapshot and accepted-file cleanup are separate operations')
    settings = dict(
        paths=paths,
        max_file_bytes=max_file_bytes,
        max_total_bytes=max_total_bytes,
        cleanup=cleanup,
        snapshot_root=snapshot_root,
    )
    return (
        f'settings = {settings!r}\n'
        + _SNAPSHOT_HELPERS
        + textwrap.dedent("""\
        import base64, hashlib, sys, uuid
        def reject(kind, limit, actual, path):
            print('LANGBOT_OUTBOX_LIMIT:' + json.dumps(dict(kind=kind, limit=limit, actual=actual, path=path)), file=sys.stderr)
            raise SystemExit(73)

        result = []
        total = 0
        snapshot_parent_fd = snapshot_fd = journal_fd = None
        owned = {}
        planned = []
        try:
            if settings['snapshot_root'] is not None:
                if len(settings['paths']) > 100:
                    reject('file_count', 100, len(settings['paths']), settings['snapshot_root'])
                snapshot_parent_fd, snapshot_name = snapshot_parent(settings['snapshot_root'], create=True)
                os.mkdir(snapshot_name, mode=0o700, dir_fd=snapshot_parent_fd)
                snapshot_fd = os.open(snapshot_name, flags, dir_fd=snapshot_parent_fd)
                planned = [('.tmp-' + uuid.uuid4().hex, uuid.uuid4().hex + '.bin') for _ in settings['paths']]
                owned = {name: None for pair in planned for name in pair}
                journal_fd = os.open('.manifest.jsonl', os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=snapshot_fd)
                owned['.manifest.jsonl'] = regular_identity(snapshot_fd, '.manifest.jsonl')
                root_info = os.fstat(snapshot_fd)
                header = dict(root=[root_info.st_dev, root_info.st_ino], files=list(name for pair in planned for name in pair))
                def record(entry):
                    body = (json.dumps(entry) + '\\n').encode()
                    offset = 0
                    while offset < len(body):
                        written = os.write(journal_fd, body[offset:])
                        if written <= 0:
                            raise OSError('Snapshot journal write made no progress')
                        offset += written
                    os.fsync(journal_fd)
                record(header)
                os.fsync(snapshot_fd)
            for index, path in enumerate(settings['paths']):
                fd, filename = open_parent(path)
                try:
                    file_fd = os.open(filename, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
                    with os.fdopen(file_fd, 'rb') as source:
                        metadata = os.fstat(source.fileno())
                        if not stat.S_ISREG(metadata.st_mode):
                            raise ValueError('Not a regular file: ' + path)
                        if metadata.st_size > settings['max_file_bytes']:
                            reject('file_bytes', settings['max_file_bytes'], metadata.st_size, path)
                        data = source.read(settings['max_file_bytes'] + 1)
                        total += len(data)
                        if len(data) > settings['max_file_bytes']:
                            reject('file_bytes', settings['max_file_bytes'], len(data), path)
                        if total > settings['max_total_bytes']:
                            reject('collection_bytes', settings['max_total_bytes'], total, path)
                        digest = hashlib.sha256(data).hexdigest()
                        if settings['cleanup'] is not None:
                            current = os.stat(filename, dir_fd=fd, follow_symlinks=False)
                            if (current.st_dev, current.st_ino) == (metadata.st_dev, metadata.st_ino) and digest == settings['cleanup'].get(path):
                                os.unlink(filename, dir_fd=fd)
                            else:
                                raise ValueError('File changed after acceptance; retained: ' + path)
                        elif snapshot_fd is not None:
                            temporary, snapshot_file = planned[index]
                            output_fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=snapshot_fd)
                            identity = regular_identity(snapshot_fd, temporary)
                            owned[temporary] = owned[snapshot_file] = identity
                            with os.fdopen(output_fd, 'wb') as output:
                                record(dict(temporary=temporary, final=snapshot_file, identity=identity))
                                output.write(data)
                                output.flush()
                                os.fsync(output.fileno())
                            os.replace(temporary, snapshot_file, src_dir_fd=snapshot_fd, dst_dir_fd=snapshot_fd)
                            os.fsync(snapshot_fd)
                            result.append(dict(index=len(result), name=path, snapshot_path=settings['snapshot_root'] + '/' + snapshot_file, size=len(data), sha256=digest))
                        else:
                            result.append({'name': path, 'b64': base64.b64encode(data).decode('ascii')})
                finally:
                    os.close(fd)
            print(json.dumps(result))
        except BaseException:
            if snapshot_fd is not None:
                try:
                    cleanup_snapshot(snapshot_parent_fd, snapshot_name, snapshot_fd, owned)
                except Exception as error:
                    print('Export snapshot cleanup failed: ' + str(error), file=sys.stderr)
            raise
        finally:
            if journal_fd is not None:
                os.close(journal_fd)
            if snapshot_fd is not None:
                os.close(snapshot_fd)
            if snapshot_parent_fd is not None:
                os.close(snapshot_parent_fd)
        """)
    )


def selected_files_cleanup_script(root):
    return (
        f'root = {root!r}\n'
        + _SNAPSHOT_HELPERS
        + textwrap.dedent("""\
        parent, name = snapshot_parent(root)
        directory = None
        try:
            try:
                directory = os.open(name, flags, dir_fd=parent)
            except FileNotFoundError:
                raise SystemExit(0)
            try:
                file_fd = os.open('.manifest.jsonl', os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory)
            except FileNotFoundError:
                if os.listdir(directory):
                    raise ValueError('Export snapshot has no recovery journal; retained')
                cleanup_snapshot(parent, name, directory, {})
                raise SystemExit(0)
            with os.fdopen(file_fd, 'rb') as manifest_file:
                info = os.fstat(manifest_file.fileno())
                if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size > 65536:
                    raise ValueError('Unsafe export snapshot journal')
                encoded = manifest_file.read(65537)
                if len(encoded) > 65536:
                    raise ValueError('Export snapshot journal is too large')
            lines = encoded.splitlines(keepends=True)
            if not lines or not lines[0].endswith(b'\\n'):
                raise ValueError('Incomplete export snapshot header')
            header = json.loads(lines[0])
            names = header.get('files') if isinstance(header, dict) else None
            root_identity = header.get('root') if isinstance(header, dict) else None
            if not isinstance(names, list) or len(names) > 1000 or len(names) != len(set(names)) or not isinstance(root_identity, list) or len(root_identity) != 2:
                raise ValueError('Invalid export snapshot header')
            for filename in names:
                if not isinstance(filename, str) or not re.fullmatch(r'(?:[0-9a-f]{32}[.]bin|[.]tmp-[0-9a-f]{32})', filename):
                    raise ValueError('Invalid export snapshot entry')
            manifest = dict.fromkeys(names)
            for line in lines[1:]:
                if not line.endswith(b'\\n'):
                    break
                entry = json.loads(line)
                temporary, final, identity = entry.get('temporary'), entry.get('final'), entry.get('identity')
                if temporary not in manifest or final not in manifest or not isinstance(identity, list) or len(identity) != 2:
                    raise ValueError('Invalid export snapshot identity')
                manifest[temporary] = manifest[final] = identity
            manifest['.manifest.jsonl'] = [info.st_dev, info.st_ino]
            cleanup_snapshot(parent, name, directory, manifest, root_identity)

        finally:
            if directory is not None:
                os.close(directory)
            os.close(parent)
        """)
    )
