from __future__ import annotations

import json
import sys


def main() -> None:
    session_id = "fake-session"
    if "--session-id" in sys.argv:
        session_index = sys.argv.index("--session-id")
        if session_index + 1 < len(sys.argv):
            session_id = sys.argv[session_index + 1]
    prompt = sys.argv[-1] if len(sys.argv) > 1 else ""
    print(json.dumps({"type": "session.started", "session_id": session_id}))
    print(json.dumps({"type": "message.completed", "text": f"FAKE_NATIVE_CLI_OK:{prompt}"}))


if __name__ == "__main__":
    main()
