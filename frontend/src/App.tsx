import { Routes, Route } from "react-router-dom"
import Layout from "@/components/layout"
import Dashboard from "@/pages/Dashboard"
import Agents from "@/pages/Agents"
import Knowledge from "@/pages/Knowledge"
import WorkflowsPage from "@/pages/Workflows"
import Monitor from "@/pages/Monitor"

function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route path="/" element={<Dashboard />} />
        <Route path="/agents" element={<Agents />} />
        <Route path="/knowledge" element={<Knowledge />} />
        <Route path="/workflows" element={<WorkflowsPage />} />
        <Route path="/monitor" element={<Monitor />} />
      </Route>
    </Routes>
  )
}

export default App