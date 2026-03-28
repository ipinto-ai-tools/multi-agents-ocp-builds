import { useState, useEffect, useRef } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { getSession, approveSession, pauseSession, streamLogs } from '../api/client'
import StatusBadge from '../components/StatusBadge'
import PipelineProgress from '../components/PipelineProgress'

function deriveStatus(session) {
  const phase = session?.latest_heartbeat?.phase || 'init'
  const currentPhase = session?.latest_heartbeat?.raw_state?.current_phase
  if (phase === 'done' || currentPhase === 'done') return 'completed'
  if (phase === 'error' || currentPhase === 'error') return 'failed'
  if (phase?.includes('waiting') || currentPhase?.includes('waiting')) return 'waiting'
  if (phase === 'init' && !currentPhase) return 'init'
  return 'running'
}

function getLatestState(session) {
  const hbs = session?.heartbeats || []
  return hbs[hbs.length - 1]?.raw_state || {}
}

export default function RunDetails() {
  const { sessionId } = useParams()
  const navigate = useNavigate()
  const [session, setSession] = useState(null)
  const [activeTab, setActiveTab] = useState('summary')
  const [logs, setLogs] = useState([])
  const [copied, setCopied] = useState(false)
  const logsRef = useRef(null)
  const esRef = useRef(null)

  async function loadSession() {
    try {
      const data = await getSession(sessionId)
      setSession(data)
    } catch (e) {
      console.error(e)
    }
  }

  useEffect(() => {
    loadSession()
    const t = setInterval(loadSession, 3000)

    // Start SSE log stream
    esRef.current = streamLogs(
      sessionId,
      (line) => setLogs(prev => [...prev, line]),
      () => setLogs(prev => [...prev, '[connection to log stream lost — refresh to reconnect]'])
    )

    return () => {
      clearInterval(t)
      esRef.current?.close()
    }
  }, [sessionId])

  // Auto-scroll logs
  useEffect(() => {
    if (logsRef.current) {
      logsRef.current.scrollTop = logsRef.current.scrollHeight
    }
  }, [logs])

  if (!session) return <div className="text-gray-400 text-center mt-20">Loading...</div>

  const status = deriveStatus(session)
  const state = getLatestState(session)
  const currentPhase = state.current_phase || 'init'

  const codeFiles = state.code_files || []
  const unitTests = state.unit_tests || {}
  const integrationTests = state.integration_tests || {}
  const e2eTests = state.e2e_tests || {}
  const prSummary = state.pr_summary || ''
  const releaseNotes = state.release_notes || ''
  const testPlan = state.test_plan || ''

  function triggerDownload(url) {
    window.open(url, '_blank')
  }

  const tabs = [
    { key: 'summary',  label: 'Summary' },
    { key: 'code',     label: `Code (${codeFiles.length})` },
    { key: 'tests',    label: `Tests (${Object.keys(unitTests).length + Object.keys(integrationTests).length + Object.keys(e2eTests).length})` },
    { key: 'docs',     label: 'Docs' },
    { key: 'logs',     label: 'Logs' },
  ]

  return (
    <div className="max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex items-start justify-between mb-6">
        <div>
          <button onClick={() => navigate('/runs')} className="text-sm text-gray-400 hover:text-gray-600 mb-2">← Dashboard</button>
          <h1 className="text-xl font-bold text-gray-900">{session.issue_title || sessionId}</h1>
          <div className="flex items-center gap-3 mt-1">
            <StatusBadge status={status} />
            <span className="text-xs text-gray-400">Session: {sessionId}</span>
            {state.jira_ticket_id && (
              <a href={state.jira_ticket_url} target="_blank" rel="noopener noreferrer"
                 className="text-xs text-sky-600 hover:underline">{state.jira_ticket_id}</a>
            )}
          </div>
        </div>
        <div className="flex gap-2">
          {status === 'waiting' && (
            <>
              <button onClick={() => approveSession(sessionId, 'approve').then(loadSession)}
                className="px-4 py-2 bg-green-500 text-white rounded-lg text-sm hover:bg-green-600">
                Approve & Continue
              </button>
              <button onClick={() => approveSession(sessionId, 'reject').then(loadSession)}
                className="px-4 py-2 border border-red-300 text-red-600 rounded-lg text-sm hover:bg-red-50">
                Reject
              </button>
            </>
          )}
          {status === 'running' && (
            <button onClick={() => pauseSession(sessionId).then(loadSession)}
              className="px-4 py-2 border border-gray-300 text-gray-600 rounded-lg text-sm hover:bg-gray-50">
              Pause
            </button>
          )}
          {(currentPhase === 'done') && (
            <a
              href={`/api/sessions/${sessionId}/download/all`}
              download
              className="px-4 py-2 bg-gray-900 text-white rounded-lg text-sm hover:bg-gray-700 flex items-center gap-1"
            >
              ↓ Download All
            </a>
          )}
        </div>
      </div>

      {/* Pipeline progress */}
      <div className="bg-white border border-gray-200 rounded-xl p-4 mb-6 shadow-sm">
        <PipelineProgress currentPhase={currentPhase} />
      </div>

      {/* Tabs */}
      <div className="border-b border-gray-200 mb-6">
        <div className="flex gap-1">
          {tabs.map(tab => (
            <button key={tab.key} onClick={() => setActiveTab(tab.key)}
              className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
                activeTab === tab.key
                  ? 'border-sky-500 text-sky-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700'
              }`}>
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      {/* Tab content */}
      <div className="bg-white rounded-xl border border-gray-200 p-6 shadow-sm">
        {activeTab === 'summary' && (
          <div className="space-y-4">
            <div className="flex justify-end mb-4">
              <button
                onClick={() => triggerDownload(`/api/sessions/${sessionId}/download/design`)}
                disabled={!state.design_analysis}
                className="px-3 py-1.5 text-xs border border-gray-300 rounded-lg hover:bg-gray-50 disabled:opacity-40 disabled:cursor-not-allowed flex items-center gap-1"
              >
                ↓ Download Design
              </button>
            </div>
            <div className="grid grid-cols-3 gap-4 text-center">
              <div className="bg-gray-50 rounded-lg p-4">
                <div className="text-2xl font-bold text-gray-800">{codeFiles.length}</div>
                <div className="text-xs text-gray-500">Code Files</div>
              </div>
              <div className="bg-gray-50 rounded-lg p-4">
                <div className="text-2xl font-bold text-gray-800">
                  {Object.keys(unitTests).length + Object.keys(integrationTests).length + Object.keys(e2eTests).length}
                </div>
                <div className="text-xs text-gray-500">Test Files</div>
              </div>
              <div className="bg-gray-50 rounded-lg p-4">
                <div className="text-2xl font-bold text-gray-800">
                  {(state.risks || []).length}
                </div>
                <div className="text-xs text-gray-500">Risks Identified</div>
              </div>
            </div>
            {state.design_analysis && (
              <div>
                <h3 className="font-semibold text-gray-700 mb-2">Design Analysis</h3>
                <pre className="text-xs text-gray-600 bg-gray-50 p-4 rounded-lg overflow-auto max-h-64 whitespace-pre-wrap">
                  {state.design_analysis.slice(0, 2000)}{state.design_analysis.length > 2000 ? '...' : ''}
                </pre>
              </div>
            )}
            {prSummary && (
              <div>
                <h3 className="font-semibold text-gray-700 mb-2">PR Summary</h3>
                <pre className="text-xs text-gray-600 bg-gray-50 p-4 rounded-lg overflow-auto max-h-48 whitespace-pre-wrap">{prSummary}</pre>
              </div>
            )}
          </div>
        )}

        {activeTab === 'code' && (
          <div>
            <div className="flex justify-end mb-4">
              <button
                onClick={() => triggerDownload(`/api/sessions/${sessionId}/download/code`)}
                disabled={codeFiles.length === 0}
                className="px-3 py-1.5 text-xs border border-gray-300 rounded-lg hover:bg-gray-50 disabled:opacity-40 disabled:cursor-not-allowed flex items-center gap-1"
              >
                ↓ Download code.zip
              </button>
            </div>
            {codeFiles.length === 0 ? (
              <p className="text-gray-400 text-center py-8">No code files generated yet.</p>
            ) : (
              <div className="space-y-4">
                {codeFiles.map((file, i) => (
                  <div key={i} className="border border-gray-200 rounded-lg overflow-hidden">
                    <div className="bg-gray-100 px-4 py-2 text-xs font-mono text-gray-600 border-b border-gray-200">
                      {file.path || `file-${i}`}
                    </div>
                    <pre className="text-xs text-gray-700 p-4 overflow-auto max-h-64 bg-gray-50">
                      {file.content || ''}
                    </pre>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {activeTab === 'tests' && (
          <div className="space-y-6">
            <div className="flex justify-end mb-4">
              <button
                onClick={() => triggerDownload(`/api/sessions/${sessionId}/download/tests`)}
                disabled={Object.keys(unitTests).length + Object.keys(integrationTests).length + Object.keys(e2eTests).length === 0}
                className="px-3 py-1.5 text-xs border border-gray-300 rounded-lg hover:bg-gray-50 disabled:opacity-40 disabled:cursor-not-allowed flex items-center gap-1"
              >
                ↓ Download tests.zip
              </button>
            </div>
            {testPlan && (
              <div>
                <h3 className="font-semibold text-gray-700 mb-2">Test Plan</h3>
                <pre className="text-xs text-gray-600 bg-gray-50 p-4 rounded-lg overflow-auto max-h-48 whitespace-pre-wrap">{testPlan}</pre>
              </div>
            )}
            {[
              { label: 'Unit Tests', files: unitTests },
              { label: 'Integration Tests', files: integrationTests },
              { label: 'E2E Tests', files: e2eTests },
            ].map(({ label, files }) => Object.keys(files).length > 0 && (
              <div key={label}>
                <h3 className="font-semibold text-gray-700 mb-2">{label} ({Object.keys(files).length})</h3>
                {Object.entries(files).map(([path, content]) => (
                  <div key={path} className="border border-gray-200 rounded-lg overflow-hidden mb-3">
                    <div className="bg-gray-100 px-4 py-2 text-xs font-mono text-gray-600 border-b">{path}</div>
                    <pre className="text-xs text-gray-700 p-4 overflow-auto max-h-48 bg-gray-50">{content}</pre>
                  </div>
                ))}
              </div>
            ))}
          </div>
        )}

        {activeTab === 'docs' && (
          <div className="space-y-4">
            <div className="flex justify-end mb-4">
              <button
                onClick={() => triggerDownload(`/api/sessions/${sessionId}/download/docs`)}
                disabled={!prSummary && !releaseNotes}
                className="px-3 py-1.5 text-xs border border-gray-300 rounded-lg hover:bg-gray-50 disabled:opacity-40 disabled:cursor-not-allowed flex items-center gap-1"
              >
                ↓ Download docs.zip
              </button>
            </div>
            {prSummary ? (
              <div>
                <h3 className="font-semibold text-gray-700 mb-2">PR Summary</h3>
                <pre className="text-xs text-gray-600 bg-gray-50 p-4 rounded-lg whitespace-pre-wrap">{prSummary}</pre>
              </div>
            ) : null}
            {releaseNotes ? (
              <div>
                <h3 className="font-semibold text-gray-700 mb-2">Release Notes</h3>
                <pre className="text-xs text-gray-600 bg-gray-50 p-4 rounded-lg whitespace-pre-wrap">{releaseNotes}</pre>
              </div>
            ) : null}
            {!prSummary && !releaseNotes && (
              <p className="text-gray-400 text-center py-8">Docs will appear after the Documentation phase completes.</p>
            )}
          </div>
        )}

        {activeTab === 'logs' && (
          <div>
          <div className="flex items-center gap-2 mb-2 text-xs text-gray-500">
            <span className="font-mono bg-gray-100 px-2 py-1 rounded text-gray-700 select-all">
              /tmp/claude/logs/{sessionId}.log
            </span>
            <button
              onClick={() => {
                navigator.clipboard.writeText(`/tmp/claude/logs/${sessionId}.log`)
                  .then(() => {
                    setCopied(true)
                    setTimeout(() => setCopied(false), 2000)
                  })
                  .catch(() => {})
              }}
              className="px-2 py-1 rounded border border-gray-200 hover:bg-gray-50 text-gray-500"
            >
              {copied ? '✓ Copied' : 'Copy path'}
            </button>
            <span className="text-gray-400">— open with: <code className="font-mono text-gray-600">vim /tmp/claude/logs/{sessionId}.log</code></span>
          </div>
          <div
            ref={logsRef}
            className="bg-gray-900 text-green-400 font-mono text-xs p-4 rounded-lg h-96 overflow-y-auto"
          >
            {logs.length === 0 ? (
              <span className="text-gray-600">Waiting for logs...</span>
            ) : (
              logs.map((line, i) => <div key={i}>{line}</div>)
            )}
          </div>
          </div>
        )}
      </div>
    </div>
  )
}
