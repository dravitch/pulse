import FinPulsePanel from './FinPulse/FinPulsePanel'
import NewsPulsePanel from './NewsPulse/NewsPulsePanel'
import ClaudeChatPanel from './ClaudeChat/ClaudeChatPanel'
import { useWebSocket } from '../hooks/useWebSocket'
import { useState, useCallback } from 'react'

type Tab = 'dashboard' | 'finpulse' | 'newspulse' | 'chat'

interface Props {
  activeTab: Tab
}

export default function Dashboard({ activeTab }: Props) {
  const [lastEvent, setLastEvent] = useState<string>('')

  const handleMessage = useCallback((msg: { event: string }) => {
    setLastEvent(msg.event)
  }, [])

  const { connected } = useWebSocket(
    `${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}/ws`,
    handleMessage
  )

  if (activeTab === 'finpulse') return <FinPulsePanel />
  if (activeTab === 'newspulse') return <NewsPulsePanel />
  if (activeTab === 'chat') return <ClaudeChatPanel />

  // Default: dashboard overview
  return (
    <div className="p-6 grid grid-cols-1 lg:grid-cols-2 gap-4">
      <div className="pulse-card">
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-sm font-semibold text-slate-300">FinPulse</h2>
          <span className={`pulse-tag ${connected ? 'bg-emerald-500/20 text-emerald-400' : 'bg-red-500/20 text-red-400'}`}>
            {connected ? 'live' : 'offline'}
          </span>
        </div>
        <FinPulsePanel compact />
      </div>

      <div className="pulse-card">
        <h2 className="text-sm font-semibold text-slate-300 mb-3">NewsPulse</h2>
        <NewsPulsePanel compact />
      </div>

      <div className="pulse-card lg:col-span-2">
        <h2 className="text-sm font-semibold text-slate-300 mb-3">Claude</h2>
        <ClaudeChatPanel compact />
      </div>

      {lastEvent && (
        <div className="text-xs text-slate-600 lg:col-span-2">
          last event: {lastEvent}
        </div>
      )}
    </div>
  )
}
