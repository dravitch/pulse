import { useApi } from '../../hooks/useApi'
import { TrendingUp, TrendingDown, RefreshCw } from 'lucide-react'

interface Position {
  asset: string
  units: number
  avg_cost_basis: number
  current_value: number
  price: number
  allocation: number
  target: number
  drift: number
}

interface PortfolioResponse {
  positions: Position[]
  total_value: number
  max_drift: number
  needs_rebalance: boolean
}

interface Props {
  compact?: boolean
}

const ASSET_COLOR: Record<string, string> = {
  BTC: 'text-orange-400',
  ETH: 'text-blue-400',
  PAXG: 'text-yellow-400',
}

export default function FinPulsePanel({ compact = false }: Props) {
  const { data, loading, error, refetch } = useApi<PortfolioResponse>('/portfolio')

  if (loading) return <Skeleton />
  if (error) return <ErrorState msg={error} onRetry={refetch} />

  const { positions, total_value, needs_rebalance } = data!

  if (compact) {
    return (
      <div>
        <div className="text-2xl font-bold text-white mb-2">
          ${total_value.toLocaleString('en-US', { minimumFractionDigits: 2 })}
        </div>
        <div className="flex gap-2">
          {positions.map((p) => (
            <div key={p.asset} className="flex-1 text-center bg-[#0a0a0f] rounded-lg p-2">
              <div className={`text-xs font-bold ${ASSET_COLOR[p.asset] ?? 'text-slate-400'}`}>{p.asset}</div>
              <div className="text-sm font-semibold text-white">{p.allocation.toFixed(1)}%</div>
              {Math.abs(p.drift) >= 1 && <DriftBadge drift={p.drift} />}
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
          {needs_rebalance && (
            <div className="mt-1 text-xs text-yellow-400 flex items-center gap-1">
              <TrendingUp size={10} /> Drift &gt;5% — rebalancing suggested
            </div>
          )}
        </div>
        <button onClick={refetch} className="pulse-btn-ghost">
          <RefreshCw size={14} className="inline mr-1" />
          Refresh
        </button>
      </div>

      {/* Live Prices */}
      <div className="grid grid-cols-3 gap-3">
        {positions.map((p) => (
          <div key={p.asset} className="pulse-card text-center">
            <div className={`text-xs font-bold uppercase tracking-widest mb-1 ${ASSET_COLOR[p.asset] ?? 'text-slate-400'}`}>
              {p.asset}
            </div>
            <div className="text-lg font-bold text-white">
              ${(p.price ?? p.current_value / (p.units || 1)).toLocaleString('en-US', { minimumFractionDigits: 2 })}
            </div>
            <div className="text-xs text-slate-500 mt-0.5">live · Binance</div>
          </div>
        ))}
      </div>

      {/* Positions */}
      <div className="grid grid-cols-3 gap-3">
        {positions.map((p) => {
          const pnl = p.current_value - p.avg_cost_basis * p.units
          const pnlPct = p.avg_cost_basis > 0 ? (pnl / (p.avg_cost_basis * p.units)) * 100 : 0
          return (
            <div key={p.asset} className="pulse-card space-y-2">
              <div className="flex items-center justify-between">
                <span className={`text-sm font-bold ${ASSET_COLOR[p.asset] ?? 'text-white'}`}>{p.asset}</span>
                {Math.abs(p.drift) >= 1 && <DriftBadge drift={p.drift} />}
              </div>

              <div className="text-2xl font-bold text-white">{p.allocation.toFixed(1)}%</div>

              <div className="text-xs text-slate-500">{p.units.toFixed(6)} units</div>
              <div className="text-xs text-slate-500">avg ${p.avg_cost_basis.toLocaleString('en-US', { minimumFractionDigits: 2 })}</div>

              <div className="text-sm font-semibold text-slate-300">
                ${p.current_value.toLocaleString('en-US', { minimumFractionDigits: 2 })}
              </div>

              {/* P&L */}
              <div className={`text-xs font-medium ${pnl >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                {pnl >= 0 ? '+' : ''}${pnl.toLocaleString('en-US', { minimumFractionDigits: 2 })}
                {' '}({pnlPct >= 0 ? '+' : ''}{pnlPct.toFixed(1)}%)
              </div>

              {/* Allocation bar */}
              <div className="h-1 bg-[#0a0a0f] rounded-full">
                <div
                  className="h-1 bg-indigo-500 rounded-full transition-all duration-500"
                  style={{ width: `${Math.min(p.allocation, 100)}%` }}
                />
              </div>
              <div className="text-xs text-slate-600">target {p.target}%</div>
            </div>
          )
        })}
      </div>

      <InsightSection />
    </div>
  )
}

function DriftBadge({ drift }: { drift: number }) {
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
      <p className="text-sm text-slate-300 leading-relaxed whitespace-pre-wrap">{data.insight}</p>
    </div>
  )
}

function Skeleton() {
  return (
    <div className="p-6 space-y-4 animate-pulse">
      <div className="h-10 bg-[#1e1e2e] rounded w-48" />
      <div className="grid grid-cols-3 gap-3">
        {[1, 2, 3].map((i) => <div key={i} className="h-20 bg-[#1e1e2e] rounded-xl" />)}
      </div>
      <div className="grid grid-cols-3 gap-3">
        {[1, 2, 3].map((i) => <div key={i} className="h-36 bg-[#1e1e2e] rounded-xl" />)}
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
