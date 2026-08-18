// ─── Health ───

export interface HealthResponse {
  status: string
  version: string
  service: string
  app_name: string
  components: Record<string, string>
}

// ─── Metrics ───

export interface MetricsOverview {
  status: string
  database: string
  period_hours: number
  llm_calls: number
  agent_executions: number
  errors_24h: number
  tenant_id?: string
}

export interface MetricsAgents {
  total_executions: number
  failed: number
  success_rate: number
  components: Record<string, number>
}

export interface MetricsLLM {
  total_calls: number
  total_tokens: number
  total_cost: number
  prompt_tokens: number
  completion_tokens: number
  per_model: Array<{
    model: string
    calls: number
    tokens: number
    cost: number
  }>
}

// ─── Knowledge / Documents ───

export interface KnowledgeDocument {
  id: string
  title: string
  content: string
  format: string
  doc_type: string
  status: string
  source: string
  version: number
  author: string | null
  tags: string[]
  created_at: string
  updated_at: string
}

export interface DocumentListResponse {
  results: KnowledgeDocument[]
  total: number
  limit: number
  offset: number
}

export interface KnowledgeStats {
  total_documents: number
  total_categories: number
  total_tags: number
  by_type: Record<string, number>
}

export interface SearchResult {
  query: string
  results: Array<{
    id: string
    title: string
    content: string
    score: number
    metadata?: Record<string, unknown>
  }>
  total: number
}

// ─── Agents ───

export interface Agent {
  id: string
  tenant_id: string
  name: string
  agent_type: string
  enabled: boolean
  config_json: Record<string, unknown>
  created_at: string
}

export interface AgentListResponse {
  success: boolean
  data: Agent[]
  total: number
}

export interface AgentExecuteResponse {
  success: boolean
  data: {
    success?: boolean
    answer: string
    sources: Array<{
      id: string
      title: string
      content: string
      score: number
    }>
    tool_calls: Array<{
      tool: string
      input: Record<string, unknown>
      output: Record<string, unknown>
    }>
    metadata?: Record<string, unknown>
  }
  conversation_id: string
  task_id?: string
}

// ─── Workflows ───

export type WorkflowStatus =
  | "CREATED" | "RUNNING" | "WAITING" | "PAUSED" | "COMPLETED" | "FAILED"

export interface WorkflowDefinition {
  id: string
  name: string
  description: string
  version: number
  status: WorkflowStatus
  trigger_type: string
  tags: string[]
  tenant_id: string
  created_at: string
  updated_at: string
  node_count: number
}

export interface WorkflowRun {
  id: string
  workflow_id: string
  workflow_name: string
  status: WorkflowStatus
  trigger_type: string
  current_node: string | null
  error: string | null
  started_at: string
  completed_at: string | null
  duration_ms: number | null
  tenant_id: string
  created_at: string
}

export interface WorkflowEvent {
  id: string
  workflow_id: string
  run_id: string
  node_name: string | null
  event_type: string
  event_data: Record<string, unknown> | null
  severity: string
  created_at: string
}

export interface Approval {
  id: string
  workflow_id: string
  run_id: string
  node_name: string
  approvers: string[]
  message: string
  status: "PENDING" | "APPROVED" | "REJECTED" | "TIMEOUT"
  timeout_minutes: number
  comment: string | null
  decided_by: string | null
  created_at: string
  decided_at: string | null
}

// ─── Graph ───

export interface GraphEntity {
  id: string
  name: string
  entity_type: string
  description: string
  created_at: string
  updated_at: string
  relations?: Array<{
    source: string
    target: string
    type: string
    confidence: number
  }>
}

export interface GraphNeighborsResponse {
  entity: GraphEntity
  neighbors: string[]
}

export interface GraphPathResponse {
  found: boolean
  path: string[]
  source_name: string
  target_name: string
}

// ─── Sync ───

export interface SyncMetrics {
  total_syncs: number
  failed: number
  success_rate: number
}

// ─── Errors ───

export interface ErrorMetrics {
  total_errors: number
  per_component: Record<string, number>
}