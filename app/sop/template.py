"""
SOP template system.

Defines the structure for Standard Operating Procedures used in
troubleshooting and operational workflows.

SOP Structure:
    - id: Unique identifier
    - title: SOP title
    - problem: Problem description
    - severity: P0/P1/P2/P3 severity level
    - services: Affected services
    - steps: Ordered list of troubleshooting steps
    - rollback: Rollback plan
    - prerequisites: Required tools/permissions
"""

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class SOPStep:
    """A single step in an SOP procedure."""

    order: int
    action: str
    command: Optional[str] = None
    expected: Optional[str] = None
    note: Optional[str] = None
    timeout_seconds: Optional[int] = None

    def to_dict(self) -> dict:
        return {
            "order": self.order,
            "action": self.action,
            "command": self.command,
            "expected": self.expected,
            "note": self.note,
            "timeout_seconds": self.timeout_seconds,
        }


@dataclass
class SOP:
    """Standard Operating Procedure model."""

    id: str
    title: str
    problem: str
    severity: str  # P0, P1, P2, P3
    services: List[str] = field(default_factory=list)
    steps: List[SOPStep] = field(default_factory=list)
    rollback: Optional[str] = None
    prerequisites: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    version: str = "1.0"

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "problem": self.problem,
            "severity": self.severity,
            "services": self.services,
            "steps": [s.to_dict() for s in self.steps],
            "rollback": self.rollback,
            "prerequisites": self.prerequisites,
            "tags": self.tags,
            "version": self.version,
        }


# Built-in SOP templates
SOP_TEMPLATES = {
    "redis-connection": SOP(
        id="sop-redis-001",
        title="Redis连接异常处理流程",
        problem="Redis连接超时或连接被拒绝",
        severity="P1",
        services=["redis", "cache"],
        steps=[
            SOPStep(
                order=1,
                action="检查Redis进程状态",
                command="systemctl status redis-server || ps aux | grep redis-server",
                expected="redis-server进程处于running状态",
            ),
            SOPStep(
                order=2,
                action="检查Redis端口监听",
                command="ss -tlnp | grep 6379",
                expected="端口6379处于LISTEN状态",
                note="如果端口未监听，检查bind配置和protected-mode",
            ),
            SOPStep(
                order=3,
                action="检查Redis日志",
                command="tail -100 /var/log/redis/redis-server.log",
                expected="日志中无ERROR或FATAL级别的错误",
            ),
            SOPStep(
                order=4,
                action="测试Redis连接",
                command="redis-cli -h localhost -p 6379 ping",
                expected="返回PONG响应",
                timeout_seconds=10,
            ),
            SOPStep(
                order=5,
                action="检查内存使用",
                command="redis-cli INFO memory | grep 'used_memory_human\\|maxmemory'",
                expected="已用内存未超过maxmemory限制",
            ),
        ],
        rollback="1. 重启Redis服务: systemctl restart redis-server\n"
        "2. 如果无法恢复，切换至从节点\n"
        "3. 联系DBA团队介入",
        prerequisites=["系统管理员权限", "Redis客户端(redis-cli)"],
        tags=["redis", "cache", "connection", "troubleshooting"],
    ),
    "k8s-pod-crashloop": SOP(
        id="sop-k8s-001",
        title="Kubernetes Pod CrashLoopBackOff 处理流程",
        problem="Pod状态为CrashLoopBackOff，持续重启",
        severity="P1",
        services=["kubernetes", "application"],
        steps=[
            SOPStep(
                order=1,
                action="查看Pod状态和重启次数",
                command="kubectl get pods -n <namespace> | grep CrashLoopBackOff",
                expected="确认问题Pod及重启次数",
            ),
            SOPStep(
                order=2,
                action="查看Pod日志",
                command="kubectl logs <pod-name> -n <namespace> --tail=200",
                expected="日志中显示具体的错误信息",
            ),
            SOPStep(
                order=3,
                action="查看Pod事件",
                command="kubectl describe pod <pod-name> -n <namespace>",
                expected="Events部分显示失败原因（OOM/Liveness探针失败等）",
            ),
            SOPStep(
                order=4,
                action="检查资源限制",
                command="kubectl get pod <pod-name> -n <namespace> -o yaml | grep -A 5 resources",
                expected="确认resources.limits配置是否合理",
            ),
            SOPStep(
                order=5,
                action="根据原因采取相应措施",
                command="- OOM: 增加内存限制\n"
                "- Liveness失败: 检查健康检查路径\n"
                "- 镜像问题: 回滚到上一个版本",
                expected="Pod恢复Running状态",
            ),
        ],
        rollback="1. 执行回滚: kubectl rollout undo deployment/<deploy-name> -n <namespace>\n"
        "2. 扩容临时实例: kubectl scale deployment/<deploy-name> --replicas=3",
        prerequisites=["kubectl配置", "集群访问权限"],
        tags=["kubernetes", "pod", "crashloop", "troubleshooting"],
    ),
}


def get_sop_by_id(sop_id: str) -> Optional[SOP]:
    """Get an SOP template by its ID.

    Args:
        sop_id: SOP identifier (e.g. 'sop-redis-001').

    Returns:
        SOP instance or None if not found.
    """
    # Search by SOP.id across all templates
    for sop in SOP_TEMPLATES.values():
        if sop.id == sop_id:
            return sop
    return None


def search_sops(query: str) -> List[SOP]:
    """Search SOP templates by query string.

    Args:
        query: Search query.

    Returns:
        List of matching SOPs.
    """
    query_lower = query.lower()
    results = []
    for sop in SOP_TEMPLATES.values():
        if (
            query_lower in sop.title.lower()
            or query_lower in sop.problem.lower()
            or query_lower in " ".join(sop.tags).lower()
            or query_lower in " ".join(sop.services).lower()
        ):
            results.append(sop)
    return results


def list_all_sops() -> List[SOP]:
    """List all available SOP templates.

    Returns:
        List of all SOPs.
    """
    return list(SOP_TEMPLATES.values())


def validate_sop_structure(data: dict) -> List[str]:
    """Validate SOP data structure.

    Args:
        data: SOP data dictionary.

    Returns:
        List of validation error messages. Empty if valid.
    """
    errors = []
    required_fields = ["id", "title", "problem", "severity", "steps"]
    for field_name in required_fields:
        if field_name not in data:
            errors.append(f"Missing required field: {field_name}")

    if "steps" in data and isinstance(data["steps"], list):
        for i, step in enumerate(data["steps"]):
            if "action" not in step:
                errors.append(f"Step {i + 1}: missing 'action' field")

    if "severity" in data and data["severity"] not in ("P0", "P1", "P2", "P3"):
        errors.append(f"Invalid severity: {data['severity']}. Must be P0-P3")

    return errors
