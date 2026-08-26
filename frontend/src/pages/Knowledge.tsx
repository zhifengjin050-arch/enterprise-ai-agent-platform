import { useState, useEffect } from "react"
import { getKnowledgeStats, getKnowledgeDocuments, searchKnowledge } from "@/lib/api"
import type { KnowledgeStats, KnowledgeDocument, SearchResult } from "@/types/api"
import { formatDate, formatNumber } from "@/lib/utils"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  FileText,
  FolderTree,
  Tags,
  Search,
  Loader2,
  AlertCircle,
  File,
  BookOpen,
  ChevronDown,
  ChevronUp,
} from "lucide-react"

export default function Knowledge() {
  // Stats
  const [stats, setStats] = useState<KnowledgeStats | null>(null)
  const [statsLoading, setStatsLoading] = useState(true)
  const [statsError, setStatsError] = useState<string | null>(null)

  // Documents
  const [documents, setDocuments] = useState<KnowledgeDocument[]>([])
  const [docsLoading, setDocsLoading] = useState(true)
  const [docsError, setDocsError] = useState<string | null>(null)

  // Search
  const [searchQuery, setSearchQuery] = useState("")
  const [searchResults, setSearchResults] = useState<SearchResult | null>(null)
  const [searchLoading, setSearchLoading] = useState(false)
  const [searchError, setSearchError] = useState<string | null>(null)
  const [expandedDoc, setExpandedDoc] = useState<string | null>(null)

  useEffect(() => {
    getKnowledgeStats()
      .then(setStats)
      .catch((e) => setStatsError(e.message))
      .finally(() => setStatsLoading(false))

    getKnowledgeDocuments({ limit: 50 })
      .then((res) => setDocuments(res.results))
      .catch((e) => setDocsError(e.message))
      .finally(() => setDocsLoading(false))
  }, [])

  async function handleSearch() {
    if (!searchQuery.trim()) return
    setSearchLoading(true)
    setSearchError(null)
    try {
      const res = await searchKnowledge(searchQuery, 10)
      setSearchResults(res)
    } catch (e: any) {
      setSearchError(e.message)
    } finally {
      setSearchLoading(false)
    }
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === "Enter") handleSearch()
  }

  const statusBadge = (status: string) => {
    switch (status) {
      case "completed":
      case "processed":
        return <Badge variant="success">{status}</Badge>
      case "processing":
      case "pending":
        return <Badge variant="warning">{status}</Badge>
      case "failed":
        return <Badge variant="destructive">{status}</Badge>
      default:
        return <Badge variant="secondary">{status}</Badge>
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold tracking-tight">知识库</h2>
        <p className="text-muted-foreground">
          知识智能管理与语义搜索
        </p>
      </div>

      {/* Stats cards */}
      <div className="grid gap-4 sm:grid-cols-3">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">文档总数</CardTitle>
            <FileText className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            {statsLoading ? (
              <div className="h-8 animate-pulse rounded bg-muted" />
            ) : statsError ? (
              <p className="text-sm text-destructive">{statsError}</p>
            ) : (
              <div className="text-2xl font-bold">
                {formatNumber(stats?.total_documents ?? 0)}
              </div>
            )}
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">分类</CardTitle>
            <FolderTree className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            {statsLoading ? (
              <div className="h-8 animate-pulse rounded bg-muted" />
            ) : statsError ? (
              <p className="text-sm text-destructive">{statsError}</p>
            ) : (
              <div className="text-2xl font-bold">
                {formatNumber(stats?.total_categories ?? 0)}
              </div>
            )}
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">标签</CardTitle>
            <Tags className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            {statsLoading ? (
              <div className="h-8 animate-pulse rounded bg-muted" />
            ) : statsError ? (
              <p className="text-sm text-destructive">{statsError}</p>
            ) : (
              <div className="text-2xl font-bold">
                {formatNumber(stats?.total_tags ?? 0)}
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Search box */}
      <Card>
        <CardContent className="p-4">
          <div className="flex gap-2">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <input
                className="flex h-10 w-full rounded-md border border-input bg-background pl-10 pr-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
                placeholder="搜索知识库..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                onKeyDown={handleKeyDown}
              />
            </div>
            <Button onClick={handleSearch} disabled={searchLoading || !searchQuery.trim()}>
              {searchLoading ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Search className="h-4 w-4" />
              )}
              <span className="ml-2">搜索</span>
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Search results */}
      {searchResults && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">
              搜索结果 ({searchResults.total})
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {searchResults.results.length === 0 && (
              <p className="text-sm text-muted-foreground">未找到相关结果</p>
            )}
            {searchResults.results.map((result) => {
              const docId = result.id || result.document_id || result.title || "unknown"
              return (
              <div
                key={docId}
                className="rounded-md border p-3 transition-colors hover:bg-muted/50 cursor-pointer"
                onClick={() =>
                  setExpandedDoc(expandedDoc === docId ? null : docId)
                }
              >
                <div className="flex items-start justify-between">
                  <div className="flex items-center gap-2 min-w-0 flex-1">
                    <File className="h-4 w-4 flex-shrink-0 text-muted-foreground" />
                    <span className="font-medium truncate">{result.title}</span>
                  </div>
                  <div className="flex items-center gap-2 shrink-0 ml-2">
                    <Badge variant="secondary" className="text-xs">
                      相关度 {(result.score * 100).toFixed(0)}%
                    </Badge>
                    {expandedDoc === docId ? (
                      <ChevronUp className="h-4 w-4 text-muted-foreground" />
                    ) : (
                      <ChevronDown className="h-4 w-4 text-muted-foreground" />
                    )}
                  </div>
                </div>
                {expandedDoc === docId && (
                  <div className="mt-3 space-y-2">
                    <p className="text-sm text-muted-foreground whitespace-pre-wrap line-clamp-6">
                      {result.content}
                    </p>
                    {result.metadata && (
                      <details className="text-xs text-muted-foreground">
                        <summary className="cursor-pointer">元数据</summary>
                        <pre className="mt-1 rounded bg-muted p-2 overflow-x-auto">
                          {JSON.stringify(result.metadata, null, 2)}
                        </pre>
                      </details>
                    )}
                  </div>
                )}
              </div>
              )
            })}
          </CardContent>
        </Card>
      )}

      {/* Search error */}
      {searchError && (
        <div className="flex items-center gap-2 rounded-md bg-destructive/10 p-3 text-sm text-destructive">
          <AlertCircle className="h-4 w-4 flex-shrink-0" />
          <span>搜索失败: {searchError}</span>
        </div>
      )}

      {/* Document list */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">文档列表</CardTitle>
        </CardHeader>
        <CardContent>
          {docsLoading ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
            </div>
          ) : docsError ? (
            <div className="flex items-center gap-2 text-destructive">
              <AlertCircle className="h-4 w-4" />
              <p className="text-sm">{docsError}</p>
            </div>
          ) : documents.length === 0 ? (
            <div className="flex flex-col items-center gap-4 py-8">
              <BookOpen className="h-12 w-12 text-muted-foreground/40" />
              <p className="text-sm text-muted-foreground">暂无文档</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b text-left">
                    <th className="pb-3 font-medium text-muted-foreground">标题</th>
                    <th className="pb-3 font-medium text-muted-foreground">状态</th>
                    <th className="pb-3 font-medium text-muted-foreground hidden md:table-cell">来源</th>
                    <th className="pb-3 font-medium text-muted-foreground hidden md:table-cell">作者</th>
                    <th className="pb-3 font-medium text-muted-foreground hidden lg:table-cell">日期</th>
                  </tr>
                </thead>
                <tbody>
                  {documents.map((doc) => (
                    <tr
                      key={doc.id}
                      className="border-b last:border-0 hover:bg-muted/50 transition-colors"
                    >
                      <td className="py-3 pr-4">
                        <div className="flex items-center gap-2">
                          <FileText className="h-4 w-4 flex-shrink-0 text-muted-foreground" />
                          <span className="font-medium truncate max-w-[200px] lg:max-w-[300px]">
                            {doc.title}
                          </span>
                        </div>
                      </td>
                      <td className="py-3 pr-4">
                        {statusBadge(doc.status)}
                      </td>
                      <td className="py-3 pr-4 text-muted-foreground hidden md:table-cell">
                        {doc.source || "-"}
                      </td>
                      <td className="py-3 pr-4 text-muted-foreground hidden md:table-cell">
                        {doc.author || "-"}
                      </td>
                      <td className="py-3 text-muted-foreground hidden lg:table-cell whitespace-nowrap">
                        {formatDate(doc.created_at)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}