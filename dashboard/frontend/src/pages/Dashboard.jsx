import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { getSessions, approveSession, pauseSession, archiveSession } from '../api/client'
import StatusBadge from '../components/StatusBadge'

const PHASE_LABELS = {
  init:             { label: 'Starting',    color: 'bg-gray-100 text-gray-500' },
  design_complete:  { label: 'Design ✓',    color: 'bg-purple-100 text-purple-700' },
  develop_complete: { label: 'Dev ✓',       color: 'bg-blue-100 text-blue-700' },
  review_complete:  { label: 'Review ✓',    color: 'bg-indigo-100 text-indigo-700' },
  testing_complete: { label: 'Tests ✓',     color: 'bg-teal-100 text-teal-700' },
  done:             { label: 'Done ✓',      color: 'bg-green-100 text-green-700' },
  error:            { label: 'Error',       color: 'bg-red-100 text-red-600' },
}

function PhaseChip({ phase }) {
  const { label, color } = PHASE_LABELS[phase] || { label: phase || 'Init', color: 'bg-gray-100 text-gray-500' }
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${color}`}>
      {label}
    </span>
  )
}

function deriveStatus(session) {
  const phase = session.latest_heartbeat?.phase || session.status || 'init'
  const currentPhase = session.latest_heartbeat?.raw_state?.current_phase
  if (phase === 'done' || currentPhase === 'done') return 'completed'
  if (phase === 'error' || currentPhase === 'error') return 'failed'
  if (phase?.includes('waiting') || currentPhase?.includes('waiting')) return 'waiting'
  if (phase === 'init' && !currentPhase) return 'init'
  return 'running'
}

function derivePhase(session) {
  return session.latest_heartbeat?.raw_state?.current_phase || 'init'
}

export default function Dashboard() {
  const navigate = useNavigate()
  const [sessions, setSessions] = useState([])
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState('all')
  const [showArchived, setShowArchived] = useState(false)

  async function load() {
    try {
      const data = await getSessions(showArchived)
      setSessions(data)
    } catch (e) {
      console.error(e)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
    const t = setInterval(load, 3000)
    return () => clearInterval(t)
  }, [showArchived])

  const counts = sessions.reduce((acc, s) => {
    const st = deriveStatus(s)
    acc[st] = (acc[st] || 0) + 1
    return acc
  }, {})

  const filtered = filter === 'all' ? sessions : sessions.filter(s => deriveStatus(s) === filter)

  if (loading) return <div className="text-gray-400 text-center mt-20">Loading...</div>

  return (
    <div className="max-w-6xl mx-auto">
      {/* Summary bar */}
      <div className="grid grid-cols-4 gap-4 mb-6">
        {[
          { key: 'running',   label: 'Running',   color: 'border-blue-400 text-blue-700' },
          { key: 'waiting',   label: 'Waiting',   color: 'border-yellow-400 text-yellow-700' },
          { key: 'failed',    label: 'Failed',    color: 'border-red-400 text-red-700' },
          { key: 'completed', label: 'Completed', color: 'border-green-400 text-green-700' },
        ].map(({ key, label, color }) => (
          <button
            key={key}
            onClick={() => setFilter(filter === key ? 'all' : key)}
            className={`bg-white border rounded-xl p-4 text-left shadow-sm hover:shadow transition-shadow ${filter === key ? color + ' border-2' : 'border-gray-200'}`}
          >
            <div className="text-2xl font-bold">{counts[key] || 0}</div>
            <div className="text-sm text-gray-500">{label}</div>
          </button>
        ))}
      </div>

      <div className="flex justify-end mb-2">
        <button
          onClick={() => setShowArchived(v => !v)}
          className="text-xs text-gray-400 hover:text-gray-600 underline"
        >
          {showArchived ? 'Hide archived' : 'Show archived'}
        </button>
      </div>

      {/* Table */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
        <div className="px-5 py-3 border-b border-gray-100 flex items-center justify-between">
          <h2 className="font-semibold text-gray-800">Feature Runs</h2>
          <button
            onClick={() => navigate('/')}
            className="text-sm bg-sky-600 text-white px-4 py-1.5 rounded-full hover:bg-sky-700 transition-colors"
          >
            + New Run
          </button>
        </div>

        {filtered.length === 0 ? (
          <div className="text-center py-16 text-gray-400">
            No runs yet. <button className="text-sky-600 underline" onClick={() => navigate('/')}>Start one</button>
          </div>
        ) : (
          <div className="overflow-x-auto overflow-y-auto max-h-[60vh]">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs text-gray-400 uppercase border-b border-gray-100">
                <th className="px-5 py-3">Feature</th>
                <th className="px-5 py-3">Jira</th>
                <th className="px-5 py-3">Pipeline</th>
                <th className="px-5 py-3">Status</th>
                <th className="px-5 py-3">Updated</th>
                <th className="px-5 py-3">Actions</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map(session => {
                const status = deriveStatus(session)
                const phase = derivePhase(session)
                return (
                  <tr key={session.id} className="border-b border-gray-50 hover:bg-gray-50 cursor-pointer"
                      onClick={() => navigate(`/runs/${session.id}`)}>
                    <td className="px-5 py-3 font-medium text-gray-800 max-w-xs truncate">
                      {session.issue_title || session.id}
                    </td>
                    <td className="px-5 py-3 text-gray-500">
                      {session.jira_ticket_id
                        ? <a href={session.jira_ticket_url} target="_blank" rel="noopener noreferrer"
                             className="text-sky-600 hover:underline" onClick={e => e.stopPropagation()}>
                            {session.jira_ticket_id}
                          </a>
                        : <span className="text-gray-300">—</span>}
                    </td>
                    <td className="px-5 py-3">
                      <PhaseChip phase={phase} />
                    </td>
                    <td className="px-5 py-3">
                      <StatusBadge status={status} />
                    </td>
                    <td className="px-5 py-3 text-gray-400 text-xs">
                      {session.updated_at ? new Date(session.updated_at + 'Z').toLocaleString() : '—'}
                    </td>
                    <td className="px-5 py-3" onClick={e => e.stopPropagation()}>
                      <div className="flex gap-1">
                        {status === 'waiting' && (
                          <button className="px-2 py-1 text-xs bg-green-500 text-white rounded hover:bg-green-600"
                            onClick={() => approveSession(session.id).then(load)}>
                            Approve
                          </button>
                        )}
                        {status === 'running' && (
                          <button className="px-2 py-1 text-xs border border-gray-300 text-gray-600 rounded hover:bg-gray-50"
                            onClick={() => pauseSession(session.id).then(load)}>
                            Pause
                          </button>
                        )}
                        {(status === 'completed' || status === 'failed') && (
                          <button className="px-2 py-1 text-xs border border-gray-300 text-gray-500 rounded hover:bg-gray-50"
                            onClick={() => archiveSession(session.id).then(load)}>
                            Archive
                          </button>
                        )}
                        <button className="px-2 py-1 text-xs bg-sky-50 text-sky-600 border border-sky-200 rounded hover:bg-sky-100 font-medium"
                          onClick={() => navigate(`/runs/${session.id}`)}>
                          Open →
                        </button>
                      </div>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
          </div>
        )}
      </div>
    </div>
  )
}
