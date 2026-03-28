import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { launchRun } from '../api/client'

const STAGES = ['design', 'develop', 'test', 'docs']

export default function NewRun() {
  const navigate = useNavigate()
  const [description, setDescription] = useState('')
  const [advanced, setAdvanced] = useState(false)
  const [jiraTicket, setJiraTicket] = useState('')
  const [githubIssue, setGithubIssue] = useState('')
  const [issueType, setIssueType] = useState('feature')
  const [selectedStages, setSelectedStages] = useState(new Set(STAGES))
  const [manualApproval, setManualApproval] = useState(false)
  const [dryRun, setDryRun] = useState(false)
  const [qodoEnabled, setQodoEnabled] = useState(true)
  const [qodoThreshold, setQodoThreshold] = useState('high')
  const [maxReviewIterations, setMaxReviewIterations] = useState(3)
  const [qodoCliPath, setQodoCliPath] = useState('')
  const [debug, setDebug] = useState(false)
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
        github_issue: githubIssue.trim() || null,
        issue_type: issueType,
        stages: [...selectedStages],
        manual_approval: manualApproval,
        dry_run: dryRun,
        qodo_enabled: qodoEnabled,
        qodo_threshold: qodoThreshold,
        max_review_iterations: maxReviewIterations,
        qodo_cli_path: qodoCliPath.trim() || null,
        debug: debug,
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
        <h1 className="text-3xl font-bold text-gray-900 mb-1">FlowPilot</h1>
        <p className="text-gray-500">AI-orchestrated feature pipelines — from idea to pull request.</p>
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
                <label className="block text-xs font-medium text-gray-600 mb-1">GitHub Issue (optional)</label>
                <input
                  className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-sky-400"
                  placeholder="SHIP-123 · owner/repo#123 · https://github.com/..."
                  value={githubIssue}
                  onChange={e => setGithubIssue(e.target.value)}
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

            <div>
              <label className="block text-xs font-medium text-gray-600 mb-2">Dry Run</label>
              <div className="flex gap-2">
                {[{ value: false, label: 'Off' }, { value: true, label: 'Dry Run (no API calls)' }].map(opt => (
                  <button key={String(opt.value)} type="button"
                    onClick={() => setDryRun(opt.value)}
                    className={`px-3 py-1 rounded-full text-xs font-medium border transition-colors ${dryRun === opt.value ? 'bg-sky-500 text-white border-sky-500' : 'border-gray-300 text-gray-600 hover:border-sky-400'}`}>
                    {opt.label}
                  </button>
                ))}
              </div>
            </div>

            <div className="border-t border-gray-100 pt-4">
              <label className="block text-xs font-semibold text-gray-700 mb-3">Code Review</label>
              <div className="flex flex-col gap-3">
                <div>
                  <label className="block text-xs font-medium text-gray-600 mb-1">Review</label>
                  <div className="flex gap-2">
                    {[{ value: true, label: 'Enabled' }, { value: false, label: 'Disabled' }].map(opt => (
                      <button key={String(opt.value)} type="button"
                        onClick={() => setQodoEnabled(opt.value)}
                        className={`px-3 py-1 rounded-full text-xs font-medium border transition-colors ${qodoEnabled === opt.value ? 'bg-indigo-500 text-white border-indigo-500' : 'border-gray-300 text-gray-600 hover:border-indigo-400'}`}>
                        {opt.label}
                      </button>
                    ))}
                  </div>
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-600 mb-1">Block on severity</label>
                  <div className="flex gap-2">
                    {['high', 'medium', 'low'].map(t => (
                      <button key={t} type="button"
                        onClick={() => setQodoThreshold(t)}
                        className={`px-3 py-1 rounded-full text-xs font-medium border transition-colors ${qodoThreshold === t ? 'bg-indigo-500 text-white border-indigo-500' : 'border-gray-300 text-gray-600 hover:border-indigo-400'}`}>
                        {t.charAt(0).toUpperCase() + t.slice(1)}
                      </button>
                    ))}
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-xs font-medium text-gray-600 mb-1">Max auto-fix iterations</label>
                    <input type="number" min={1} max={10}
                      className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400"
                      value={maxReviewIterations}
                      onChange={e => setMaxReviewIterations(Number(e.target.value))} />
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-gray-600 mb-1">Qodo CLI path (optional)</label>
                    <input type="text"
                      className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400"
                      placeholder="/usr/local/bin/qodo"
                      value={qodoCliPath}
                      onChange={e => setQodoCliPath(e.target.value)} />
                  </div>
                </div>
              </div>
            </div>

          </div>
        )}

        {/* Debug toggle — always visible */}
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={() => setDebug(v => !v)}
            className={`px-3 py-1 rounded-full text-xs font-medium border transition-colors ${debug ? 'bg-orange-500 text-white border-orange-500' : 'border-gray-300 text-gray-500 hover:border-orange-400'}`}
          >
            {debug ? '🐛 Debug ON' : 'Debug OFF'}
          </button>
          {debug && <span className="text-xs text-orange-600">Verbose logging enabled</span>}
        </div>

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
      <p className="text-xs text-gray-400">
        <a
          href="https://github.com/ipinto-ai-tools/multi-agents-ocp-builds"
          target="_blank"
          rel="noopener noreferrer"
          className="hover:text-gray-600 underline"
        >
          View on GitHub
        </a>
        {' · '}
        Feature SDLC Automation for Shipwright / OpenShift Builds
      </p>
    </div>
  )
}
