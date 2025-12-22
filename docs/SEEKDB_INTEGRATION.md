# SeekDB Vector Database Integration

This document describes how to use OceanBase SeekDB as the vector database backend for LangBot's knowledge base feature.

## What is SeekDB?

**OceanBase SeekDB** is an AI-native search database that unifies relational, vector, text, JSON and GIS in a single engine, enabling hybrid search and in-database AI workflows. It's developed by OceanBase and released under Apache 2.0 license.

### Key Features

- **Hybrid Search**: Combine vector search, full-text search and relational query in a single statement
- **Multi-Model Support**: Support relational, vector, text, JSON and GIS in a single engine
- **Lightweight**: Requires as little as 1 CPU core and 2 GB of memory
- **Multiple Deployment Modes**: Supports both embedded mode and client/server mode
- **MySQL Compatible**: Powered by OceanBase engine with full ACID compliance and MySQL compatibility

## Installation

SeekDB support is automatically included when you install LangBot. The required dependency `pyseekdb` is listed in `pyproject.toml`.

If you need to install it manually:

```bash
pip install pyseekdb
```

## ⚠️ Platform Compatibility

### Embedded Mode

| Platform | Status | Notes |
|----------|--------|-------|
| Linux | ✅ Supported | Full embedded mode support via `pylibseekdb` |
| macOS | ❌ Not Supported | `pylibseekdb` is Linux-only; use server mode instead |
| Windows | ❌ Not Supported | `pylibseekdb` is Linux-only; use server mode instead |

**Important**: Embedded mode requires the `pylibseekdb` library, which is only available on Linux. If you're on macOS or Windows, you must use server mode.

### Server Mode (Docker)

| Platform | Status | Notes |
|----------|--------|-------|
| Linux | ✅ Supported | Full Docker support |
| macOS | ⚠️ Known Issue | Docker container initialization failure - [See Issue #36](https://github.com/oceanbase/seekdb/issues/36) |
| Windows | ⚠️ Untested | Should work but not yet tested |

**macOS Users**: Currently, SeekDB Docker containers have an initialization issue on macOS ([oceanbase/seekdb#36](https://github.com/oceanbase/seekdb/issues/36)). Until this is resolved, we recommend:
- Using ChromaDB or Qdrant as alternatives
- Connecting to a remote SeekDB server on Linux if available

### Server Mode (Remote Connection)

| Platform | Status | Notes |
|----------|--------|-------|
| All Platforms | ✅ Supported | Connect to SeekDB running on a remote Linux server |

**Recommendation for macOS/Windows users**: Deploy SeekDB on a Linux server and connect via server mode configuration.

## Configuration

### Embedded Mode (Recommended for Development)

Embedded mode runs SeekDB directly within the LangBot process, storing data locally. This is the simplest setup and requires no external services.

Edit your `config.yaml`:

```yaml
vdb:
  use: seekdb
  seekdb:
    mode: embedded
    path: './data/seekdb'  # Path to store SeekDB data
    database: 'langbot'    # Database name
```

### Server Mode (For Production)

Server mode connects to a remote SeekDB server or OceanBase server. This is recommended for production deployments.

#### SeekDB Server

```yaml
vdb:
  use: seekdb
  seekdb:
    mode: server
    host: 'localhost'
    port: 2881
    database: 'langbot'
    user: 'root'
    password: ''  # Can also use SEEKDB_PASSWORD env var
```

#### OceanBase Server

If you're using OceanBase with seekdb capabilities:

```yaml
vdb:
  use: seekdb
  seekdb:
    mode: server
    host: 'localhost'
    port: 2881
    tenant: 'sys'        # OceanBase tenant name
    database: 'langbot'
    user: 'root'
    password: ''
```

## Configuration Parameters

| Parameter  | Required | Default      | Description |
|-----------|----------|--------------|-------------|
| `mode`    | No       | `embedded`   | Deployment mode: `embedded` or `server` |
| `path`    | No       | `./data/seekdb` | Data directory for embedded mode |
| `database` | No      | `langbot`    | Database name |
| `host`    | No       | `localhost`  | Server host (server mode only) |
| `port`    | No       | `2881`       | Server port (server mode only) |
| `user`    | No       | `root`       | Username (server mode only) |
| `password` | No      | `''`         | Password (server mode only) |
| `tenant`  | No       | None         | OceanBase tenant (optional, server mode only) |

## Usage

Once configured, SeekDB will be used automatically for all knowledge base operations in LangBot:

1. **Creating Knowledge Bases**: Vectors will be stored in SeekDB collections
2. **Adding Documents**: Document embeddings will be indexed in SeekDB
3. **Searching**: Vector similarity search will use SeekDB's efficient indexing
4. **Deleting**: Document removal will delete vectors from SeekDB

No code changes are required - just update your configuration!

## Architecture Details

### Implementation

The SeekDB adapter is implemented in `src/langbot/pkg/vector/vdbs/seekdb.py` and follows the same `VectorDatabase` interface as Chroma and Qdrant adapters.

Key methods:
- `add_embeddings()`: Add vectors with metadata to a collection
- `search()`: Perform vector similarity search
- `delete_by_file_id()`: Delete vectors by file ID metadata
- `get_or_create_collection()`: Manage collections
- `delete_collection()`: Remove entire collections

### Vector Storage

- Collections are created with HNSW (Hierarchical Navigable Small World) index
- Default distance metric: Cosine similarity
- Default vector dimension: 384 (adjusts automatically based on embeddings)
- Metadata is stored alongside vectors for filtering

## Advantages Over Other Vector Databases

### vs. ChromaDB
- ✅ Better MySQL compatibility
- ✅ Hybrid search capabilities (vector + full-text + SQL)
- ✅ Production-grade distributed mode support
- ✅ Lightweight embedded mode

### vs. Qdrant
- ✅ SQL query support
- ✅ MySQL ecosystem integration
- ✅ Simpler deployment (no Docker required for embedded mode)
- ✅ Multi-model data support (not just vectors)

## Troubleshooting

### Import Error

If you see: `ImportError: pyseekdb is not installed`

Solution:
```bash
pip install pyseekdb
```

### Embedded Mode Error on macOS/Windows

**Error**:
```
RuntimeError: Embedded Client is not available because pylibseekdb is not available.
Please install pylibseekdb (Linux only) or use RemoteServerClient (host/port) instead.
```

**Cause**: `pylibseekdb` is only available on Linux platforms.

**Solution**: Use server mode instead:
1. Deploy SeekDB on a Linux server or VM
2. Configure LangBot to use server mode:
```yaml
vdb:
  use: seekdb
  seekdb:
    mode: server
    host: 'your-seekdb-server-ip'
    port: 2881
    database: 'langbot'
    user: 'root'
    password: ''
```

**Alternative**: Use ChromaDB or Qdrant, which work on all platforms:
```yaml
vdb:
  use: chroma  # or qdrant
```

### Docker Container Fails on macOS

**Symptoms**:
```bash
docker run -d -p 2881:2881 oceanbase/seekdb:latest
# Container exits immediately with code 30
```

**Error in logs**:
```
[ERROR] Code: Agent.SeekDB.Not.Exists
Message: initialize failed: init agent failed: SeekDB not exists in current directory.
```

**Cause**: This is a known issue with SeekDB Docker containers on macOS. See [oceanbase/seekdb#36](https://github.com/oceanbase/seekdb/issues/36).

**Status**: Under investigation by OceanBase team.

**Workaround Options**:
1. **Use alternatives**: ChromaDB or Qdrant work perfectly on macOS
2. **Remote server**: Deploy SeekDB on a Linux server and connect remotely
3. **Wait for fix**: Monitor the GitHub issue for updates

### Connection Error (Server Mode)

If SeekDB server is not reachable, check:
1. Server is running: `ps aux | grep observer`
2. Port is accessible: `nc -zv localhost 2881`
3. Credentials are correct in config
4. Firewall allows connections on port 2881

### Performance Issues

For large datasets:
- Use server mode instead of embedded mode
- Ensure adequate memory allocation
- Consider using OceanBase distributed mode for very large scale
- Adjust HNSW index parameters if needed

## Resources

- SeekDB GitHub: https://github.com/oceanbase/seekdb
- pyseekdb SDK: https://github.com/oceanbase/pyseekdb
- OceanBase Documentation: https://oceanbase.ai
- LangBot Documentation: https://docs.langbot.app

## License

SeekDB is licensed under Apache License 2.0.
