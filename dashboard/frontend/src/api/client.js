const BASE = ''  // same origin (proxied in dev, same server in prod)

export async function launchRun(payload) {
  const res = await fetch(`${BASE}/api/runs`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export async function getSessions(includeArchived = false) {
  const res = await fetch(`${BASE}/api/sessions?include_archived=${includeArchived}`)
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export async function getSession(sessionId) {
  const res = await fetch(`${BASE}/api/sessions/${sessionId}`)
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export async function approveSession(sessionId, action = 'approve') {
  const res = await fetch(`${BASE}/api/sessions/${sessionId}/approve?action=${action}`, {
    method: 'POST',
  })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export async function pauseSession(sessionId) {
  const res = await fetch(`${BASE}/api/sessions/${sessionId}/pause`, { method: 'POST' })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export async function resumeSession(sessionId) {
  const res = await fetch(`${BASE}/api/sessions/${sessionId}/resume`, { method: 'POST' })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export async function archiveSession(sessionId) {
  const res = await fetch(`${BASE}/api/sessions/${sessionId}/archive`, { method: 'PATCH' })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export async function deleteSession(sessionId) {
  const res = await fetch(`${BASE}/api/sessions/${sessionId}`, { method: 'DELETE' })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export async function cleanStuckSessions(maxStaleHours = 1) {
  const res = await fetch(`${BASE}/api/sessions/stuck?max_stale_hours=${maxStaleHours}`, { method: 'DELETE' })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export function streamLogs(sessionId, onLine, onError) {
  const es = new EventSource(`${BASE}/api/sessions/${sessionId}/logs`)
  es.onmessage = (e) => {
    try {
      const { line } = JSON.parse(e.data)
      onLine(line)
    } catch (_) {}
  }
  es.onerror = () => {
    if (onError) onError()
  }
  return es  // caller should call es.close() on cleanup
}
