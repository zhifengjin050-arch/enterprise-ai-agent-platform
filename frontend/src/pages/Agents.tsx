import { useState, useEffect } from "react"
import { getAgents, executeAgent } from "@/lib/api"
import type { Agent, AgentExecuteResponse } from "@/types/api"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Bot,
  Zap,
  Loader2,
  AlertCircle,
  Play,
  X,
  FileText,
  Wrench,
} from "lucide-react"

export default function Agents() {
  const [agents, setAgents] = useState<Agent[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // Execute dialog state
  const [executingAgent, setExecutingAgent] = useState<Agent | null>(null)
  const [taskInput, setTaskInput] = useState("")
  const [execResult, setExecResult] = useState<AgentExecuteResponse | null>(null)
  const [execLoading, setExecLoading] = useState(false)
  const [execError, setExecError] = useState<string | null>(null)

  useEffect(() => {
    loadAgents()
  }, [])

  async function loadAgents() {
    setLoading(true)
    setError(null)
    try {
      const res = await getAgents()
      setAgents(res.data)
    } catch (e: any) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  async function handleExecute() {
    if (!executingAgent || !taskInput.trim()) return
    setExecLoading(true)
    setExecError(null)
    setExecResult(null)
    try {
      const res = await executeAgent(executingAgent.id, taskInput)
      setExecResult(res)
    } catch (e: any) {
      setExecError(e.message)
    } finally {
      setExecLoading(false)
    }
  }

  function closeDialog() {
    setExecutingAgent(null)
    setTaskInput("")
    setExecResult(null)
    setExecError(null)
  }

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
          <Button variant="outline" size="sm" onClick={loadAgents}>
            重试
          </Button>
        </div>
      </div>
    )
  }

  // Empty state
  if (agents.length === 0) {
    return (
      <div className="space-y-6">
        <div>
          <h2 className="text-2xl font-bold tracking-tight">AI 智能体</h2>
          <p className="text-muted-foreground">
            管理和执行 AI 智能体任务
          </p>
        </div>
        <Card>
          <CardContent className="flex flex-col items-center gap-4 py-12">
            <Bot className="h-12 w-12 text-muted-foreground/40" />
            <p className="text-muted-foreground">暂无智能体</p>
          </CardContent>
        </Card>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold tracking-tight">AI 智能体</h2>
        <p className="text-muted-foreground">
          管理和执行 AI 智能体任务
        </p>
      </div>

      {/* Agent cards grid */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {agents.map((agent) => (
          <Card key={agent.id}>
            <CardHeader className="flex flex-row items-start justify-between space-y-0">
              <div className="flex items-center gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10">
                  <Bot className="h-5 w-5 text-primary" />
                </div>
                <div>
                  <CardTitle className="text-base">{agent.name}</CardTitle>
                  <p className="text-xs text-muted-foreground">
                    {agent.agent_type}
                  </p>
                </div>
              </div>
              <Badge
                variant={agent.enabled ? "success" : "secondary"}
                className="shrink-0"
              >
                {agent.enabled ? "已启用" : "已禁用"}
              </Badge>
            </CardHeader>
            <CardContent>
              <Button
                className="w-full gap-2"
                size="sm"
                onClick={() => setExecutingAgent(agent)}
              >
                <Play className="h-4 w-4" />
                执行
              </Button>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Execute dialog overlay */}
      {executingAgent && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
          onClick={closeDialog}
        >
          <Card
            className="w-full max-w-2xl max-h-[80vh] overflow-y-auto"
            onClick={(e) => e.stopPropagation()}
          >
            <CardHeader className="flex flex-row items-start justify-between">
              <div>
                <CardTitle className="text-lg">
                  执行: {executingAgent.name}
                </CardTitle>
                <p className="text-sm text-muted-foreground">
                  {executingAgent.agent_type}
                </p>
              </div>
              <Button variant="ghost" size="icon" onClick={closeDialog}>
                <X className="h-4 w-4" />
              </Button>
            </CardHeader>
            <CardContent className="space-y-4">
              {/* Task input */}
              <div>
                <label className="mb-1.5 block text-sm font-medium">
                  任务描述
                </label>
                <textarea
                  className="flex min-h-[100px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
                  placeholder="请输入任务描述..."
                  value={taskInput}
                  onChange={(e) => setTaskInput(e.target.value)}
                />
              </div>

              <Button
                className="w-full gap-2"
                onClick={handleExecute}
                disabled={execLoading || !taskInput.trim()}
              >
                {execLoading ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin" />
                    执行中...
                  </>
                ) : (
                  <>
                    <Zap className="h-4 w-4" />
                    运行
                  </>
                )}
              </Button>

              {/* Execute error */}
              {execError && (
                <div className="flex items-center gap-2 rounded-md bg-destructive/10 p-3 text-sm text-destructive">
                  <AlertCircle className="h-4 w-4 flex-shrink-0" />
                  <span>{execError}</span>
                </div>
              )}

              {/* Execute result */}
              {execResult && (
                <div className="space-y-4">
                  {/* Answer */}
                  <div>
                    <h4 className="mb-1 text-sm font-medium">回答</h4>
                    <div className="rounded-md bg-muted p-3 text-sm whitespace-pre-wrap">
                      {execResult.data.answer}
                    </div>
                  </div>

                  {/* Sources */}
                  {(execResult.data.sources ?? []).length > 0 && (
                    <div>
                      <h4 className="mb-2 text-sm font-medium">来源 ({execResult.data.sources.length})</h4>
                      <div className="space-y-2">
                        {execResult.data.sources.map((src, i) => (
                          <div
                            key={i}
                            className="flex items-start gap-2 rounded-md border p-2 text-sm"
                          >
                            <FileText className="mt-0.5 h-4 w-4 flex-shrink-0 text-muted-foreground" />
                            <div className="flex-1 min-w-0">
                              <p className="font-medium truncate">
                                {src.title}
                              </p>
                              <p className="text-xs text-muted-foreground">
                                相关度: {(src.score * 100).toFixed(1)}%
                              </p>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Tool calls */}
                  {(execResult.data.tool_calls ?? []).length > 0 && (
                    <div>
                      <h4 className="mb-2 text-sm font-medium">工具调用 ({execResult.data.tool_calls.length})</h4>
                      <div className="space-y-2">
                        {execResult.data.tool_calls.map((tc, i) => (
                          <div
                            key={i}
                            className="rounded-md border p-2 text-sm"
                          >
                            <div className="flex items-center gap-2">
                              <Wrench className="h-4 w-4 text-muted-foreground" />
                              <span className="font-medium">{tc.tool}</span>
                            </div>
                            <details className="mt-1">
                              <summary className="cursor-pointer text-xs text-muted-foreground">
                                查看详情
                              </summary>
                              <pre className="mt-1 overflow-x-auto rounded bg-muted p-2 text-xs">
                                {JSON.stringify({ input: tc.input, output: tc.output }, null, 2)}
                              </pre>
                            </details>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  )
}