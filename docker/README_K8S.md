# LangBot Kubernetes 部署指南 / Kubernetes Deployment Guide

[简体中文](#简体中文) | [English](#english)

---

## 简体中文

### 概述

本指南提供了在 Kubernetes 集群中部署 LangBot 的完整步骤。Kubernetes 部署配置基于 `docker-compose.yaml`，适用于生产环境的容器化部署。

### 前置要求

- Kubernetes 集群（版本 1.19+）
- `kubectl` 命令行工具已配置并可访问集群
- 集群中有可用的存储类（StorageClass）用于持久化存储（可选但推荐）
- 至少 2 vCPU 和 4GB RAM 的可用资源

### 架构说明

Kubernetes 部署包含以下组件：

1. **langbot**: 主应用服务
   - 提供 Web UI（端口 5300）
   - 处理平台 webhook（端口 2280-2290）
   - 数据持久化卷
   
2. **langbot-plugin-runtime**: 插件运行时服务
   - WebSocket 通信（端口 5400）
   - 插件数据持久化卷

3. **持久化存储**:
   - `langbot-data`: LangBot 主数据
   - `langbot-plugins`: 插件文件
   - `langbot-plugin-runtime-data`: 插件运行时数据

### 快速开始

#### 1. 下载部署文件

```bash
# 克隆仓库
git clone https://github.com/langbot-app/LangBot
cd LangBot/docker

# 或直接下载 kubernetes.yaml
wget https://raw.githubusercontent.com/langbot-app/LangBot/main/docker/kubernetes.yaml
```

#### 2. 部署到 Kubernetes

```bash
# 应用所有配置
kubectl apply -f kubernetes.yaml

# 检查部署状态
kubectl get all -n langbot

# 查看 Pod 日志
kubectl logs -n langbot -l app=langbot -f
```

#### 3. 访问 LangBot

默认情况下，LangBot 服务使用 ClusterIP 类型，只能在集群内部访问。您可以选择以下方式之一来访问：

**选项 A: 端口转发（推荐用于测试）**

```bash
kubectl port-forward -n langbot svc/langbot 5300:5300
```

然后访问 http://localhost:5300

**选项 B: NodePort（适用于开发环境）**

编辑 `kubernetes.yaml`，取消注释 NodePort Service 部分，然后：

```bash
kubectl apply -f kubernetes.yaml
# 获取节点 IP
kubectl get nodes -o wide
# 访问 http://<NODE_IP>:30300
```

**选项 C: LoadBalancer（适用于云环境）**

编辑 `kubernetes.yaml`，取消注释 LoadBalancer Service 部分，然后：

```bash
kubectl apply -f kubernetes.yaml
# 获取外部 IP
kubectl get svc -n langbot langbot-loadbalancer
# 访问 http://<EXTERNAL_IP>
```

**选项 D: Ingress（推荐用于生产环境）**

确保集群中已安装 Ingress Controller（如 nginx-ingress），然后：

1. 编辑 `kubernetes.yaml` 中的 Ingress 配置
2. 修改域名为您的实际域名
3. 应用配置：

```bash
kubectl apply -f kubernetes.yaml
# 访问 http://langbot.yourdomain.com
```

### 配置说明

#### 环境变量

在 `ConfigMap` 中配置环境变量：

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: langbot-config
  namespace: langbot
data:
  TZ: "Asia/Shanghai"  # 修改为您的时区
```

#### 存储配置

默认使用动态存储分配。如果您有特定的 StorageClass，请在 PVC 中指定：

```yaml
spec:
  storageClassName: your-storage-class-name
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 10Gi
```

#### 资源限制

根据您的需求调整资源限制：

```yaml
resources:
  requests:
    memory: "1Gi"
    cpu: "500m"
  limits:
    memory: "4Gi"
    cpu: "2000m"
```

### 常用操作

#### 查看日志

```bash
# 查看 LangBot 主服务日志
kubectl logs -n langbot -l app=langbot -f

# 查看插件运行时日志
kubectl logs -n langbot -l app=langbot-plugin-runtime -f
```

#### 重启服务

```bash
# 重启 LangBot
kubectl rollout restart deployment/langbot -n langbot

# 重启插件运行时
kubectl rollout restart deployment/langbot-plugin-runtime -n langbot
```

#### 更新镜像

```bash
# 更新到最新版本
kubectl set image deployment/langbot -n langbot langbot=rockchin/langbot:latest
kubectl set image deployment/langbot-plugin-runtime -n langbot langbot-plugin-runtime=rockchin/langbot:latest

# 检查更新状态
kubectl rollout status deployment/langbot -n langbot
```

#### 扩容（不推荐）

注意：由于 LangBot 使用 ReadWriteOnce 的持久化存储，不支持多副本扩容。如需高可用，请考虑使用 ReadWriteMany 存储或其他架构方案。

#### 备份数据

```bash
# 备份 PVC 数据
kubectl exec -n langbot -it <langbot-pod-name> -- tar czf /tmp/backup.tar.gz /app/data
kubectl cp langbot/<langbot-pod-name>:/tmp/backup.tar.gz ./backup.tar.gz
```

### 卸载

```bash
# 删除所有资源（保留 PVC）
kubectl delete deployment,service,configmap -n langbot --all

# 删除 PVC（会删除数据）
kubectl delete pvc -n langbot --all

# 删除命名空间
kubectl delete namespace langbot
```

### 故障排查

#### Pod 无法启动

```bash
# 查看 Pod 状态
kubectl get pods -n langbot

# 查看详细信息
kubectl describe pod -n langbot <pod-name>

# 查看事件
kubectl get events -n langbot --sort-by='.lastTimestamp'
```

#### 存储问题

```bash
# 检查 PVC 状态
kubectl get pvc -n langbot

# 检查 PV
kubectl get pv
```

#### 网络访问问题

```bash
# 检查 Service
kubectl get svc -n langbot

# 检查端口转发
kubectl port-forward -n langbot svc/langbot 5300:5300
```

### 生产环境建议

1. **使用特定版本标签**：避免使用 `latest` 标签，使用具体版本号如 `rockchin/langbot:v1.0.0`
2. **配置资源限制**：根据实际负载调整 CPU 和内存限制
3. **使用 Ingress + TLS**：配置 HTTPS 访问和证书管理
4. **配置监控和告警**：集成 Prometheus、Grafana 等监控工具
5. **定期备份**：配置自动备份策略保护数据
6. **使用专用 StorageClass**：为生产环境配置高性能存储
7. **配置亲和性规则**：确保 Pod 调度到合适的节点

### 高级配置

#### 使用 Secrets 管理敏感信息

如果需要配置 API 密钥等敏感信息：

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: langbot-secrets
  namespace: langbot
type: Opaque
data:
  api_key: <base64-encoded-value>
```

然后在 Deployment 中引用：

```yaml
env:
- name: API_KEY
  valueFrom:
    secretKeyRef:
      name: langbot-secrets
      key: api_key
```

#### 配置水平自动扩缩容（HPA）

注意：需要确保使用 ReadWriteMany 存储类型

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: langbot-hpa
  namespace: langbot
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: langbot
  minReplicas: 1
  maxReplicas: 3
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
```

### 参考资源

- [LangBot 官方文档](https://docs.langbot.app)
- [Docker 部署文档](https://docs.langbot.app/zh/deploy/langbot/docker.html)
- [Kubernetes 官方文档](https://kubernetes.io/docs/)

---

## English

### Overview

This guide provides complete steps for deploying LangBot in a Kubernetes cluster. The Kubernetes deployment configuration is based on `docker-compose.yaml` and is suitable for production containerized deployments.

### Prerequisites

- Kubernetes cluster (version 1.19+)
- `kubectl` command-line tool configured with cluster access
- Available StorageClass in the cluster for persistent storage (optional but recommended)
- At least 2 vCPU and 4GB RAM of available resources

### Architecture

The Kubernetes deployment includes the following components:

1. **langbot**: Main application service
   - Provides Web UI (port 5300)
   - Handles platform webhooks (ports 2280-2290)
   - Data persistence volume
   
2. **langbot-plugin-runtime**: Plugin runtime service
   - WebSocket communication (port 5400)
   - Plugin data persistence volume

3. **Persistent Storage**:
   - `langbot-data`: LangBot main data
   - `langbot-plugins`: Plugin files
   - `langbot-plugin-runtime-data`: Plugin runtime data

### Quick Start

#### 1. Download Deployment Files

```bash
# Clone repository
git clone https://github.com/langbot-app/LangBot
cd LangBot/docker

# Or download kubernetes.yaml directly
wget https://raw.githubusercontent.com/langbot-app/LangBot/main/docker/kubernetes.yaml
```

#### 2. Deploy to Kubernetes

```bash
# Apply all configurations
kubectl apply -f kubernetes.yaml

# Check deployment status
kubectl get all -n langbot

# View Pod logs
kubectl logs -n langbot -l app=langbot -f
```

#### 3. Access LangBot

By default, LangBot service uses ClusterIP type, accessible only within the cluster. Choose one of the following methods to access:

**Option A: Port Forwarding (Recommended for testing)**

```bash
kubectl port-forward -n langbot svc/langbot 5300:5300
```

Then visit http://localhost:5300

**Option B: NodePort (Suitable for development)**

Edit `kubernetes.yaml`, uncomment the NodePort Service section, then:

```bash
kubectl apply -f kubernetes.yaml
# Get node IP
kubectl get nodes -o wide
# Visit http://<NODE_IP>:30300
```

**Option C: LoadBalancer (Suitable for cloud environments)**

Edit `kubernetes.yaml`, uncomment the LoadBalancer Service section, then:

```bash
kubectl apply -f kubernetes.yaml
# Get external IP
kubectl get svc -n langbot langbot-loadbalancer
# Visit http://<EXTERNAL_IP>
```

**Option D: Ingress (Recommended for production)**

Ensure an Ingress Controller (e.g., nginx-ingress) is installed in the cluster, then:

1. Edit the Ingress configuration in `kubernetes.yaml`
2. Change the domain to your actual domain
3. Apply configuration:

```bash
kubectl apply -f kubernetes.yaml
# Visit http://langbot.yourdomain.com
```

### Configuration

#### Environment Variables

Configure environment variables in ConfigMap:

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: langbot-config
  namespace: langbot
data:
  TZ: "Asia/Shanghai"  # Change to your timezone
```

#### Storage Configuration

Uses dynamic storage provisioning by default. If you have a specific StorageClass, specify it in PVC:

```yaml
spec:
  storageClassName: your-storage-class-name
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 10Gi
```

#### Resource Limits

Adjust resource limits based on your needs:

```yaml
resources:
  requests:
    memory: "1Gi"
    cpu: "500m"
  limits:
    memory: "4Gi"
    cpu: "2000m"
```

### Common Operations

#### View Logs

```bash
# View LangBot main service logs
kubectl logs -n langbot -l app=langbot -f

# View plugin runtime logs
kubectl logs -n langbot -l app=langbot-plugin-runtime -f
```

#### Restart Services

```bash
# Restart LangBot
kubectl rollout restart deployment/langbot -n langbot

# Restart plugin runtime
kubectl rollout restart deployment/langbot-plugin-runtime -n langbot
```

#### Update Images

```bash
# Update to latest version
kubectl set image deployment/langbot -n langbot langbot=rockchin/langbot:latest
kubectl set image deployment/langbot-plugin-runtime -n langbot langbot-plugin-runtime=rockchin/langbot:latest

# Check update status
kubectl rollout status deployment/langbot -n langbot
```

#### Scaling (Not Recommended)

Note: Due to LangBot using ReadWriteOnce persistent storage, multi-replica scaling is not supported. For high availability, consider using ReadWriteMany storage or alternative architectures.

#### Backup Data

```bash
# Backup PVC data
kubectl exec -n langbot -it <langbot-pod-name> -- tar czf /tmp/backup.tar.gz /app/data
kubectl cp langbot/<langbot-pod-name>:/tmp/backup.tar.gz ./backup.tar.gz
```

### Uninstall

```bash
# Delete all resources (keep PVCs)
kubectl delete deployment,service,configmap -n langbot --all

# Delete PVCs (will delete data)
kubectl delete pvc -n langbot --all

# Delete namespace
kubectl delete namespace langbot
```

### Troubleshooting

#### Pods Not Starting

```bash
# Check Pod status
kubectl get pods -n langbot

# View detailed information
kubectl describe pod -n langbot <pod-name>

# View events
kubectl get events -n langbot --sort-by='.lastTimestamp'
```

#### Storage Issues

```bash
# Check PVC status
kubectl get pvc -n langbot

# Check PV
kubectl get pv
```

#### Network Access Issues

```bash
# Check Service
kubectl get svc -n langbot

# Test port forwarding
kubectl port-forward -n langbot svc/langbot 5300:5300
```

### Production Recommendations

1. **Use specific version tags**: Avoid using `latest` tag, use specific version like `rockchin/langbot:v1.0.0`
2. **Configure resource limits**: Adjust CPU and memory limits based on actual load
3. **Use Ingress + TLS**: Configure HTTPS access and certificate management
4. **Configure monitoring and alerts**: Integrate monitoring tools like Prometheus, Grafana
5. **Regular backups**: Configure automated backup strategy to protect data
6. **Use dedicated StorageClass**: Configure high-performance storage for production
7. **Configure affinity rules**: Ensure Pods are scheduled to appropriate nodes

### Advanced Configuration

#### Using Secrets for Sensitive Information

If you need to configure sensitive information like API keys:

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: langbot-secrets
  namespace: langbot
type: Opaque
data:
  api_key: <base64-encoded-value>
```

Then reference in Deployment:

```yaml
env:
- name: API_KEY
  valueFrom:
    secretKeyRef:
      name: langbot-secrets
      key: api_key
```

#### Configure Horizontal Pod Autoscaling (HPA)

Note: Requires ReadWriteMany storage type

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: langbot-hpa
  namespace: langbot
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: langbot
  minReplicas: 1
  maxReplicas: 3
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
```

### References

- [LangBot Official Documentation](https://docs.langbot.app)
- [Docker Deployment Guide](https://docs.langbot.app/zh/deploy/langbot/docker.html)
- [Kubernetes Official Documentation](https://kubernetes.io/docs/)
