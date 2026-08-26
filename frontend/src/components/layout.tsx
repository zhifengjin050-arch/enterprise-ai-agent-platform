import { useState, useEffect } from "react"
import { Link, useLocation, Outlet } from "react-router-dom"
import { cn } from "@/lib/utils"
import {
  LayoutDashboard,
  Bot,
  Library,
  Workflow,
  BarChart3,
  Menu,
  X,
  ChevronRight,
  LogOut,
} from "lucide-react"
import { Button } from "@/components/ui/button"
import { useAuth } from "@/lib/auth-context"

interface NavItem {
  label: string
  href: string
  icon: React.ElementType
}

const navItems: NavItem[] = [
  { label: "仪表盘", href: "/", icon: LayoutDashboard },
  { label: "AI 智能体", href: "/agents", icon: Bot },
  { label: "知识库", href: "/knowledge", icon: Library },
  { label: "工作流", href: "/workflows", icon: Workflow },
  { label: "系统监控", href: "/monitor", icon: BarChart3 },
]

function CurrentTime() {
  const [time, setTime] = useState(new Date())

  useEffect(() => {
    const timer = setInterval(() => setTime(new Date()), 1000)
    return () => clearInterval(timer)
  }, [])

  return (
    <span className="text-sm text-muted-foreground">
      {time.toLocaleString("zh-CN", {
        year: "numeric",
        month: "2-digit",
        day: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
      })}
    </span>
  )
}

export default function Layout() {
  const location = useLocation()
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const { user, logout } = useAuth()

  return (
    <div className="flex h-screen overflow-hidden bg-background">
      {/* Mobile overlay */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/50 lg:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Sidebar */}
      <aside
        className={cn(
          "fixed inset-y-0 left-0 z-50 flex w-64 flex-col border-r border-sidebar-border bg-sidebar transition-transform duration-300 lg:static lg:translate-x-0",
          sidebarOpen ? "translate-x-0" : "-translate-x-full"
        )}
      >
        {/* Sidebar header */}
        <div className="flex h-14 items-center gap-2 border-b border-sidebar-border px-6">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-sidebar-primary">
            <Bot className="h-5 w-5 text-sidebar-primary-foreground" />
          </div>
          <span className="text-lg font-bold text-sidebar-foreground">
            DevOps RAG
          </span>
        </div>

        {/* Navigation */}
        <nav className="flex-1 space-y-1 p-4">
          {navItems.map((item) => {
            const isActive =
              item.href === "/"
                ? location.pathname === "/"
                : location.pathname.startsWith(item.href)
            const Icon = item.icon
            return (
              <Link
                key={item.href}
                to={item.href}
                onClick={() => setSidebarOpen(false)}
                className={cn(
                  "flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors",
                  isActive
                    ? "bg-sidebar-accent text-sidebar-accent-foreground"
                    : "text-sidebar-foreground/70 hover:bg-sidebar-accent hover:text-sidebar-accent-foreground"
                )}
              >
                <Icon className="h-5 w-5 flex-shrink-0" />
                <span>{item.label}</span>
                {isActive && (
                  <ChevronRight className="ml-auto h-4 w-4 text-sidebar-primary" />
                )}
              </Link>
            )
          })}
        </nav>

        {/* Sidebar footer */}
        <div className="border-t border-sidebar-border p-4">
          <p className="text-xs text-sidebar-foreground/50">
            Enterprise AI Agent Platform
          </p>
          <p className="text-xs text-sidebar-foreground/50">v1.0.0</p>
        </div>
      </aside>

      {/* Main content area */}
      <div className="flex flex-1 flex-col overflow-hidden">
        {/* Top header */}
        <header className="flex h-14 items-center gap-4 border-b bg-background px-6">
          <Button
            variant="ghost"
            size="icon"
            className="lg:hidden"
            onClick={() => setSidebarOpen(true)}
          >
            {sidebarOpen ? (
              <X className="h-5 w-5" />
            ) : (
              <Menu className="h-5 w-5" />
            )}
          </Button>

          <h1 className="text-base font-semibold">
            Enterprise AI Agent Platform
          </h1>

          <div className="ml-auto flex items-center gap-4">
            {user?.username && (
              <span className="hidden text-sm text-muted-foreground sm:inline">
                {user.username}
              </span>
            )}
            <CurrentTime />
            <Button variant="ghost" size="sm" className="gap-1" onClick={logout}>
              <LogOut className="h-4 w-4" />
              退出
            </Button>
          </div>
        </header>

        {/* Page content */}
        <main className="flex-1 overflow-y-auto p-6">
          <Outlet />
        </main>
      </div>
    </div>
  )
}