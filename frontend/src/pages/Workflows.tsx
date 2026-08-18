import { useState, useEffect } from "react"
import {
  getWorkflows,
  getWorkflowRuns,
  executeWorkflow,
  cancelWorkflowRun,
} from "@/lib/api"
import type { WorkflowDefinition, WorkflowRun } from "@/types/api"
import { cn, formatDate } from "@/lib/utils"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Workflow,
  Loader2,
  AlertCircle,
  Play,
  XCircle,
  ChevronDown,
  ChevronRight,
  Zap,
  Bot,
  Wrench,
  CheckCircle2,
} from "lucide-react"

const workflowStatusBadge = (status: string) => {
  switch (status) {
    case "CREATED":
      return <Badge variant="secondary">已创建</Badge>
    case "RUNNING":
      return <Badge variant="warning">运行中</Badge>
    case "WAITING":
      return <Badge variant="outline">等待中</Badge>
    case "PAUSED":
      return <Badge variant="warning">已暂停</Badge>
    case "COMPLETED":
      return <Badge variant="success">已完成</Badge>
    case "FAILED":
      return <Badge variant="destructive">失败</Badge>
    default:
      return <Badge variant="secondary">{status}</Badge>
  }
}

const runStatusBadge = (status: string) => {
  switch (status) {
    case "CREATED":
      return <Badge variant="secondary">已创建</Badge>
    case "RUNNING":
      return <Badge variant="warning">运行中</Badge>
    case "WAITING":
      return <Badge variant="outline">等待中</Badge>
    case "PAUSED":
      return <Badge variant="warning">已暂停</Badge>
    case "COMPLETED":
      return <Badge variant="success">已完成</Badge>
    case "FAILED":
      return <Badge variant="destructive">失败</Badge>
    default:
      return <Badge variant="secondary">{status}</Badge>
  }
}

export default function WorkflowsPage() {
  const [workflows, setWorkflows] = useState<WorkflowDefinition[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // Expanded workflow with runs
  const [expandedId, setExpandedId] = useState<string | null>(null)
  const [runs, setRuns] = useState<Record<string, WorkflowRun[]>>({})
  const [runsLoading, setRunsLoading] = useState<Record<string, boolean>>({})
  const [runsError, setRunsError] = useState<Record<string, string | null>>({})

  useEffect(() => {
    loadWorkflows()
  }, [])

  async function loadWorkflows() {
    setLoading(true)
    setError(null)
    try {
      const res = await getWorkflows()
      setWorkflows(res)
    } catch (e: any) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  async function toggleExpand(workflowId: string) {
    if (expandedId === workflowId) {
      setExpandedId(null)
      return
    }
    setExpandedId(workflowId)

    if (!runs[workflowId]) {
      setRunsLoading((prev) => ({ ...prev, [workflowId]: true }))
      try {
        const data = await getWorkflowRuns(workflowId)
        setRuns((prev) => ({ ...prev, [workflowId]: data }))
      } catch (e: any) {
        setRunsError((prev) => ({ ...prev, [workflowId]: e.message }))
      } finally {
        setRunsLoading((prev) => ({ ...prev, [workflowId]: false }))
      }
    }
  }

  async function handleExecute(workflowId: string) {
    try {
      await executeWorkflow(workflowId)
      // Refresh runs for this workflow
      const data = await getWorkflowRuns(workflowId)
      setRuns((prev) => ({ ...prev, [workflowId]: data }))
    } catch (e: any) {
      // Handle error inline
      setRunsError((prev) => ({ ...prev, [workflowId]: e.message }))
    }
  }

  async function handleCancel(runId: string) {
    try {
      await cancelWorkflowRun(runId)
      // Refresh runs for all expanded workflows
      if (expandedId) {
        const data = await getWorkflowRuns(expandedId)
        setRuns((prev) => ({ ...prev, [expandedId]: data }))
      }
    } catch (e: any) {
      console.error("Cancel failed:", e)
    }
  }

  const nodeChain = [
    { label: "触发器", icon: Zap, color: "bg-blue-500" },
    { label: "智能体", icon: Bot, color: "bg-purple-500" },
    { label: "工具", icon: Wrench, color: "bg-amber-500" },
    { label: "审批", icon: CheckCircle2, color: "bg-green-500" },
    { label: "结束", icon: XCircle, color: "bg-slate-500" },
  ]

  // Loading state
  if (loading) {
    return (
      <div className="flex h-96 items-center justify-center">
        <div className="flex items-center gap-2 text-muted-foreground">
          <Loader2 className="h-5 w-5 animate-spin" />
          <span>加载中...</span>
        </div>
      </div>
    )
  }

  // Error state
  if (error) {
    return (
      <div className="flex h-96 items-center justify-center">
        <div className="flex flex-col items-center gap-2 text-destructive">
          <AlertCircle className="h-8 w-8" />
          <p className="text-sm">加载失败: {error}</p>
          <Button variant="outline" size="sm" onClick={loadWorkflows}>
            重试
          </Button>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold tracking-tight">工作流引擎</h2>
        <p className="text-muted-foreground">
          管理工作流定义和执行
        </p>
      </div>

      {/* Visual node chain */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">工作流节点链</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap items-center justify-center gap-1 py-2">
            {nodeChain.map((node, index) => {
              const NodeIcon = node.icon
              return (
                <div key={node.label} className="flex items-center gap-1">
                  <div
                    className={cn(
                      "flex h-10 w-10 items-center justify-center rounded-lg text-white shadow-sm",
                      node.color
                    )}
                  >
                    <NodeIcon className="h-5 w-5" />
                  </div>
                  <span className="text-xs font-medium text-muted-foreground mr-1">
                    {node.label}
                  </span>
                  {index < nodeChain.length - 1 && (
                    <ChevronRight className="h-4 w-4 text-muted-foreground/40" />
                  )}
                </div>
              )
            })}
          </div>
        </CardContent>
      </Card>

      {/* Empty state */}
      {workflows.length === 0 && (
        <Card>
          <CardContent className="flex flex-col items-center gap-4 py-12">
            <Workflow className="h-12 w-12 text-muted-foreground/40" />
            <p className="text-muted-foreground">暂无工作流定义</p>
          </CardContent>
        </Card>
      )}

      {/* Workflow cards */}
      <div className="space-y-4">
        {workflows.map((wf) => (
          <Card key={wf.id}>
            <CardHeader className="flex flex-row items-start justify-between space-y-0">
              <div className="flex items-center gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10">
                  <Workflow className="h-5 w-5 text-primary" />
                </div>
                <div>
                  <CardTitle className="text-base">{wf.name}</CardTitle>
                  <p className="text-xs text-muted-foreground">
                    {wf.description || "无描述"}
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-2">
                {workflowStatusBadge(wf.status)}
              </div>
            </CardHeader>
            <CardContent>
              {/* Meta info */}
              <div className="flex flex-wrap gap-4 text-sm text-muted-foreground mb-3">
                <span>
                  节点数: <strong>{wf.node_count}</strong>
                </span>
                <span>
                  触发器: <strong>{wf.trigger_type}</strong>
                </span>
                <span>
                  版本: <strong>v{wf.version}</strong>
                </span>
              </div>

              {/* Action buttons */}
              <div className="flex flex-wrap gap-2 mb-3">
                <Button
                  size="sm"
                  className="gap-1.5"
                  onClick={() => handleExecute(wf.id)}
                >
                  <Play className="h-3.5 w-3.5" />
                  执行
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  className="gap-1.5"
                  onClick={() => toggleExpand(wf.id)}
                >
                  {expandedId === wf.id ? (
                    <ChevronDown className="h-3.5 w-3.5" />
                  ) : (
                    <ChevronRight className="h-3.5 w-3.5" />
                  )}
                  {expandedId === wf.id ? "收起运行记录" : "查看运行记录"}
                </Button>
              </div>

              {/* Runs list */}
              {expandedId === wf.id && (
                <div className="border-t pt-3">
                  {runsLoading[wf.id] ? (
                    <div className="flex items-center justify-center py-4">
                      <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
                    </div>
                  ) : runsError[wf.id] ? (
                    <p className="text-sm text-destructive">
                      {runsError[wf.id]}
                    </p>
                  ) : !runs[wf.id] || runs[wf.id].length === 0 ? (
                    <p className="text-sm text-muted-foreground py-2">
                      暂无运行记录
                    </p>
                  ) : (
                    <div className="space-y-2">
                      {runs[wf.id].map((run) => (
                        <div
                          key={run.id}
                          className="flex flex-wrap items-center justify-between gap-2 rounded-md border p-3 text-sm"
                        >
                          <div className="flex items-center gap-3">
                            {runStatusBadge(run.status)}
                            <span className="text-muted-foreground">
                              当前节点:{" "}
                              <strong>{run.current_node || "-"}</strong>
                            </span>
                          </div>
                          <div className="flex items-center gap-3 text-muted-foreground">
                            <span>开始: {formatDate(run.started_at)}</span>
                            {run.duration_ms !== null && (
                              <span>
                                耗时:{" "}
                                {(run.duration_ms / 1000).toFixed(1)}s
                              </span>
                            )}
                            {run.status === "RUNNING" && (
                              <Button
                                variant="ghost"
                                size="sm"
                                className="gap-1 text-destructive hover:text-destructive"
                                onClick={() => handleCancel(run.id)}
                              >
                                <XCircle className="h-3.5 w-3.5" />
                                取消
                              </Button>
                            )}
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  )
}