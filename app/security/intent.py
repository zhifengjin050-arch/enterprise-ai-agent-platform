"""Intent classification for enterprise questions.

Secret questions are hard-denied. HR and asset questions are routed to
identity-bound tools rather than dumping unrestricted RAG hits.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum


class IntentKind(str, Enum):
    POLICY = "policy"
    HR_SELF = "hr_self"
    ASSET = "asset"
    SECRET = "secret"
    GENERAL = "general"


SECRET_REFUSAL = (
    "凭据不能通过对话查询。SSH 密码、云密钥、证书私钥等存放在 Vault / PAM 中，"
    "请走已审批的堡垒机或工单获取短期访问。本次请求已记录审计。"
)

_SECRET_RE = re.compile(
    r"("
    r"ssh\s*密码|ssh\s*password|root\s*密码|登录密码|口令|"
    r"private\s*key|私钥|kubeconfig|"
    r"api[_-]?secret|secret\s*key|access[_-]?key|"
    r"密码是(什么|多少)|password\s*(is|:|什么|多少)|"
    r"token\s*(是什么|是多少)"
    r")",
    re.IGNORECASE,
)
_HR_RE = re.compile(
    r"("
    r"我(的|今年|今年的)?.*(年假|假|工资|薪酬|绩效)|"
    r"年假还(有|剩)|还有多少天假|剩余.*年假|"
    r"我的(考勤|加班费)|leave\s*balance|\bpto\b"
    r")",
    re.IGNORECASE,
)
_ASSET_RE = re.compile(
    r"(服务器|主机|机器).*(多少|几台|数量)|"
    r"(多少|几)台.*(服务器|主机|机器)|"
    r"\bip\s*(地址|是什么|多少)|"
    r"cmdb|资产(清单|目录)|集群.*节点",
    re.IGNORECASE,
)
_POLICY_RE = re.compile(
    r"(制度|政策|规定|流程|sop|怎么申请|如何申请|handbook|runbook)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class Intent:
    kind: IntentKind
    reason: str

    @property
    def allow_rag(self) -> bool:
        return self.kind != IntentKind.SECRET

    @property
    def allow_live_tools(self) -> bool:
        return self.kind in {
            IntentKind.HR_SELF,
            IntentKind.ASSET,
            IntentKind.GENERAL,
            IntentKind.POLICY,
        }


def classify_intent(query: str) -> Intent:
    """Classify a natural-language employee question."""
    q = (query or "").strip()
    if not q:
        return Intent(IntentKind.GENERAL, "empty")
    if _SECRET_RE.search(q):
        return Intent(IntentKind.SECRET, "credential_pattern")
    if _HR_RE.search(q):
        return Intent(IntentKind.HR_SELF, "hr_self_pattern")
    if _ASSET_RE.search(q):
        return Intent(IntentKind.ASSET, "asset_pattern")
    if _POLICY_RE.search(q):
        return Intent(IntentKind.POLICY, "policy_pattern")
    return Intent(IntentKind.GENERAL, "default")
