import { Routes, Route, Navigate } from 'react-router-dom'
import Layout from './components/Layout'
import NewRun from './pages/NewRun'
import Dashboard from './pages/Dashboard'
import RunDetails from './pages/RunDetails'

export default function App() {
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<NewRun />} />
        <Route path="/runs" element={<Dashboard />} />
        <Route path="/runs/:sessionId" element={<RunDetails />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Layout>
  )
}
