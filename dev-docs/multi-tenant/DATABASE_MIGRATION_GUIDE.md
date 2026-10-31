# LangBot 多租户数据库迁移指南

## 概述

LangBot 从单租户 OSS 架构迁移到多租户 SaaS 架构，需要执行 7 个数据库迁移（0009-0015）。

## 迁移序列

```
0009_workspace_tenancy_kernel → 创建 Workspace、成员、邀请表
0010_scope_tenant_resources → 所有业务表添加 workspace_uuid
0011_postgres_tenant_rls → PostgreSQL 行级安全策略
0012_plugin_installation_identity → 插件实例租户绑定
0013_tenant_pgvector → RAG 向量存储隔离
0014_cloud_directory_projection → Cloud 控制平面同步
0015_cloud_core_collaboration → 协作和权限功能
```

## 执行步骤

### 1. 备份（必须）

```bash
# SQLite
cp ~/.langbot/data/langbot.db ~/.langbot/data/langbot.db.backup-$(date +%Y%m%d)

# PostgreSQL  
pg_dump -U langbot_user -d langbot_db -F c -f langbot_backup_$(date +%Y%m%d).dump
```

### 2. 执行迁移

```bash
# 停止服务
sudo -S -p '' systemctl stop langbot

# 执行迁移
python -m langbot.pkg.persistence.migration upgrade head

# 验证
python -m langbot.pkg.persistence.migration current
# 预期: 0015_cloud_core_collaboration

# 启动服务
sudo -S -p '' systemctl start langbot
```

### 3. OSS 单租户自动迁移

迁移会自动：
- 创建默认 Workspace（名称："Default Workspace"）
- 第一个用户成为 Owner
- 所有现有资源绑定到该 Workspace

### 4. 验证检查

```bash
# 检查 Workspace
python << EOF
from langbot.pkg.persistence import manager
import sqlalchemy as sa

with manager.engine.connect() as conn:
    ws = conn.execute(sa.text("SELECT uuid, name FROM workspaces LIMIT 1")).first()
    print(f"Workspace: {ws[1]} ({ws[0]})")
    
    # 检查资源绑定
    bot_count = conn.execute(sa.text(
        f"SELECT COUNT(*) FROM bots WHERE workspace_uuid='{ws[0]}'"
    )).scalar()
    print(f"Bots: {bot_count}")
EOF
```

## 回滚方案

### 完全回滚（丢失多租户数据）

```bash
# 1. 停止服务
sudo -S -p '' systemctl stop langbot

# 2. 恢复备份
cp ~/.langbot/data/langbot.db.backup-YYYYMMDD ~/.langbot/data/langbot.db

# 3. 回退代码
git checkout v4.10.x
pip install -e .

# 4. 启动
sudo -S -p '' systemctl start langbot
```

### 降级迁移（保留数据但移除多租户）

```bash
# 警告：会移除 Workspace 表但保留资源
python -m langbot.pkg.persistence.migration downgrade 0008_mcp_resource_prefs
```

## 常见问题

### Q: 迁移后无法登录

```bash
# 检查用户 UUID
python << EOF
from langbot.pkg.persistence import manager
import sqlalchemy as sa

with manager.engine.connect() as conn:
    users = conn.execute(sa.text("SELECT id, user, uuid, status FROM users")).all()
    for u in users:
        print(f"{u[1]}: UUID={u[2]}, Status={u[3]}")
EOF
```

### Q: 资源看不见了

检查 Workspace 上下文：
```bash
# 前端请求需要带 X-Workspace-ID header
curl -H "Authorization: Bearer $TOKEN" \
     -H "X-Workspace-ID: $WORKSPACE_UUID" \
     http://localhost:5200/api/v1/platform/bots
```

### Q: 迁移速度慢

```bash
# SQLite 优化
sqlite3 ~/.langbot/data/langbot.db << EOF
PRAGMA journal_mode=WAL;
PRAGMA synchronous=NORMAL;
VACUUM;
EOF
```

## 性能调优

### PostgreSQL 索引

```sql
-- 迁移后创建
CREATE INDEX CONCURRENTLY idx_model_providers_workspace 
    ON model_providers(workspace_uuid);

CREATE INDEX CONCURRENTLY idx_bots_workspace 
    ON bots(workspace_uuid);

CREATE INDEX CONCURRENTLY idx_pipelines_workspace 
    ON pipelines(workspace_uuid);
```

## 预估时间

- SQLite < 100MB: 2-5 分钟
- SQLite 100MB-1GB: 5-15 分钟  
- PostgreSQL: < 5 分钟（取决于数据量）

## 支持

问题反馈：https://github.com/langbot-app/LangBot/issues

**版本**: 1.0  
**最后更新**: 2026-07-30
