const STATUS_STYLES = {
  running:   'bg-blue-100 text-blue-700',
  waiting:   'bg-yellow-100 text-yellow-700',
  failed:    'bg-red-100 text-red-700',
  completed: 'bg-green-100 text-green-700',
  done:      'bg-green-100 text-green-700',
  active:    'bg-blue-100 text-blue-700',
  error:     'bg-red-100 text-red-700',
  init:      'bg-gray-100 text-gray-600',
}

export default function StatusBadge({ status }) {
  const label = status || 'unknown'
  const style = STATUS_STYLES[label] || 'bg-gray-100 text-gray-600'
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${style}`}>
      {label}
    </span>
  )
}
