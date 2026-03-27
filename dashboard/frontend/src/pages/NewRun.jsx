import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { launchRun } from '../api/client'

const STAGES = ['design', 'develop', 'test', 'docs']

export default function NewRun() {
  const navigate = useNavigate()
  const [description, setDescription] = useState('')
  const [advanced, setAdvanced] = useState(false)
  const [jiraTicket, setJiraTicket] = useState('')
  const [repoPath, setRepoPath] = useState('')
  const [issueType, setIssueType] = useState('feature')
  const [selectedStages, setSelectedStages] = useState(new Set(STAGES))
  const [manualApproval, setManualApproval] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  function toggleStage(stage) {
    setSelectedStages(prev => {
      const next = new Set(prev)
      if (next.has(stage)) next.delete(stage)
      else next.add(stage)
      return next
    })
  }

  async function handleSubmit(e) {
    e.preventDefault()
    if (!description.trim() && !jiraTicket.trim()) {
      setError('Enter a description or Jira ticket ID')
      return
    }
    setLoading(true)
    setError(null)
    try {
      const payload = {
        title: description.trim().split('\n')[0].slice(0, 120) || null,
        description: description.trim() || null,
        jira_ticket: jiraTicket.trim() || null,
        repo_path: repoPath.trim() || null,
        issue_type: issueType,
        stages: [...selectedStages],
        manual_approval: manualApproval,
      }
      const { session_id } = await launchRun(payload)
      navigate(`/runs/${session_id}`)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex flex-col items-center justify-center min-h-[70vh] gap-6">
      <div className="text-center">
        <h1 className="text-3xl font-bold text-gray-900 mb-1">AI Agent Control Plane</h1>
        <p className="text-gray-500">Feature SDLC automation — Design → Develop → Test → Docs</p>
      </div>

      <form onSubmit={handleSubmit} className="w-full max-w-2xl flex flex-col gap-4">
        <textarea
          className="w-full rounded-xl border border-gray-200 shadow-sm px-5 py-4 text-base resize-none focus:outline-none focus:ring-2 focus:ring-sky-500 bg-white"
          rows={4}
          placeholder="Describe the feature you want to build..."
          value={description}
          onChange={e => setDescription(e.target.value)}
        />

        {error && <p className="text-red-600 text-sm">{error}</p>}

        {/* Advanced options toggle */}
        <button
          type="button"
          className="self-start text-sm text-sky-600 hover:underline"
          onClick={() => setAdvanced(v => !v)}
        >
          {advanced ? '▲ Hide' : '▼ Advanced Options'}
        </button>

        {advanced && (
          <div className="bg-white border border-gray-200 rounded-xl p-5 flex flex-col gap-4 shadow-sm">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">Jira Ticket (optional)</label>
                <input
                  className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-sky-400"
                  placeholder="BUILD-123"
                  value={jiraTicket}
                  onChange={e => setJiraTicket(e.target.value)}
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">Repository Path (optional)</label>
                <input
                  className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-sky-400"
                  placeholder="/home/user/git/shipwright-build"
                  value={repoPath}
                  onChange={e => setRepoPath(e.target.value)}
                />
              </div>
            </div>

            <div>
              <label className="block text-xs font-medium text-gray-600 mb-2">Issue Type</label>
              <div className="flex gap-2">
                {['feature', 'bug', 'refactor'].map(t => (
                  <button
                    key={t}
                    type="button"
                    onClick={() => setIssueType(t)}
                    className={`px-3 py-1 rounded-full text-xs font-medium border transition-colors ${issueType === t ? 'bg-sky-500 text-white border-sky-500' : 'border-gray-300 text-gray-600 hover:border-sky-400'}`}
                  >
                    {t}
                  </button>
                ))}
              </div>
            </div>

            <div>
              <label className="block text-xs font-medium text-gray-600 mb-2">Stages</label>
              <div className="flex gap-2">
                {STAGES.map(s => (
                  <button
                    key={s}
                    type="button"
                    onClick={() => toggleStage(s)}
                    className={`px-3 py-1 rounded-full text-xs font-medium border transition-colors ${selectedStages.has(s) ? 'bg-gray-900 text-white border-gray-900' : 'border-gray-300 text-gray-500'}`}
                  >
                    {s.charAt(0).toUpperCase() + s.slice(1)}
                  </button>
                ))}
              </div>
            </div>

            <div>
              <label className="block text-xs font-medium text-gray-600 mb-2">Approval Mode</label>
              <div className="flex gap-3">
                {[
                  { value: false, label: 'Auto' },
                  { value: true,  label: 'Require Approval' },
                ].map(opt => (
                  <button
                    key={String(opt.value)}
                    type="button"
                    onClick={() => setManualApproval(opt.value)}
                    className={`px-3 py-1 rounded-full text-xs font-medium border transition-colors ${manualApproval === opt.value ? 'bg-sky-500 text-white border-sky-500' : 'border-gray-300 text-gray-600 hover:border-sky-400'}`}
                  >
                    {opt.label}
                  </button>
                ))}
              </div>
            </div>
          </div>
        )}

        <div className="flex gap-3 justify-center">
          <button
            type="submit"
            disabled={loading}
            className="px-8 py-3 bg-sky-600 text-white rounded-full font-semibold hover:bg-sky-700 disabled:opacity-50 transition-colors shadow"
          >
            {loading ? 'Launching...' : 'Run Feature'}
          </button>
          <button
            type="button"
            onClick={() => navigate('/runs')}
            className="px-6 py-3 border border-gray-300 rounded-full text-sm text-gray-600 hover:border-gray-400 transition-colors"
          >
            View Dashboard
          </button>
        </div>
      </form>
    </div>
  )
}
