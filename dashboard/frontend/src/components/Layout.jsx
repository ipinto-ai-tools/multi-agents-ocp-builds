import { Link, useLocation } from 'react-router-dom'

export default function Layout({ children }) {
  const loc = useLocation()
  return (
    <div className="min-h-screen flex flex-col">
      <header className="bg-gray-900 text-white px-6 py-3 flex items-center justify-between shadow">
        <div className="flex items-center gap-6">
          <Link to="/" className="font-bold text-lg tracking-tight">
            AI Agent Control Plane
          </Link>
          <nav className="flex gap-4 text-sm">
            <Link
              to="/"
              className={`hover:text-sky-400 transition-colors ${loc.pathname === '/' ? 'text-sky-400' : 'text-gray-300'}`}
            >
              New Run
            </Link>
            <Link
              to="/runs"
              className={`hover:text-sky-400 transition-colors ${loc.pathname.startsWith('/runs') ? 'text-sky-400' : 'text-gray-300'}`}
            >
              Dashboard
            </Link>
            <a
              href="https://github.com/ipinto-ai-tools/multi-agents-ocp-builds/blob/feature/initial-setup/docs/user-guide/01-getting-started/quick-start.md"
              target="_blank"
              rel="noopener noreferrer"
              className="hover:text-sky-400 transition-colors text-gray-300"
            >
              Help
            </a>
          </nav>
        </div>
        <span className="text-xs text-gray-400">Feature SDLC Pipeline</span>
      </header>
      <main className="flex-1 p-6">{children}</main>
    </div>
  )
}
