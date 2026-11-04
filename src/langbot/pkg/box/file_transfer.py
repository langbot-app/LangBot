"""Explicit bounded file transfers over the existing bound Box exec channel."""

import textwrap

CHUNK_BYTES = 48 * 1024

_PREAMBLE = textwrap.dedent("""\
    import base64, hashlib, json, os, stat
    directory_flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    file_flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK
    def open_directory(path, create=False):
        if not path.startswith('/'):
            raise ValueError('Expected an absolute sandbox path')
        parts = path.split('/')[1:]
        if any(p in ('', '.', '..') or '\\\\' in p or '\\x00' in p for p in parts):
            raise ValueError('Expected a normalized sandbox path')
        fd = os.open('/', directory_flags)
        try:
            for part in parts:
                if create:
                    try:
                        os.mkdir(part, 0o700, dir_fd=fd)
                    except FileExistsError:
                        pass
                child = os.open(part, directory_flags, dir_fd=fd)
                os.close(fd)
                fd = child
            return fd
        except BaseException:
            os.close(fd)
            raise
""")


def import_chunk_script(directory, staging, name, chunk, offset, size, digest):
    settings = dict(
        directory=directory, staging=staging, name=name, chunk=chunk, offset=offset, size=size, digest=digest
    )
    return (
        _PREAMBLE
        + f'settings = {settings!r}\n'
        + textwrap.dedent("""\
        parent = open_directory(settings['directory'], create=True)
        try:
            flags = os.O_RDWR | os.O_NOFOLLOW | os.O_NONBLOCK
            if settings['offset'] == 0:
                flags |= os.O_CREAT | os.O_EXCL
            fd = os.open(settings['staging'], flags, 0o600, dir_fd=parent)
            with os.fdopen(fd, 'r+b') as target:
                info = os.fstat(target.fileno())
                if not stat.S_ISREG(info.st_mode) or info.st_size != settings['offset']:
                    raise ValueError('Import staging file changed')
                data = base64.b64decode(settings['chunk'], validate=True)
                target.seek(settings['offset'])
                target.write(data)
                target.flush()
                complete = target.tell() == settings['size']
                if complete:
                    target.seek(0)
                    if hashlib.sha256(target.read()).hexdigest() != settings['digest']:
                        raise ValueError('Import content checksum mismatch')
                    try:
                        os.link(settings['staging'], settings['name'], src_dir_fd=parent,
                                dst_dir_fd=parent, follow_symlinks=False)
                    except FileExistsError:
                        existing = os.open(settings['name'], file_flags, dir_fd=parent)
                        with os.fdopen(existing, 'rb') as source:
                            if (not stat.S_ISREG(os.fstat(source.fileno()).st_mode)
                                    or hashlib.sha256(source.read(settings['size'] + 1)).hexdigest() != settings['digest']):
                                raise ValueError('Import destination already contains different content')
                    os.unlink(settings['staging'], dir_fd=parent)
            print(json.dumps({'size': settings['offset'] + len(data), 'complete': complete}))
        finally:
            os.close(parent)
    """)
    )


def directory_snapshot_script(path, *, max_files=2048, max_bytes=256 * 1024 * 1024):
    settings = dict(path=path, max_files=max_files, max_bytes=max_bytes)
    return (
        _PREAMBLE
        + f'settings = {settings!r}\n'
        + textwrap.dedent("""\
        budget = {'files': 0, 'bytes': 0, 'entries': 8192}
        first = True
        def walk(fd, prefix='', depth=0):
            global first
            if depth > 16:
                raise ValueError('Skill draft directory is too deep')
            with os.scandir(fd) as entries:
                for entry in entries:
                    budget['entries'] -= 1
                    if budget['entries'] < 0:
                        raise ValueError('Skill draft has too many entries')
                    if entry.name in {'.git', '__pycache__', '.venv', 'node_modules'}:
                        continue
                    if entry.is_symlink():
                        raise ValueError('Skill draft contains a symbolic link')
                    relative = prefix + entry.name
                    if entry.is_dir(follow_symlinks=False):
                        child = os.open(entry.name, directory_flags, dir_fd=fd)
                        try:
                            walk(child, relative + '/', depth + 1)
                        finally:
                            os.close(child)
                    else:
                        child = os.open(entry.name, file_flags, dir_fd=fd)
                        with os.fdopen(child, 'rb') as source:
                            before = os.fstat(source.fileno())
                            if not stat.S_ISREG(before.st_mode):
                                raise ValueError('Skill draft contains a non-regular file')
                            remaining = settings['max_bytes'] - budget['bytes']
                            data = source.read(min(10 * 1024 * 1024, remaining) + 1)
                            after = os.fstat(source.fileno())
                            if (len(data) > min(10 * 1024 * 1024, remaining)
                                    or budget['files'] >= settings['max_files']):
                                raise ValueError('Skill draft exceeds transfer limits')
                            if (before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (after.st_size, after.st_mtime_ns, after.st_ctime_ns):
                                raise ValueError('Skill draft changed while being read')
                        if not first:
                            print(',', end='')
                        print(json.dumps({'name': relative, 'b64': base64.b64encode(data).decode('ascii')}), end='')
                        first = False
                        budget['files'] += 1
                        budget['bytes'] += len(data)
        root = open_directory(settings['path'])
        try:
            print('[', end='')
            walk(root)
            print(']')
        finally:
            os.close(root)
    """)
    )


def capture_script(script, path, max_bytes):
    # Keep large snapshots out of stdout; fetch the completed payload in chunks.
    return (
        'import contextlib, hashlib, json, os\n'
        + f'path = {path!r}\n'
        + textwrap.dedent(f"""\
        with open(path, 'x', encoding='utf-8') as output:
            with contextlib.redirect_stdout(output):
                exec(compile({script!r}, '<box-transfer>', 'exec'), {{}})
        size = os.path.getsize(path)
        if size > {max_bytes!r}:
            raise ValueError('Sandbox transfer exceeds the response limit')
        digest = hashlib.sha256()
        with open(path, 'rb') as source:
            for chunk in iter(lambda: source.read(65536), b''):
                digest.update(chunk)
        print(json.dumps({{'size': size, 'sha256': digest.hexdigest()}}))
    """)
    )


def read_chunk_script(path, offset):
    return _PREAMBLE + textwrap.dedent(f"""\
        fd = os.open({path!r}, file_flags)
        with os.fdopen(fd, 'rb') as source:
            if not stat.S_ISREG(os.fstat(source.fileno()).st_mode):
                raise ValueError('Unsafe sandbox transfer file')
            source.seek({offset!r})
            print(base64.b64encode(source.read({CHUNK_BYTES})).decode('ascii'))
    """)


def remove_import_script(directory, staging):
    return _PREAMBLE + textwrap.dedent(f"""\
        parent = open_directory({directory!r})
        try:
            try:
                os.unlink({staging!r}, dir_fd=parent)
            except FileNotFoundError:
                pass
        finally:
            os.close(parent)
    """)
