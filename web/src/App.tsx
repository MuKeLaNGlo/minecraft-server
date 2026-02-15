import { useState } from 'react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { useAuth } from './hooks/useAuth'
import { useAuthStore } from './stores/authStore'
import { ServerStatus } from './components/ServerStatus'
import { PlayerList } from './components/PlayerList'
import { MonitoringCard } from './components/MonitoringCard'
import { Statistics } from './pages/Statistics'
import { Management } from './pages/Management'
import { Mods } from './pages/Mods'
import { Console } from './pages/Console'
import { Logs } from './pages/Logs'
import { PlayerProfile } from './components/PlayerProfile'
import { usePlayerStore } from './stores/playerStore'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      staleTime: 5000,
    },
  },
})

type Tab = 'dashboard' | 'stats' | 'manage' | 'mods' | 'console' | 'logs'

const TABS: { id: Tab; label: string; icon: string; adminOnly?: boolean }[] = [
  { id: 'dashboard', label: 'Главная', icon: '🏠' },
  { id: 'stats', label: 'Стата', icon: '📊' },
  { id: 'manage', label: 'Управл.', icon: '⚙️', adminOnly: true },
  { id: 'mods', label: 'Моды', icon: '🧩', adminOnly: true },
  { id: 'console', label: 'Консоль', icon: '💻' },
  { id: 'logs', label: 'Логи', icon: '📋', adminOnly: true },
]

function Dashboard() {
  return (
    <div className="space-y-3">
      <ServerStatus />
      <MonitoringCard />
      <PlayerList />
    </div>
  )
}

function TabContent({ tab }: { tab: Tab }) {
  switch (tab) {
    case 'dashboard': return <Dashboard />
    case 'stats': return <Statistics />
    case 'manage': return <Management />
    case 'mods': return <Mods />
    case 'console': return <Console />
    case 'logs': return <Logs />
  }
}

function AppShell() {
  const [tab, setTab] = useState<Tab>('dashboard')
  const firstName = useAuthStore((s) => s.firstName)
  const role = useAuthStore((s) => s.role)
  const isAdmin = role === 'admin' || role === 'super_admin'
  const selectedPlayer = usePlayerStore((s) => s.selectedPlayer)
  const closeProfile = usePlayerStore((s) => s.closeProfile)

  const visibleTabs = TABS.filter((t) => !t.adminOnly || isAdmin)

  return (
    <div className="flex flex-col min-h-screen">
      {selectedPlayer && (
        <PlayerProfile name={selectedPlayer} onClose={closeProfile} />
      )}

      <header className="max-w-lg mx-auto w-full px-4 pt-4 pb-3">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-lg font-bold tracking-tight">
              {firstName ? `Привет, ${firstName}` : 'MC Server'}
            </h1>
            <p className="text-hint text-xs mt-0.5">Управление сервером</p>
          </div>
          {role && <span className="badge badge-blue">{role}</span>}
        </div>
      </header>

      <main className="flex-1 max-w-lg mx-auto w-full px-4 pb-24">
        <TabContent tab={tab} />
      </main>

      <nav className="tab-bar">
        <div className="tab-bar-inner">
          {visibleTabs.map((t) => (
            <button
              key={t.id}
              onClick={() => setTab(t.id)}
              className={`tab-item ${tab === t.id ? 'active' : ''}`}
            >
              <span className="tab-icon">{t.icon}</span>
              <span>{t.label}</span>
            </button>
          ))}
        </div>
      </nav>
    </div>
  )
}

function AuthGate() {
  const { loading, error, authenticated } = useAuth()

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-center">
          <div className="w-10 h-10 border-2 border-[var(--tg-theme-button-color)] border-t-transparent rounded-full animate-spin mx-auto mb-4" />
          <p className="text-hint text-sm">Авторизация...</p>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="flex items-center justify-center min-h-screen px-6">
        <div className="text-center">
          <div className="text-4xl mb-3">⚠️</div>
          <p className="text-[var(--color-danger)] font-semibold mb-1">Ошибка</p>
          <p className="text-hint text-sm">{error}</p>
        </div>
      </div>
    )
  }

  if (!authenticated) return null
  return <AppShell />
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AuthGate />
    </QueryClientProvider>
  )
}
