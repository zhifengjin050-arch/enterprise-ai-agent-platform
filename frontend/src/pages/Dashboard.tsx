import { useState, useEffect } from "react"
import {
  getHealth,
  getKnowledgeStats,
  getAgents,
  getWorkflows,
  getMetricsOverview,
} from "@/lib/api"
import type {
  HealthResponse,
  KnowledgeStats,
  AgentListResponse,
  MetricsOverview,
} from "@/types/api"
import { cn, formatNumber } from "@/lib/utils"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import {
  FileText,
  Layers,
  Library,
  Bot,
  Workflow,
  DollarSign,
  Heart,
  ArrowRight,
  Database,
  Search,
  Cog,
  Zap,
  Terminal,
} from "lucide-react"

interface StatCardData {
  title: string
  icon: React.ElementType
  loading: boolean
  error: string | null
  value: string | number | null
  color: string
}

export default function Dashboard() {
  const [health, setHealth] = useState<HealthResponse | null>(null)
  const [healthLoading, setHealthLoading] = useState(true)
  const [healthError, setHealthError] = useState<string | null>(null)

  const [knowledgeStats, setKnowledgeStats] = useState<KnowledgeStats | null>(
    null
  )
  const [knowledgeLoading, setKnowledgeLoading] = useState(true)
  const [knowledgeError, setKnowledgeError] = useState<string | null>(null)

  const [agentsData, setAgentsData] = useState<AgentListResponse | null>(null)
  const [agentsLoading, setAgentsLoading] = useState(true)
  const [agentsError, setAgentsError] = useState<string | null>(null)

  const [workflows, setWorkflows] = useState<any[] | null>(null)
  const [workflowsLoading, setWorkflowsLoading] = useState(true)
  const [workflowsError, setWorkflowsError] = useState<string | null>(null)

  const [metrics, setMetrics] = useState<MetricsOverview | null>(null)
  const [metricsLoading, setMetricsLoading] = useState(true)
  const [metricsError, setMetricsError] = useState<string | null>(null)

  useEffect(() => {
    getHealth()
      .then(setHealth)
      .catch((e) => setHealthError(e.message))
      .finally(() => setHealthLoading(false))

    getKnowledgeStats()
      .then(setKnowledgeStats)
      .catch((e) => setKnowledgeError(e.message))
      .finally(() => setKnowledgeLoading(false))

    getAgents()
      .then(setAgentsData)
      .catch((e) => setAgentsError(e.message))
      .finally(() => setAgentsLoading(false))

    getWorkflows()
      .then(setWorkflows)
      .catch((e) => setWorkflowsError(e.message))
      .finally(() => setWorkflowsLoading(false))

    getMetricsOverview()
      .then(setMetrics)
      .catch((e) => setMetricsError(e.message))
      .finally(() => setMetricsLoading(false))
  }, [])

  const statCards: StatCardData[] = [
    {
      title: "文档总数",
      icon: FileText,
      loading: knowledgeLoading,
      error: knowledgeError,
      value: knowledgeStats ? formatNumber(knowledgeStats.total_documents) : null,
      color: "text-blue-600 dark:text-blue-400",
    },
    {
      title: "知识片段",
      icon: Layers,
      loading: knowledgeLoading,
      error: knowledgeError,
      value: knowledgeStats
        ? formatNumber(
            Object.values(knowledgeStats.by_type || {}).reduce(
              (a, b) => a + b,
              0
            )
          )
        : null,
      color: "text-indigo-600 dark:text-indigo-400",
    },
    {
      title: "智能体数量",
      icon: Bot,
      loading: agentsLoading,
      error: agentsError,
      value: agentsData ? formatNumber(agentsData.total) : null,
      color: "text-purple-600 dark:text-purple-400",
    },
    {
      title: "工作流执行",
      icon: Workflow,
      loading: workflowsLoading,
      error: workflowsError,
      value: workflows ? formatNumber(workflows.length) : null,
      color: "text-amber-600 dark:text-amber-400",
    },
    {
      title: "Token 消耗",
      icon: DollarSign,
      loading: metricsLoading,
      error: metricsError,
      value: metrics ? formatNumber(metrics.llm_calls) : null,
      color: "text-green-600 dark:text-green-400",
    },
    {
      title: "系统状态",
      icon: Heart,
      loading: healthLoading,
      error: healthError,
      value: health?.status === "healthy" ? "健康" : health?.status || "未知",
      color:
        health?.status === "healthy"
          ? "text-green-600 dark:text-green-400"
          : "text-red-600 dark:text-red-400",
    },
  ]

  const pipelineStages = [
    { label: "连接器", icon: Database, color: "bg-blue-500" },
    { label: "同步", icon: ArrowRight, color: "bg-cyan-500" },
    { label: "知识库", icon: Library, color: "bg-indigo-500" },
    { label: "智能体", icon: Bot, color: "bg-purple-500" },
    { label: "工作流", icon: Workflow, color: "bg-amber-500" },
    { label: "API", icon: Terminal, color: "bg-green-500" },
  ]

  return (
    <div className="space-y-6">
      {/* Welcome banner */}
      <Card className="border-none bg-gradient-to-r from-primary/10 via-primary/5 to-background">
        <CardContent className="p-6">
          <h2 className="text-2xl font-bold tracking-tight">
            Enterprise AI Agent Platform v1.0
          </h2>
          <p className="mt-2 text-muted-foreground">
            企业级 DevOps RAG 知识库智能体平台，集成文档管理、知识检索、智能体编排、
            工作流自动化与系统监控能力。
          </p>
        </CardContent>
      </Card>

      {/* Stat cards */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">
        {statCards.map((card) => {
          const Icon = card.icon
          return (
            <Card key={card.title}>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">
                  {card.title}
                </CardTitle>
                <Icon className={cn("h-4 w-4", card.color)} />
              </CardHeader>
              <CardContent>
                {card.loading ? (
                  <div className="h-8 flex items-center">
                    <div className="h-4 w-16 animate-pulse rounded bg-muted" />
                  </div>
                ) : card.error ? (
                  <p className="text-sm text-destructive">{card.error}</p>
                ) : (
                  <div className="text-2xl font-bold">{card.value}</div>
                )}
              </CardContent>
            </Card>
          )
        })}
      </div>

      {/* Platform Architecture pipeline */}
      <Card>
        <CardHeader>
          <CardTitle>平台架构</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap items-center justify-center gap-2 py-4">
            {pipelineStages.map((stage, index) => {
              const StageIcon = stage.icon
              return (
                <div
                  key={stage.label}
                  className="flex items-center gap-2"
                >
                  <div
                    className={cn(
                      "flex h-16 w-16 flex-col items-center justify-center rounded-xl text-white shadow-md transition-transform hover:scale-105",
                      stage.color
                    )}
                  >
                    <StageIcon className="h-6 w-6" />
                    <span className="mt-1 text-[10px] font-medium">
                      {stage.label}
                    </span>
                  </div>
                  {index < pipelineStages.length - 1 && (
                    <ArrowRight className="h-5 w-5 text-muted-foreground/40 hidden sm:block" />
                  )}
                </div>
              )
            })}
          </div>
        </CardContent>
      </Card>
    </div>
  )
}