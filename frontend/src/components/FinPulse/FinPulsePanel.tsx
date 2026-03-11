import { useApi } from '../../hooks/useApi'
import { TrendingUp, TrendingDown, RefreshCw } from 'lucide-react'

interface Position {
  asset: string
  units: number
  avg_cost_basis: number
  current_value: number
  allocation: number
}

interface PortfolioResponse {
  positions: Position[]
  total_value: number
}

interface Props {
  compact?: boolean
}

const TARGETS: Record<string, number> = { BTC: 60, ETH: 30, PAXG: 10 }

export default function FinPulsePanel({ compact = false }: Props) {
  const { data, loading, error, refetch } = useApi<PortfolioResponse>('/portfolio')

  if (loading) return <Skeleton />
  if (error) return <ErrorState msg={error} onRetry={refetch} />

  const { positions, total_value } = data!

  if (compact) {
    return (
      <div>
        <div className="text-2xl font-bold text-white mb-2">
          ${total_value.toLocaleString('en-US', { minimumFractionDigits: 2 })}
        </div>
        <div className="flex gap-2">
          {positions.map((p) => (
            <div key={p.asset} className="flex-1 text-center bg-[#0a0a0f] rounded-lg p-2">
              <div className="text-xs text-slate-500">{p.asset}</div>
              <div className="text-sm font-semibold text-white">{p.allocation.toFixed(1)}%</div>
              <DriftBadge asset={p.asset} actual={p.allocation} />
            </div>
          ))}
        </div>
      </div>
    )
  }

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <div className="text-xs text-slate-500 uppercase tracking-widest mb-1">Total Value</div>
          <div className="text-4xl font-bold text-white">
            ${total_value.toLocaleString('en-US', { minimumFractionDigits: 2 })}
          </div>
        </div>
        <button onClick={refetch} className="pulse-btn-ghost">
          <RefreshCw size={14} className="inline mr-1" />
          Refresh
        </button>
      </div>

      {/* Positions */}
      <div className="grid grid-cols-3 gap-3">
        {positions.map((p) => (
          <div key={p.asset} className="pulse-card space-y-1">
            <div className="flex items-center justify-between">
              <span className="text-sm font-bold text-white">{p.asset}</span>
              <DriftBadge asset={p.asset} actual={p.allocation} />
            </div>
            <div className="text-2xl font-bold text-indigo-300">{p.allocation.toFixed(1)}%</div>
            <div className="text-xs text-slate-500">
              {p.units.toFixed(6)} units
            </div>
            <div className="text-xs text-slate-500">
              avg ${p.avg_cost_basis.toFixed(2)}
            </div>
            <div className="text-sm text-slate-300">
              ${p.current_value.toLocaleString('en-US', { minimumFractionDigits: 2 })}
            </div>

            {/* Allocation bar */}
            <div className="h-1 bg-[#0a0a0f] rounded-full mt-2">
              <div
                className="h-1 bg-indigo-500 rounded-full"
                style={{ width: `${Math.min(p.allocation, 100)}%` }}
              />
            </div>
            <div className="text-xs text-slate-600">target {TARGETS[p.asset] ?? '?'}%</div>
          </div>
        ))}
      </div>

      <InsightSection />
    </div>
  )
}

function DriftBadge({ asset, actual }: { asset: string; actual: number }) {
  const target = TARGETS[asset] ?? actual
  const drift = actual - target
  if (Math.abs(drift) < 1) return null
  return (
    <span className={`pulse-tag ${drift > 0 ? 'bg-yellow-500/20 text-yellow-400' : 'bg-blue-500/20 text-blue-400'}`}>
      {drift > 0 ? <TrendingUp size={10} className="inline" /> : <TrendingDown size={10} className="inline" />}
      {' '}{Math.abs(drift).toFixed(1)}%
    </span>
  )
}

function InsightSection() {
  const { data, loading } = useApi<{ insight: string }>('/portfolio/insight')
  if (loading) return <div className="pulse-card animate-pulse h-16" />
  if (!data) return null
  return (
    <div className="pulse-card border-indigo-500/20">
      <div className="text-xs text-indigo-400 mb-2 uppercase tracking-widest">Claude Insight</div>
      <p className="text-sm text-slate-300 leading-relaxed">{data.insight}</p>
    </div>
  )
}

function Skeleton() {
  return (
    <div className="p-6 space-y-4 animate-pulse">
      <div className="h-10 bg-[#1e1e2e] rounded w-48" />
      <div className="grid grid-cols-3 gap-3">
        {[1, 2, 3].map((i) => <div key={i} className="h-32 bg-[#1e1e2e] rounded-xl" />)}
      </div>
    </div>
  )
}

function ErrorState({ msg, onRetry }: { msg: string; onRetry: () => void }) {
  return (
    <div className="p-6 text-center space-y-3">
      <div className="text-red-400 text-sm">{msg}</div>
      <button onClick={onRetry} className="pulse-btn">Retry</button>
    </div>
  )
}
