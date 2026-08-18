"""Tests for TaskPlanner."""

from __future__ import annotations

import pytest

from app.agent_runtime.planner import TaskPlanner


@pytest.fixture
def planner() -> TaskPlanner:
    return TaskPlanner()


class TestTaskPlannerBasic:
    def test_empty_query_still_plans(self, planner: TaskPlanner) -> None:
        plan = planner.plan("")
        assert plan.query == ""
        assert len(plan.steps) >= 1
        assert plan.steps[0].tool == "knowledge_search"

    def test_simple_qa(self, planner: TaskPlanner) -> None:
        plan = planner.plan("什么是 CI/CD？")
        assert plan.steps[0].tool == "knowledge_search"
        assert "knowledge_search" in plan.rationale

    def test_plan_to_dict(self, planner: TaskPlanner) -> None:
        plan = planner.plan("hello")
        d = plan.to_dict()
        assert "steps" in d
        assert d["steps"][0]["step"] == 1

    def test_step_input_contains_query(self, planner: TaskPlanner) -> None:
        q = "如何部署服务"
        plan = planner.plan(q)
        assert plan.steps[0].input["query"] == q


class TestTaskPlannerHints:
    @pytest.mark.parametrize(
        "query",
        [
            "为什么 Kubernetes Pod 一直 OOM？",
            "k8s deployment crash",
            "Pod OOMKilled",
            "container memory limit",
        ],
    )
    def test_k8s_adds_graph(self, planner: TaskPlanner, query: str) -> None:
        plan = planner.plan(query)
        tools = [s.tool for s in plan.steps]
        assert "knowledge_search" in tools
        assert "graph_query" in tools

    @pytest.mark.parametrize(
        "query",
        [
            "系统故障 error 500",
            "服务 timeout 超时",
            "crash loop",
            "历史故障根因",
        ],
    )
    def test_incident_adds_extra_search(self, planner: TaskPlanner, query: str) -> None:
        plan = planner.plan(query)
        search_steps = [s for s in plan.steps if s.tool == "knowledge_search"]
        assert len(search_steps) >= 2

    @pytest.mark.parametrize(
        "query",
        [
            "依赖关系是什么",
            "图谱关联实体",
            "谁负责这个系统",
            "entity depends on",
        ],
    )
    def test_graph_hints(self, planner: TaskPlanner, query: str) -> None:
        plan = planner.plan(query)
        assert any(s.tool == "graph_query" for s in plan.steps)

    @pytest.mark.parametrize(
        "query",
        [
            "同步飞书文档",
            "connector sync gitlab",
            "拉取语雀知识库",
        ],
    )
    def test_sync_hints(self, planner: TaskPlanner, query: str) -> None:
        plan = planner.plan(query)
        assert any(s.tool == "connector_sync" for s in plan.steps)

    def test_oom_full_plan(self, planner: TaskPlanner) -> None:
        plan = planner.plan("为什么 Kubernetes Pod 一直 OOM？")
        tools = [s.tool for s in plan.steps]
        assert tools[0] == "knowledge_search"
        assert "graph_query" in tools
        # OOM triggers incident search
        assert tools.count("knowledge_search") >= 2

    def test_graph_entity_kubernetes(self, planner: TaskPlanner) -> None:
        plan = planner.plan("Kubernetes Pod OOM")
        graph = next(s for s in plan.steps if s.tool == "graph_query")
        assert graph.input["entity_name"] == "Kubernetes"

    def test_graph_entity_redis(self, planner: TaskPlanner) -> None:
        plan = planner.plan("Redis 依赖关系")
        graph = next(s for s in plan.steps if s.tool == "graph_query")
        assert graph.input["entity_name"] == "Redis"

    def test_guess_entity_fallback_token(self, planner: TaskPlanner) -> None:
        name = planner._guess_entity("Check FooBar service health")
        assert name == "Check" or name == "FooBar" or len(name) >= 3

    def test_guess_entity_empty(self, planner: TaskPlanner) -> None:
        assert planner._guess_entity("你好世界") == ""

    @pytest.mark.parametrize(
        "name",
        ["Docker", "MySQL", "PostgreSQL", "Nginx", "Kafka", "Prometheus"],
    )
    def test_known_entities(self, planner: TaskPlanner, name: str) -> None:
        plan = planner.plan(f"{name} 依赖图谱")
        graph = next(s for s in plan.steps if s.tool == "graph_query")
        assert graph.input["entity_name"] == name

    def test_steps_are_ordered(self, planner: TaskPlanner) -> None:
        plan = planner.plan("Kubernetes OOM sync 飞书")
        steps = [s.step for s in plan.steps]
        assert steps == list(range(1, len(steps) + 1))

    def test_descriptions_present(self, planner: TaskPlanner) -> None:
        plan = planner.plan("Kubernetes OOM")
        for s in plan.steps:
            assert s.description

    def test_plan_step_to_dict(self, planner: TaskPlanner) -> None:
        plan = planner.plan("test")
        d = plan.steps[0].to_dict()
        assert set(d.keys()) >= {"step", "tool", "input", "description"}
