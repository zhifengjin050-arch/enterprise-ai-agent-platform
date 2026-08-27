"""Intent classification tests."""

from __future__ import annotations

from app.agent_runtime.planner import TaskPlanner
from app.security.intent import IntentKind, classify_intent


def test_secret_password_question() -> None:
    intent = classify_intent("SSH密码是什么？")
    assert intent.kind == IntentKind.SECRET


def test_secret_english_password() -> None:
    assert classify_intent("what is the ssh password").kind == IntentKind.SECRET


def test_hr_leave_balance() -> None:
    assert classify_intent("我今年年假还有多少天？").kind == IntentKind.HR_SELF


def test_asset_server_count() -> None:
    assert classify_intent("我们公司的服务器有多少台？").kind == IntentKind.ASSET


def test_asset_ip() -> None:
    assert classify_intent("这台机器的 IP 地址是什么？").kind == IntentKind.ASSET


def test_policy_handbook() -> None:
    assert classify_intent("年假制度怎么申请？").kind == IntentKind.POLICY


def test_general_cicd() -> None:
    assert classify_intent("什么是 CI/CD？").kind == IntentKind.GENERAL


def test_planner_secret_has_no_tools() -> None:
    plan = TaskPlanner().plan("root 密码是什么")
    assert plan.steps == []
    assert plan.rationale == "secret_denied"


def test_planner_hr_does_not_add_graph() -> None:
    plan = TaskPlanner().plan("我今年年假还有多少天？")
    tools = [s.tool for s in plan.steps]
    assert tools == ["knowledge_search"]
