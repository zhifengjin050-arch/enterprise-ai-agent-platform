import { Routes, Route } from "react-router-dom"
import Layout from "@/components/layout"
import RequireAuth from "@/components/RequireAuth"
import Dashboard from "@/pages/Dashboard"
import Agents from "@/pages/Agents"
import Knowledge from "@/pages/Knowledge"
import WorkflowsPage from "@/pages/Workflows"
import Monitor from "@/pages/Monitor"
import Login from "@/pages/Login"

function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route element={<RequireAuth />}>
        <Route element={<Layout />}>
          <Route path="/" element={<Dashboard />} />
          <Route path="/agents" element={<Agents />} />
          <Route path="/knowledge" element={<Knowledge />} />
          <Route path="/workflows" element={<WorkflowsPage />} />
          <Route path="/monitor" element={<Monitor />} />
        </Route>
      </Route>
    </Routes>
  )
}

export default App
