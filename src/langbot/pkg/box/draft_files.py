"""Create a bounded Skill draft snapshot inside the sandbox."""

import textwrap

from .selected_files import _SNAPSHOT_HELPERS


MAX_DRAFT_ARCHIVE_BYTES = 20 * 1024 * 1024


def skill_draft_script(path: str, snapshot_root: str) -> str:
    return (
        f'source_path = {path!r}\nsnapshot_root = {snapshot_root!r}\n'
        + _SNAPSHOT_HELPERS
        + textwrap.dedent("""\
        import hashlib, sys, uuid, zipfile
        max_archive = 20 * 1024 * 1024
        source_fd = parent_fd = directory = journal = None
        owned = {}
        def identity(info):
            return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)

        def source_entry(relative):
            fd = os.dup(source_fd)
            try:
                parts = relative.split('/')
                for part in parts[:-1]:
                    child = os.open(part, flags, dir_fd=fd)
                    os.close(fd)
                    fd = child
                result = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
                return result
            finally:
                os.close(fd)

        try:
            parent, name = open_parent(source_path)
            try:
                source_fd = os.open(name, flags, dir_fd=parent)
            finally:
                os.close(parent)
            entries = []
            directories = []
            total = 0
            def scan(fd, prefix='', depth=0):
                global total
                if depth > 16:
                    raise ValueError('Skill draft exceeds the directory depth limit (16)')
                directories.append((prefix, identity(os.fstat(fd))))
                with os.scandir(fd) as children:
                    for child in children:
                        relative = prefix + child.name
                        if '\\\\' in child.name or '\\x00' in child.name or (not prefix and len(child.name) >= 2 and child.name[1] == ':'):
                            raise ValueError('Unsafe Skill draft path: ' + relative)
                        if len(entries) >= 512:
                            raise ValueError('Skill draft exceeds the entry limit (512)')
                        info = child.stat(follow_symlinks=False)
                        is_directory = stat.S_ISDIR(info.st_mode)
                        if not is_directory and (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1):
                            raise ValueError('Skill draft contains a link or special file: ' + relative)
                        if not is_directory:
                            if info.st_size > 16 * 1024 * 1024:
                                raise ValueError('Skill draft file exceeds the size limit: ' + relative)
                            total += info.st_size
                            if total > 64 * 1024 * 1024:
                                raise ValueError('Skill draft exceeds the expanded size limit')
                        entries.append((relative, info, is_directory))
                        if is_directory:
                            child_fd = os.open(child.name, flags, dir_fd=fd)
                            try:
                                if identity(os.fstat(child_fd)) != identity(info):
                                    raise ValueError('Skill draft changed: ' + relative)
                                scan(child_fd, relative + '/', depth + 1)
                            finally:
                                os.close(child_fd)
            scan(source_fd)

            # Collect the bounded source list before creating a snapshot under /workspace.
            parent_fd, snapshot_name = snapshot_parent(snapshot_root, create=True)
            os.mkdir(snapshot_name, mode=0o700, dir_fd=parent_fd)
            directory = os.open(snapshot_name, flags, dir_fd=parent_fd)
            temporary, final = '.tmp-' + uuid.uuid4().hex, uuid.uuid4().hex + '.bin'
            owned = {temporary: None, final: None}
            journal = os.open('.manifest.jsonl', os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=directory)
            owned['.manifest.jsonl'] = regular_identity(directory, '.manifest.jsonl')
            def record(entry):
                body = (json.dumps(entry) + '\\n').encode()
                while body:
                    written = os.write(journal, body)
                    if written <= 0:
                        raise OSError('Snapshot journal write made no progress')
                    body = body[written:]
                os.fsync(journal)
            info = os.fstat(directory)
            record(dict(root=[info.st_dev, info.st_ino], files=[temporary, final]))
            output_fd = os.open(temporary, os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=directory)
            owned[temporary] = owned[final] = regular_identity(directory, temporary)
            with os.fdopen(output_fd, 'w+b') as output:
                record(dict(temporary=temporary, final=final, identity=owned[temporary]))
                with zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_STORED, allowZip64=False) as archive:
                    for relative, expected, is_directory in entries:
                        member = zipfile.ZipInfo(relative + '/' if is_directory else relative)
                        member.create_system = 3
                        member.external_attr = ((stat.S_IFDIR | 0o755) if is_directory else (stat.S_IFREG | (0o755 if expected.st_mode & 0o111 else 0o644))) << 16
                        if is_directory:
                            archive.writestr(member, b'')
                        else:
                            with os.fdopen(source_entry(relative), 'rb') as source:
                                before = os.fstat(source.fileno())
                                if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or identity(before) != identity(expected):
                                    raise ValueError('Skill draft changed: ' + relative)
                                copied = 0
                                with archive.open(member, 'w') as target:
                                    while True:
                                        chunk = source.read(65536)
                                        if not chunk:
                                            break
                                        copied += len(chunk)
                                        if copied > expected.st_size:
                                            raise ValueError('Skill draft changed: ' + relative)
                                        target.write(chunk)
                                        if output.tell() > max_archive:
                                            raise ValueError('Skill draft archive exceeds the size limit (20 MiB)')
                                if copied != expected.st_size or identity(os.fstat(source.fileno())) != identity(expected):
                                    raise ValueError('Skill draft changed: ' + relative)
                        if output.tell() > max_archive:
                            raise ValueError('Skill draft archive exceeds the size limit (20 MiB)')
                output.flush()
                os.fsync(output.fileno())
                size = output.tell()
                if size > max_archive:
                    raise ValueError('Skill draft archive exceeds the size limit (20 MiB)')
                output.seek(0)
                hasher = hashlib.sha256()
                while True:
                    chunk = output.read(65536)
                    if not chunk:
                        break
                    hasher.update(chunk)
                digest = hasher.hexdigest()
            for relative, expected in directories:
                check_fd = os.dup(source_fd) if not relative else source_entry(relative.rstrip('/'))
                try:
                    current = os.fstat(check_fd)
                    # Snapshot creation may change /workspace itself, never its selected children.
                    if source_path == '/workspace' and not relative:
                        if (current.st_dev, current.st_ino) != expected[:2]:
                            raise ValueError('Skill draft source changed')
                    elif identity(current) != expected:
                        raise ValueError('Skill draft directory changed: ' + relative)
                finally:
                    os.close(check_fd)
            os.replace(temporary, final, src_dir_fd=directory, dst_dir_fd=directory)
            os.fsync(directory)
            print(json.dumps(dict(snapshot_path=snapshot_root + '/' + final, size=size, sha256=digest)))
        except BaseException:
            if directory is not None:
                try:
                    cleanup_snapshot(parent_fd, snapshot_name, directory, owned)
                except Exception as error:
                    print('Skill draft snapshot cleanup failed: ' + str(error), file=sys.stderr)
            raise
        finally:
            for fd in (journal, directory, parent_fd, source_fd):
                if fd is not None:
                    os.close(fd)
        """)
    )
