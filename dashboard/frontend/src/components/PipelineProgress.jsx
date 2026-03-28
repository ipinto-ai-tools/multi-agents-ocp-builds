const PHASES = [
  { key: 'design',       label: 'Design' },
  { key: 'develop',      label: 'Develop' },
  { key: 'code_review',  label: 'Review' },
  { key: 'testing',      label: 'Test' },
  { key: 'docs',         label: 'Docs' },
]

const PHASE_ORDER = ['init', 'design_complete', 'develop_complete', 'review_complete', 'testing_complete', 'done', 'error']

function phaseStatus(phaseKey, currentPhase) {
  const phaseMap = {
    design:      'design_complete',
    develop:     'develop_complete',
    code_review: 'review_complete',
    testing:     'testing_complete',
    docs:        'done',
  }
  const completedAt = phaseMap[phaseKey]
  const currentIdx = PHASE_ORDER.indexOf(currentPhase)
  const completedIdx = PHASE_ORDER.indexOf(completedAt)

  if (currentPhase === 'error') return 'failed'
  if (currentIdx >= completedIdx) return 'done'
  // Is this the active phase?
  const prevPhase = PHASE_ORDER[completedIdx - 1]
  if (PHASE_ORDER.indexOf(currentPhase) === PHASE_ORDER.indexOf(prevPhase)) return 'active'
  return 'pending'
}

export default function PipelineProgress({ currentPhase }) {
  return (
    <div className="flex items-center gap-1">
      {PHASES.map((phase, i) => {
        const status = phaseStatus(phase.key, currentPhase)
        const colors = {
          done:    'bg-green-500 text-white',
          active:  'bg-blue-500 text-white animate-pulse',
          failed:  'bg-red-500 text-white',
          pending: 'bg-gray-200 text-gray-500',
        }
        return (
          <div key={phase.key} className="flex items-center">
            <div className={`px-2 py-1 rounded text-xs font-medium ${colors[status] || colors.pending}`}>
              {status === 'done' ? '✓ ' : ''}{phase.label}
            </div>
            {i < PHASES.length - 1 && (
              <span className="text-gray-300 mx-1">→</span>
            )}
          </div>
        )
      })}
    </div>
  )
}
