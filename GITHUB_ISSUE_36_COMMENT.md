# GitHub Issue Comment for oceanbase/seekdb#36

**Please manually post this comment to: https://github.com/oceanbase/seekdb/issues/36**

---

## Same Issue on macOS (Intel x86_64)

I'm encountering the exact same problem while integrating SeekDB into [LangBot](https://github.com/langbot-app/LangBot), an open-source LLM chatbot platform.

### Environment
- **Platform**: macOS (Darwin 24.6.0)
- **Architecture**: x86_64
- **Docker**: Docker Desktop on macOS
- **SeekDB Image**: `oceanbase/seekdb:latest`

### What I Tried

#### 1. Embedded Mode (Expected to Fail)
```python
import pyseekdb
client = pyseekdb.Client(path='./data/seekdb', database='langbot')
```

**Result**: ❌ Expected failure
```
RuntimeError: Embedded Client is not available because pylibseekdb is not available.
Please install pylibseekdb (Linux only) or use RemoteServerClient (host/port) instead.
```

This is expected since `pylibseekdb` is Linux-only.

#### 2. Server Mode via Docker (Unexpected Failure)
```bash
docker run -d --name seekdb -p 2881:2881 oceanbase/seekdb:latest
```

**Result**: ❌ Container exits with code 30

**Logs**:
```
Starting seekdb with command: /usr/bin/observer --base-dir=/var/lib/oceanbase --port=2881 ...
Configuration loaded from: /etc/oceanbase/seekdb.cnf
SeekDB started successfully, starting obshell agent...
[ERROR] Code: Agent.SeekDB.Not.Exists, Message: initialize failed: init agent failed: SeekDB not exists in current directory. Please initialize seekdb first.
[ERROR] Code: Agent.Daemon.StartFailed, Message: Daemon start failed: obshell server exited with code 20, please check obshell.log for more details
```

**Container Status**: Exited (30)

### Observations

1. The `observer` process starts successfully ("SeekDB started successfully")
2. The `obshell agent` initialization fails with "SeekDB not exists"
3. The container exits after ~10 seconds of retry loops
4. This matches exactly what @SamYuan1990 reported

### Impact

This blocks testing SeekDB integration on macOS. While I've validated my integration code architecture using ChromaDB as a fallback, I cannot test the actual SeekDB functionality.

### Integration Code Status

✅ **Integration Complete**: I've implemented a complete SeekDB adapter for LangBot
✅ **Architecture Validated**: Tested end-to-end with ChromaDB to verify the integration pattern
✅ **Documentation Complete**: Full docs and examples ready
❌ **Actual Testing Blocked**: Cannot test with real SeekDB due to this Docker issue

### Request

Could the OceanBase team provide:
1. A workaround for macOS users to run SeekDB in server mode?
2. Expected timeline for fixing this Docker initialization issue?
3. Alternative ways to test SeekDB on macOS (e.g., connecting to a remote instance)?

### Related

- Integration PR: https://github.com/langbot-app/LangBot (SeekDB support added)
- SeekDB Adapter: Implements full `VectorDatabase` interface for knowledge base RAG functionality

Thank you for working on this issue! Looking forward to testing SeekDB properly once this is resolved. 🙏
