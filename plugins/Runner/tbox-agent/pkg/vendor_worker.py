"""Private Tbox JSON-lines worker, scoped to one request and temp directory."""

import base64
import contextlib
import json
import resource
import sys
import tempfile


def cap(kind, value):
    soft, hard = resource.getrlimit(kind)
    # Never raise a tighter nsjail/inherited limit.
    limits = [value] + [v for v in (soft, hard) if v != resource.RLIM_INFINITY]
    limit = min(limits)
    resource.setrlimit(kind, (limit, limit))


cap(resource.RLIMIT_AS, 512 * 1024 * 1024)
cap(resource.RLIMIT_FSIZE, 16 * 1024 * 1024)
cap(resource.RLIMIT_CORE, 0)
output = sys.stdout
payload = json.loads(sys.stdin.readline(16 * 1024 * 1024 + 1))
sys.path[:] = payload.pop("import_paths")


def emit(item):
    line = json.dumps({"item": item}, ensure_ascii=False)
    if len(line.encode()) > 1024 * 1024 - 1:
        raise ValueError("Response too large")
    output.write(line + "\n")
    output.flush()


try:
    with contextlib.redirect_stdout(sys.stderr):
        from tboxsdk.tbox import TboxClient

        client = TboxClient(authorization=payload["api_key"])
        if payload["operation"] == "upload":
            data = base64.b64decode(payload["data"], validate=True)
            if len(data) > 10 * 1024 * 1024:
                raise ValueError("Upload too large")
            # Parent removes the whole private directory even after SIGKILL.
            with tempfile.NamedTemporaryFile(suffix=payload["suffix"]) as tmp:
                tmp.write(data)
                tmp.flush()
                emit(client.upload_file(tmp.name))
        else:
            from tboxsdk.model.file import File, FileType

            kwargs = payload["kwargs"]
            if kwargs.get("files"):
                kwargs["files"] = [File(file_id=f["file_id"], type=FileType.IMAGE) for f in kwargs["files"]]
            response = client.chat(**kwargs)
            if kwargs["stream"]:
                for chunk in response:
                    emit(chunk)
            else:
                emit(response)
except BaseException as exc:
    output.write(json.dumps({"error": "timeout" if "timeout" in type(exc).__name__.lower() else "vendor"}) + "\n")
    output.flush()
    sys.exit(1)
