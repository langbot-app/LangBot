"""Bounded, link-free outbox operations executed inside the bound sandbox."""

import os
import textwrap


def outbox_script(
    outbox_root: str,
    query_key: str,
    *,
    operation: str,
    max_file_bytes: int,
    max_files: int,
    max_total_bytes: int,
) -> str:
    settings = {
        'workspace': os.path.dirname(outbox_root),
        'outbox': os.path.basename(outbox_root),
        'query': query_key,
        'operation': operation,
        'max_file_bytes': max_file_bytes,
        'max_files': max_files,
        'max_total_bytes': max_total_bytes,
    }
    return f'settings = {settings!r}\n' + textwrap.dedent("""\
        import base64, errno, json, os, stat
        directory_flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
        file_flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK
        out = []
        budget = {'entries': 512, 'directories': 64, 'bytes': 0}

        def component(value):
            if (not value or value in {'.', '..'} or len(os.fsencode(value)) > 240
                    or any(c in value for c in ('/', '\\\\', '\\x00'))):
                raise RuntimeError('Unsafe sandbox outbox path component')
            return value

        def read_directory(fd, prefix='', depth=0):
            if depth > 8:
                raise RuntimeError('Sandbox outbox exceeds the depth limit')
            with os.scandir(fd) as entries:
                for entry in entries:
                    if budget['entries'] <= 0:
                        raise RuntimeError('Sandbox outbox exceeds the directory-entry limit')
                    budget['entries'] -= 1
                    name = component(entry.name)
                    relative = prefix + '/' + name if prefix else name
                    if entry.is_symlink():
                        continue
                    if entry.is_dir(follow_symlinks=False):
                        if budget['directories'] <= 0:
                            raise RuntimeError('Sandbox outbox exceeds the directory limit')
                        budget['directories'] -= 1
                        flags = directory_flags
                    elif entry.is_file(follow_symlinks=False):
                        flags = file_flags
                    else:
                        continue
                    try:
                        child_fd = os.open(name, flags, dir_fd=fd)
                    except OSError as exc:
                        if exc.errno in {errno.ENOENT, errno.ELOOP, errno.ENOTDIR}:
                            continue
                        raise
                    try:
                        metadata = os.fstat(child_fd)
                        if flags == directory_flags and stat.S_ISDIR(metadata.st_mode):
                            read_directory(child_fd, relative, depth + 1)
                            continue
                        if not stat.S_ISREG(metadata.st_mode):
                            continue
                        if len(out) >= settings['max_files']:
                            raise RuntimeError('Sandbox outbox exceeds the file-count limit')
                        remaining = settings['max_total_bytes'] - budget['bytes']
                        if metadata.st_size > settings['max_file_bytes'] or metadata.st_size > remaining:
                            raise RuntimeError('Sandbox output attachment exceeds the export size limit')
                        with os.fdopen(child_fd, 'rb', closefd=False) as source:
                            data = source.read(settings['max_file_bytes'] + 1)
                        if len(data) > settings['max_file_bytes'] or len(data) > remaining:
                            raise RuntimeError('Sandbox output attachment exceeds the export size limit')
                        out.append({'name': relative, 'b64': base64.b64encode(data).decode('ascii')})
                        budget['bytes'] += len(data)
                    finally:
                        os.close(child_fd)

        def clear_directory(fd, depth=0):
            if depth > 16:
                raise RuntimeError('Sandbox cleanup exceeded its depth limit')
            with os.scandir(fd) as entries:
                for entry in entries:
                    if budget['entries'] <= 0:
                        raise RuntimeError('Sandbox cleanup exceeded its inode limit')
                    budget['entries'] -= 1
                    name = component(entry.name)
                    try:
                        child_fd = os.open(name, directory_flags, dir_fd=fd)
                    except FileNotFoundError:
                        continue
                    except OSError as exc:
                        if exc.errno not in {errno.ELOOP, errno.ENOTDIR}:
                            raise
                        try:
                            os.unlink(name, dir_fd=fd)
                        except FileNotFoundError:
                            pass
                    else:
                        try:
                            clear_directory(child_fd, depth + 1)
                        finally:
                            os.close(child_fd)
                        try:
                            os.rmdir(name, dir_fd=fd)
                        except FileNotFoundError:
                            pass

        try:
            workspace_fd = os.open(settings['workspace'], directory_flags)
            try:
                outbox_fd = os.open(component(settings['outbox']), directory_flags, dir_fd=workspace_fd)
                try:
                    query_fd = os.open(component(settings['query']), directory_flags, dir_fd=outbox_fd)
                    try:
                        if settings['operation'] == 'read':
                            read_directory(query_fd)
                        elif settings['operation'] == 'clear':
                            budget['entries'] = 4096
                            clear_directory(query_fd)
                        else:
                            raise RuntimeError('Unknown sandbox outbox operation')
                    finally:
                        os.close(query_fd)
                finally:
                    os.close(outbox_fd)
            finally:
                os.close(workspace_fd)
        except FileNotFoundError:
            pass
        print(json.dumps(out))
        """)
