import { Navigate, Outlet } from "react-router-dom"
import { Loader2 } from "lucide-react"
import { useAuth } from "@/lib/auth-context"

export default function RequireAuth() {
  const { user, ready } = useAuth()

  if (!ready) {
    return (
      <div className="flex h-screen items-center justify-center text-muted-foreground">
        <Loader2 className="mr-2 h-5 w-5 animate-spin" />
        加载会话...
      </div>
    )
  }

  if (!user) {
    return <Navigate to="/login" replace />
  }

  return <Outlet />
}
