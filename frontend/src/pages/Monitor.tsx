import { useState, useEffect } from "react"
import {
  getMetricsOverview,
  getMetricsAgents,
  getMetricsLLM,
  getMetricsErrors,
  getMetricsSync,
  getHealth,
} from "@/lib/api"
import type {
  MetricsOverview,
  MetricsAgents,
  MetricsLLM,
  ErrorMetrics,
  SyncMetrics,
  HealthResponse,
} from "@/types/api"
import { cn, formatNumber, formatCost } from "@/lib/utils"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import {
  Activity,
  Bot,
  AlertTriangle,
  Database,
  DollarSign,
  Loader2,
  AlertCircle,
  RefreshCw,
  Gauge,
  PieChart,
} from "lucide-react"

interface AsyncData<T> {
  data: T | null
  loading: boolean
  error: string | null
}

export default function Monitor() {
  const [overview, setOverview] = useState<AsyncData<MetricsOverview>>({
    data: null,
    loading: true,
    error: null,
  })
  const [agents, setAgents] = useState<AsyncData<MetricsAgents>>({
    data: null,
    loading: true,
    error: null,
  })
  const [llm, setLlm] = useState<AsyncData<MetricsLLM>>({
    data: null,
    loading: true,
    error: null,
  })
  const [errors, setErrors] = useState<AsyncData<ErrorMetrics>>({
    data: null,
    loading: true,
    error: null,
  })
  const [sync, setSync] = useState<AsyncData<SyncMetrics>>({
    data: null,
    loading: true,
    error: null,
  })
  const [health, setHealthData] = useState<AsyncData<HealthResponse>>({
    data: null,
    loading: true,
    error: null,
  })

  useEffect(() => {
    loadAll()
  }, [])

  function loadAll() {
    // Reset
    setOverview((prev) => ({ ...prev, loading: true, error: null }))
    setAgents((prev) => ({ ...prev, loading: true, error: null }))
    setLlm((prev) => ({ ...prev, loading: true, error: null }))
    setErrors((prev) => ({ ...prev, loading: true, error: null }))
    setSync((prev) => ({ ...prev, loading: true, error: null }))
    setHealthData((prev) => ({ ...prev, loading: true, error: null }))

    getMetricsOverview()
      .then((data) => setOverview({ data, loading: false, error: null }))
      .catch((e) =>
        setOverview({ data: null, loading: false, error: e.message })
      )

    getMetricsAgents()
      .then((data) => setAgents({ data, loading: false, error: null }))
      .catch((e) =>
        setAgents({ data: null, loading: false, error: e.message })
      )

    getMetricsLLM()
      .then((data) => setLlm({ data, loading: false, error: null }))
      .catch((e) => setLlm({ data: null, loading: false, error: e.message }))

    getMetricsErrors()
      .then((data) => setErrors({ data, loading: false, error: null }))
      .catch((e) =>
        setErrors({ data: null, loading: false, error: e.message })
      )

    getMetricsSync()
      .then((data) => setSync({ data, loading: false, error: null }))
      .catch((e) => setSync({ data: null, loading: false, error: e.message }))

    getHealth()
      .then((data) => setHealthData({ data, loading: false, error: null }))
      .catch((e) =>
        setHealthData({ data: null, loading: false, error: e.message })
      )
  }

  const MetricCard = ({
    title,
    icon: Icon,
    state,
    value,
    color,
    suffix,
  }: {
    title: string
    icon: React.ElementType
    state: AsyncData<any>
    value: React.ReactNode
    color: string
    suffix?: string
  }) => (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
        <CardTitle className="text-sm font-medium">{title}</CardTitle>
        <Icon className={cn("h-4 w-4", color)} />
      </CardHeader>
      <CardContent>
        {state.loading ? (
          <div className="h-8 flex items-center">
            <div className="h-4 w-16 animate-pulse rounded bg-muted" />
          </div>
        ) : state.error ? (
          <p className="text-xs text-destructive">{state.error}</p>
        ) : (
          <div className="flex items-baseline gap-1">
            <span className="text-2xl font-bold">{value}</span>
            {suffix && (
              <span className="text-xs text-muted-foreground">{suffix}</span>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  )

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold tracking-tight">系统监控</h2>
          <p className="text-muted-foreground">
            查看系统运行状态与性能指标
          </p>
        </div>
        <Button
          variant="outline"
          size="sm"
          className="gap-2"
          onClick={loadAll}
        >
          <RefreshCw className="h-4 w-4" />
          刷新
        </Button>
      </div>

      {/* 4 metric cards */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <MetricCard
          title="LLM 调用"
          icon={Activity}
          state={overview}
          value={formatNumber(overview.data?.llm_calls ?? 0)}
          color="text-blue-600 dark:text-blue-400"
          suffix="次"
        />
        <MetricCard
          title="智能体执行"
          icon={Bot}
          state={overview}
          value={formatNumber(overview.data?.agent_executions ?? 0)}
          color="text-purple-600 dark:text-purple-400"
          suffix="次"
        />
        <MetricCard
          title="错误 (24h)"
          icon={AlertTriangle}
          state={overview}
          value={formatNumber(overview.data?.errors_24h ?? 0)}
          color={
            (overview.data?.errors_24h ?? 0) > 0
              ? "text-destructive"
              : "text-green-600 dark:text-green-400"
          }
          suffix="个"
        />
        <MetricCard
          title="数据库状态"
          icon={Database}
          state={overview}
          value={overview.data?.database ?? "-"}
          color="text-emerald-600 dark:text-emerald-400"
        />
      </div>

      {/* LLM Cost Breakdown */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base flex items-center gap-2">
            <DollarSign className="h-4 w-4 text-muted-foreground" />
            LLM 成本明细
          </CardTitle>
        </CardHeader>
        <CardContent>
          {llm.loading ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
            </div>
          ) : llm.error ? (
            <div className="flex items-center gap-2 text-destructive py-4">
              <AlertCircle className="h-4 w-4" />
              <p className="text-sm">{llm.error}</p>
            </div>
          ) : (
            <>
              {/* Summary row */}
              <div className="grid grid-cols-3 gap-4 mb-4">
                <div className="rounded-md bg-muted p-3 text-center">
                  <p className="text-xs text-muted-foreground">总调用</p>
                  <p className="text-lg font-bold">
                    {formatNumber(llm.data?.total_calls ?? 0)}
                  </p>
                </div>
                <div className="rounded-md bg-muted p-3 text-center">
                  <p className="text-xs text-muted-foreground">总 Tokens</p>
                  <p className="text-lg font-bold">
                    {formatNumber(llm.data?.total_tokens ?? 0)}
                  </p>
                </div>
                <div className="rounded-md bg-muted p-3 text-center">
                  <p className="text-xs text-muted-foreground">总成本</p>
                  <p className="text-lg font-bold">
                    {formatCost(llm.data?.total_cost ?? 0)}
                  </p>
                </div>
              </div>

              {/* Table */}
              {llm.data?.per_model && llm.data.per_model.length > 0 ? (
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b text-left">
                        <th className="pb-2 font-medium text-muted-foreground">
                          模型
                        </th>
                        <th className="pb-2 font-medium text-muted-foreground">
                          调用次数
                        </th>
                        <th className="pb-2 font-medium text-muted-foreground">
                          Tokens
                        </th>
                        <th className="pb-2 font-medium text-muted-foreground">
                          成本
                        </th>
                      </tr>
                    </thead>
                    <tbody>
                      {llm.data.per_model.map((m, i) => (
                        <tr
                          key={i}
                          className="border-b last:border-0 hover:bg-muted/50"
                        >
                          <td className="py-2 pr-4 font-medium">{m.model}</td>
                          <td className="py-2 pr-4">
                            {formatNumber(m.calls)}
                          </td>
                          <td className="py-2 pr-4">
                            {formatNumber(m.tokens)}
                          </td>
                          <td className="py-2">{formatCost(m.cost)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <p className="text-sm text-muted-foreground py-4 text-center">
                  暂无数据
                </p>
              )}
            </>
          )}
        </CardContent>
      </Card>

      {/* Agent Performance */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base flex items-center gap-2">
            <Gauge className="h-4 w-4 text-muted-foreground" />
            智能体性能
          </CardTitle>
        </CardHeader>
        <CardContent>
          {agents.loading ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
            </div>
          ) : agents.error ? (
            <div className="flex items-center gap-2 text-destructive py-4">
              <AlertCircle className="h-4 w-4" />
              <p className="text-sm">{agents.error}</p>
            </div>
          ) : (
            <>
              {/* Summary */}
              <div className="grid grid-cols-3 gap-4 mb-4">
                <div className="rounded-md bg-muted p-3 text-center">
                  <p className="text-xs text-muted-foreground">总执行</p>
                  <p className="text-lg font-bold">
                    {formatNumber(agents.data?.total_executions ?? 0)}
                  </p>
                </div>
                <div className="rounded-md bg-muted p-3 text-center">
                  <p className="text-xs text-muted-foreground">失败</p>
                  <p className="text-lg font-bold">
                    {formatNumber(agents.data?.failed ?? 0)}
                  </p>
                </div>
                <div className="rounded-md bg-muted p-3 text-center">
                  <p className="text-xs text-muted-foreground">成功率</p>
                  <p className="text-lg font-bold">
                    {agents.data?.success_rate != null
                      ? `${(agents.data.success_rate * 100).toFixed(1)}%`
                      : "-"}
                  </p>
                </div>
              </div>

              {/* Per-component */}
              {agents.data?.components &&
              Object.keys(agents.data.components).length > 0 ? (
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b text-left">
                        <th className="pb-2 font-medium text-muted-foreground">
                          组件
                        </th>
                        <th className="pb-2 font-medium text-muted-foreground">
                          执行次数
                        </th>
                      </tr>
                    </thead>
                    <tbody>
                      {Object.entries(agents.data.components).map(
                        ([component, count]) => (
                          <tr
                            key={component}
                            className="border-b last:border-0 hover:bg-muted/50"
                          >
                            <td className="py-2 pr-4 font-medium">
                              {component}
                            </td>
                            <td className="py-2">
                              {formatNumber(count)}
                            </td>
                          </tr>
                        )
                      )}
                    </tbody>
                  </table>
                </div>
              ) : (
                <p className="text-sm text-muted-foreground text-center py-4">
                  暂无组件数据
                </p>
              )}
            </>
          )}
        </CardContent>
      </Card>

      {/* Sync Metrics & Error Breakdown */}
      <div className="grid gap-4 lg:grid-cols-2">
        {/* Sync Metrics */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base flex items-center gap-2">
              <RefreshCw className="h-4 w-4 text-muted-foreground" />
              同步指标
            </CardTitle>
          </CardHeader>
          <CardContent>
            {sync.loading ? (
              <div className="flex items-center justify-center py-8">
                <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
              </div>
            ) : sync.error ? (
              <div className="flex items-center gap-2 text-destructive py-4">
                <AlertCircle className="h-4 w-4" />
                <p className="text-sm">{sync.error}</p>
              </div>
            ) : (
              <div className="grid grid-cols-3 gap-4">
                <div className="rounded-md bg-muted p-3 text-center">
                  <p className="text-xs text-muted-foreground">总同步</p>
                  <p className="text-lg font-bold">
                    {formatNumber(sync.data?.total_syncs ?? 0)}
                  </p>
                </div>
                <div className="rounded-md bg-muted p-3 text-center">
                  <p className="text-xs text-muted-foreground">失败</p>
                  <p className="text-lg font-bold">
                    {formatNumber(sync.data?.failed ?? 0)}
                  </p>
                </div>
                <div className="rounded-md bg-muted p-3 text-center">
                  <p className="text-xs text-muted-foreground">成功率</p>
                  <p className="text-lg font-bold">
                    {sync.data?.success_rate != null
                      ? `${(sync.data.success_rate * 100).toFixed(1)}%`
                      : "-"}
                  </p>
                </div>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Error Breakdown */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base flex items-center gap-2">
              <PieChart className="h-4 w-4 text-muted-foreground" />
              错误分布
            </CardTitle>
          </CardHeader>
          <CardContent>
            {errors.loading ? (
              <div className="flex items-center justify-center py-8">
                <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
              </div>
            ) : errors.error ? (
              <div className="flex items-center gap-2 text-destructive py-4">
                <AlertCircle className="h-4 w-4" />
                <p className="text-sm">{errors.error}</p>
              </div>
            ) : errors.data?.per_component &&
              Object.keys(errors.data.per_component).length > 0 ? (
              <div className="space-y-3">
                {Object.entries(errors.data.per_component).map(
                  ([component, count]) => {
                    const total = errors.data?.total_errors ?? 1
                    const pct = Number(((count / total) * 100).toFixed(1))
                    return (
                      <div key={component}>
                        <div className="mb-1 flex items-center justify-between text-sm">
                          <span className="font-medium">{component}</span>
                          <span className="text-muted-foreground">
                            {count} ({pct}%)
                          </span>
                        </div>
                        <div className="h-2 overflow-hidden rounded-full bg-muted">
                          <div
                            className={cn(
                              "h-full rounded-full",
                              count > 0
                                ? "bg-destructive"
                                : "bg-green-500"
                            )}
                            style={{
                              width: `${Math.min(pct, 100)}%`,
                            }}
                          />
                        </div>
                      </div>
                    )
                  }
                )}
              </div>
            ) : (
              <p className="text-sm text-muted-foreground text-center py-4">
                暂无错误数据
              </p>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  )
}