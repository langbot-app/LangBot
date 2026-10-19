"""Explicit file selection inside a sandbox, with no symlink traversal."""

import textwrap


def selected_files_script(paths, *, max_file_bytes, max_total_bytes, cleanup=None):
    settings = dict(paths=paths, max_file_bytes=max_file_bytes, max_total_bytes=max_total_bytes, cleanup=cleanup)
    return f'settings = {settings!r}\n' + textwrap.dedent("""\
        import os, stat, json, base64, hashlib, sys
        flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
        def reject(kind, limit, actual, path):
            print('LANGBOT_OUTBOX_LIMIT:' + json.dumps(dict(kind=kind, limit=limit, actual=actual, path=path)), file=sys.stderr)
            raise SystemExit(73)

        result = []
        total = 0
        for path in settings['paths']:
            parts = path.split('/')
            if not path.startswith('/') or any(p in ('', '.', '..') for p in parts[1:]):
                raise ValueError('Expected a normalized absolute sandbox file path: ' + path)
            fd = os.open('/', flags)
            try:
                for part in parts[1:-1]:
                    child = os.open(part, flags, dir_fd=fd)
                    os.close(fd)
                    fd = child
                file_fd = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
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
                        current = os.stat(parts[-1], dir_fd=fd, follow_symlinks=False)
                        if (current.st_dev, current.st_ino) == (metadata.st_dev, metadata.st_ino) and digest == settings['cleanup'].get(path):
                            os.unlink(parts[-1], dir_fd=fd)
                        else:
                            raise ValueError('File changed after acceptance; retained: ' + path)
                    else:
                        result.append({'name': path, 'b64': base64.b64encode(data).decode('ascii')})
            finally:
                os.close(fd)
        print(json.dumps(result))
        """)
