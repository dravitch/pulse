import { useState } from 'react'
import { useApi, apiFetch } from '../../hooks/useApi'
import { ExternalLink, Check, Archive } from 'lucide-react'

interface Article {
  id: number
  source: string
  title: string
  url: string
  published: string | null
  relevance_score: number | null
  read: boolean
  summary: string | null
}

interface NewsResponse {
  articles: Article[]
}

interface Props {
  compact?: boolean
}

export default function NewsPulsePanel({ compact = false }: Props) {
  const [unreadOnly, setUnreadOnly] = useState(false)
  const { data, loading, error, refetch } = useApi<NewsResponse>(
    `/news?unread_only=${unreadOnly}`,
    [unreadOnly]
  )

  const markRead = async (id: number) => {
    await apiFetch(`/news/${id}/read`, { method: 'POST' })
    refetch()
  }

  const archive = async (id: number) => {
    await apiFetch(`/news/${id}/archive`, { method: 'POST' })
    refetch()
  }

  if (loading) return <Skeleton compact={compact} />
  if (error) return <div className="p-4 text-red-400 text-sm">{error}</div>

  const articles = data?.articles ?? []

  if (compact) {
    return (
      <div className="space-y-2">
        {articles.slice(0, 5).map((a) => (
          <div key={a.id} className="flex items-center gap-2">
            <ScoreBadge score={a.relevance_score} />
            <a href={a.url} target="_blank" rel="noopener noreferrer"
              className="text-xs text-slate-300 hover:text-indigo-300 line-clamp-1 flex-1">
              {a.title}
            </a>
          </div>
        ))}
        {articles.length === 0 && <p className="text-xs text-slate-600">No articles yet</p>}
      </div>
    )
  }

  return (
    <div className="p-6 space-y-4">
      {/* Toolbar */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-sm text-slate-400">{articles.length} articles</span>
          <button
            onClick={() => setUnreadOnly(!unreadOnly)}
            className={`pulse-btn-ghost text-xs ${unreadOnly ? 'border-indigo-500 text-indigo-300' : ''}`}
          >
            {unreadOnly ? 'All' : 'Unread only'}
          </button>
        </div>
        <DigestButton />
      </div>

      {/* Articles */}
      <div className="space-y-2">
        {articles.map((a) => (
          <div key={a.id}
            className={`pulse-card flex items-start gap-3 hover:border-slate-600 transition-colors ${a.read ? 'opacity-50' : ''}`}>
            <ScoreBadge score={a.relevance_score} />

            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 mb-0.5">
                <span className="text-xs text-indigo-400 font-medium">{a.source}</span>
                {a.published && (
                  <span className="text-xs text-slate-600">
                    {new Date(a.published).toLocaleDateString()}
                  </span>
                )}
              </div>
              <a href={a.url} target="_blank" rel="noopener noreferrer"
                className="text-sm text-slate-200 hover:text-white font-medium line-clamp-2">
                {a.title}
                <ExternalLink size={11} className="inline ml-1 text-slate-500" />
              </a>
              {a.summary && (
                <p className="text-xs text-slate-500 mt-1 line-clamp-2">{a.summary}</p>
              )}
            </div>

            <div className="flex gap-1 shrink-0">
              {!a.read && (
                <button onClick={() => markRead(a.id)}
                  className="p-1.5 rounded hover:bg-emerald-500/20 text-slate-500 hover:text-emerald-400 transition-colors"
                  title="Mark read">
                  <Check size={13} />
                </button>
              )}
              <button onClick={() => archive(a.id)}
                className="p-1.5 rounded hover:bg-slate-500/20 text-slate-600 hover:text-slate-400 transition-colors"
                title="Archive">
                <Archive size={13} />
              </button>
            </div>
          </div>
        ))}

        {articles.length === 0 && (
          <div className="text-center py-12 text-slate-600 text-sm">
            No articles yet. Feeds are fetched every 15 minutes.
          </div>
        )}
      </div>
    </div>
  )
}

function ScoreBadge({ score }: { score: number | null }) {
  if (score === null) return <div className="w-8 h-8 rounded bg-[#0a0a0f]" />
  const color = score >= 0.85 ? 'text-emerald-400' : score >= 0.7 ? 'text-yellow-400' : 'text-slate-500'
  return (
    <div className={`w-8 h-8 rounded bg-[#0a0a0f] flex items-center justify-center text-xs font-bold ${color} shrink-0`}>
      {Math.round(score * 10)}
    </div>
  )
}

function DigestButton() {
  const [digest, setDigest] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  const fetchDigest = async (type: 'morning' | 'evening') => {
    setLoading(true)
    try {
      const res = await apiFetch<{ summary: string }>(`/news/digest/${type}`)
      setDigest(res.summary)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="relative">
      <div className="flex gap-1">
        <button onClick={() => fetchDigest('morning')} className="pulse-btn-ghost text-xs" disabled={loading}>
          Morning brief
        </button>
        <button onClick={() => fetchDigest('evening')} className="pulse-btn-ghost text-xs" disabled={loading}>
          Evening brief
        </button>
      </div>
      {digest && (
        <div className="absolute right-0 top-10 w-80 pulse-card border-indigo-500/30 z-10 shadow-xl">
          <div className="flex justify-between items-center mb-2">
            <span className="text-xs text-indigo-400 uppercase tracking-widest">Digest</span>
            <button onClick={() => setDigest(null)} className="text-slate-600 hover:text-white text-xs">✕</button>
          </div>
          <p className="text-xs text-slate-300 leading-relaxed whitespace-pre-line">{digest}</p>
        </div>
      )}
    </div>
  )
}

function Skeleton({ compact }: { compact: boolean }) {
  if (compact) return <div className="space-y-2">{[1,2,3].map(i => <div key={i} className="h-4 bg-[#1e1e2e] rounded animate-pulse" />)}</div>
  return <div className="p-6 space-y-3">{[1,2,3,4,5].map(i => <div key={i} className="h-16 bg-[#1e1e2e] rounded-xl animate-pulse" />)}</div>
}
