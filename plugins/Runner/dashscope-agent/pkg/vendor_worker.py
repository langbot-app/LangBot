"""Private JSON-lines worker; never import this module into the shared loop."""

import contextlib
import json
import resource
import sys


# SDK response parsing is synchronous; bound that process even before framing.
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
        import requests
        from dashscope import Application

        class NoRedirectSession(requests.Session):
            def request(self, method, url, **kwargs):
                kwargs["allow_redirects"] = False
                return super().request(method, url, **kwargs)

        # A private session: never forward prompts/credentials across redirects.
        # Call arguments are invocation-owned; no module-global api_key mutation.
        with NoRedirectSession() as session:
            session.trust_env = False
            response = Application.call(**payload["kwargs"], session=session)
            for chunk in response:
                emit(dict(chunk))
except BaseException as exc:
    output.write(json.dumps({"error": "timeout" if "timeout" in type(exc).__name__.lower() else "vendor"}) + "\n")
    output.flush()
    sys.exit(1)
