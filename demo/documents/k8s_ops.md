---
title: Kubernetes 运维规范
doc_type: SOP
tags: [kubernetes, ops, deployment, troubleshooting]
version: 2.0
author: SRE Team
---

# Kubernetes 运维规范

## 1. 集群管理

### 1.1 集群版本策略
- 生产集群使用 Kubernetes v1.28+
- 测试集群可宽松一个版本
- 每季度评估版本升级

### 1.2 节点管理
- 节点规格：最少 4C16G
- 节点最大 Pod 数：110
- 节点预留资源：系统 10%，Kubelet 5%

## 2. Pod 运维

### 2.1 Pod 生命周期管理
- 所有 Pod 必须设置 Resource Request/Limit
- CPU Request = 实际使用量 * 1.2
- Memory Request = 实际使用量 * 1.5
- Limit = Request * 2

### 2.2 健康检查
- 必须配置 livenessProbe 和 readinessProbe
- 初始延迟: 30s
- 检查间隔: 15s
- 超时: 5s

### 2.3 Pod OOM 处理流程

当 Pod 出现 OOM (Out of Memory) 错误时：

1. **立即诊断**
   ```bash
   # 查看 Pod 状态
   kubectl describe pod <pod-name> -n <namespace>
   
   # 查看日志
   kubectl logs <pod-name> -n <namespace> --previous
   
   # 查看资源使用
   kubectl top pod <pod-name> -n <namespace>
   ```

2. **紧急恢复**
   - 增加 Memory Limit（1.5x）
   - 滚动重启 Pod
   - 监控是否复现

3. **根因分析**
   - 检查是否有内存泄漏
   - 检查 JVM / 运行时参数
   - 检查业务流量突增

4. **长期修复**
   - 设置 HPA (Horizontal Pod Autoscaler)
   - 配置 VPA (Vertical Pod Autoscaler)
   - 实施内存限制告警（>80%）

### 2.4 Pod CrashLoopBackOff 处理

1. 查看 logs: `kubectl logs --previous`
2. 检查配置: `kubectl describe`
3. 验证镜像: 是否存在、版本正确
4. 检查资源: 是否超出 limit

## 3. 服务发现

### 3.1 Service 规范
- 内部服务使用 ClusterIP
- 外部服务使用 LoadBalancer
- 微服务间使用 DNS 发现

### 3.2 Ingress 配置
```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  annotations:
    nginx.ingress.kubernetes.io/ssl-redirect: "true"
spec:
  rules:
  - host: api.example.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: api-gateway
            port:
              number: 80
```

## 4. 监控告警

### 4.1 关键指标
- Pod CPU 使用率 > 80%: Warning
- Pod 内存使用率 > 80%: Warning
- Pod 重启次数 > 3/小时: Critical
- Node 磁盘使用率 > 85%: Warning

### 4.2 告警响应时间
- Critical: 15分钟
- Warning: 1小时
- Info: 24小时

## 5. 故障演练

### 5.1 定期演练项目
- Pod 故障恢复（季度）
- 节点故障转移（半年）
- 集群升级演练（年）
- 灾难恢复演练（年）