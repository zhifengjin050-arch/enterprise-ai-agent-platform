// ─── API Service Layer ───
// All calls go through Vite proxy (/api → http://localhost:8000/api)

const BASE = "/api"

async function fetchJSON<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, {
    headers: { "Content-Type": "application/json", ...init?.headers },
    ...init,
  })
  if (!res.ok) {
    const text = await res.text().catch(() => "")
    throw new Error(`API ${res.status}: ${text.slice(0, 200)}`)
  }
  return res.json()
}

// ─── Health ───

export async function getHealth() {
  return fetchJSON<{ status: string; version: string; service: string; app_name: string; components: Record<string, string> }>(`${BASE}/health`)
}

// ─── Metrics ───

export async function getMetricsOverview() {
  return fetchJSON<{ status: string; database: string; period_hours: number; llm_calls: number; agent_executions: number; errors_24h: number }>(`${BASE}/metrics/overview`)
}

export async function getMetricsAgents() {
  return fetchJSON<{ total_executions: number; failed: number; success_rate: number; components: Record<string, number> }>(`${BASE}/metrics/agents`)
}

export async function getMetricsLLM() {
  return fetchJSON<{ total_calls: number; total_tokens: number; total_cost: number; prompt_tokens: number; completion_tokens: number; per_model: Array<{ model: string; calls: number; tokens: number; cost: number }> }>(`${BASE}/metrics/llm`)
}

export async function getMetricsErrors() {
  return fetchJSON<{ total_errors: number; per_component: Record<string, number> }>(`${BASE}/metrics/errors`)
}

export async function getMetricsSync() {
  return fetchJSON<{ total_syncs: number; failed: number; success_rate: number }>(`${BASE}/metrics/sync`)
}

// ─── Knowledge ───

export async function getKnowledgeStats() {
  return fetchJSON<{ total_documents: number; total_categories: number; total_tags: number; by_type: Record<string, number> }>(`${BASE}/knowledge/stats`)
}

export async function getKnowledgeDocuments(params?: { limit?: number; offset?: number; status?: string }) {
  const qs = new URLSearchParams()
  if (params?.limit) qs.set("limit", String(params.limit))
  if (params?.offset) qs.set("offset", String(params.offset))
  if (params?.status) qs.set("status", params.status)
  const query = qs.toString() ? `?${qs.toString()}` : ""
  return fetchJSON<{ results: any[]; total: number }>(`${BASE}/knowledge/documents${query}`)
}

export async function searchKnowledge(query: string, topN = 5) {
  return fetchJSON<{ query: string; results: any[]; total: number }>(`${BASE}/knowledge/search`, {
    method: "POST",
    body: JSON.stringify({ query, top_n: topN }),
  })
}

// ─── Agents ───

export async function getAgents() {
  return fetchJSON<{ success: boolean; data: any[]; total: number }>(`${BASE}/agents`)
}

export async function executeAgent(agentId: string, task: string) {
  return fetchJSON<{ success: boolean; data: { answer: string; sources: any[]; tool_calls: any[] }; conversation_id: string }>(`${BASE}/agents/${agentId}/execute`, {
    method: "POST",
    body: JSON.stringify({ task }),
  })
}

// ─── Workflows ───

export async function getWorkflows() {
  return fetchJSON<any[]>(`${BASE}/workflows`)
}

export async function getWorkflowRuns(workflowId: string) {
  return fetchJSON<any[]>(`${BASE}/workflows/${workflowId}/runs`)
}

export async function executeWorkflow(workflowId: string) {
  return fetchJSON<any>(`${BASE}/workflows/${workflowId}/execute`, { method: "POST", body: "{}" })
}

export async function cancelWorkflowRun(runId: string) {
  return fetchJSON<any>(`${BASE}/workflows/runs/${runId}/cancel`, { method: "POST" })
}

// ─── Graph ───

export async function searchGraphEntities(query: string) {
  const qs = encodeURIComponent(query)
  return fetchJSON<any[]>(`${BASE}/graph/search?q=${qs}`)
}

export async function getGraphEntity(name: string) {
  return fetchJSON<any>(`${BASE}/graph/entity/${encodeURIComponent(name)}`)
}

export async function getGraphNeighbors(name: string) {
  return fetchJSON<{ entity: any; neighbors: string[] }>(`${BASE}/graph/entity/${encodeURIComponent(name)}/neighbors`)
}