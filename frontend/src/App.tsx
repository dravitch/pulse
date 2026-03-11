import { useState } from 'react'
import Dashboard from './components/Dashboard'
import { Activity } from 'lucide-react'

type Tab = 'dashboard' | 'finpulse' | 'newspulse' | 'chat'

export default function App() {
  const [activeTab, setActiveTab] = useState<Tab>('dashboard')

  const tabs: { id: Tab; label: string; icon: string }[] = [
    { id: 'dashboard', label: 'Dashboard', icon: '◈' },
    { id: 'finpulse', label: 'FinPulse', icon: '₿' },
    { id: 'newspulse', label: 'NewsPulse', icon: '⬡' },
    { id: 'chat', label: 'Claude', icon: '◎' },
  ]

  return (
    <div className="min-h-screen bg-[#0a0a0f] flex flex-col">
      {/* Header */}
      <header className="border-b border-[#1e1e2e] px-6 py-3 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Activity className="text-indigo-400" size={20} />
          <span className="text-lg font-bold tracking-widest text-white">PULSE</span>
          <span className="text-xs text-slate-500 ml-1">v0.1.0</span>
        </div>

        <nav className="flex items-center gap-1">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`px-4 py-2 rounded-lg text-sm font-medium transition-all ${
                activeTab === tab.id
                  ? 'bg-indigo-500/20 text-indigo-300 border border-indigo-500/40'
                  : 'text-slate-500 hover:text-slate-300 hover:bg-white/5'
              }`}
            >
              <span className="mr-1.5">{tab.icon}</span>
              {tab.label}
            </button>
          ))}
        </nav>

        <div className="flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
          <span className="text-xs text-slate-500">live</span>
        </div>
      </header>

      {/* Main content */}
      <main className="flex-1 overflow-auto">
        <Dashboard activeTab={activeTab} />
      </main>
    </div>
  )
}
