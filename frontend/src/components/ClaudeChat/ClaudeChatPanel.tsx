import { useState, useRef, useEffect } from 'react'
import { apiFetch } from '../../hooks/useApi'
import { Send, Zap } from 'lucide-react'

interface Message {
  role: 'user' | 'assistant'
  content: string
}

const QUICK_ACTIONS = [
  { label: 'Analyse semaine', msg: 'Analyse les performances de mon portefeuille cette semaine et donne les points clés.' },
  { label: 'Rééquilibrer ?', msg: 'Dois-je rééquilibrer mon portefeuille maintenant ? Vérifie le drift actuel vs les cibles.' },
  { label: 'Ratio de Sharpe', msg: 'Explique le ratio de Sharpe et comment il s\'applique à mon portefeuille.' },
  { label: 'Stratégie DCA', msg: 'Évalue ma stratégie DCA. Mon montant mensuel est-il optimal pour mes objectifs ?' },
]

interface Props {
  compact?: boolean
}

export default function ClaudeChatPanel({ compact = false }: Props) {
  const [messages, setMessages] = useState<Message[]>([
    {
      role: 'assistant',
      content: 'Bonjour. Je suis PULSE, votre assistant personnel spécialisé en finance crypto. J\'ai accès à votre portefeuille et à votre flux d\'actualités. Comment puis-je vous aider ?',
    },
  ])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const sendMessage = async (text: string) => {
    if (!text.trim() || loading) return

    const userMsg: Message = { role: 'user', content: text }
    setMessages((prev) => [...prev, userMsg])
    setInput('')
    setLoading(true)

    try {
      const res = await apiFetch<{ response: string }>('/chat', {
        method: 'POST',
        body: JSON.stringify({ message: text }),
      })
      setMessages((prev) => [...prev, { role: 'assistant', content: res.response }])
    } catch (e) {
      setMessages((prev) => [
        ...prev,
        { role: 'assistant', content: 'Erreur de connexion à Claude. Vérifiez votre clé API.' },
      ])
    } finally {
      setLoading(false)
    }
  }

  if (compact) {
    return (
      <div className="space-y-2">
        <div className="text-xs text-slate-500">
          {messages[messages.length - 1]?.content.slice(0, 120)}...
        </div>
        <div className="flex gap-1 flex-wrap">
          {QUICK_ACTIONS.slice(0, 2).map((a) => (
            <button key={a.label} onClick={() => sendMessage(a.msg)}
              className="pulse-btn-ghost text-xs" disabled={loading}>
              {a.label}
            </button>
          ))}
        </div>
      </div>
    )
  }

  return (
    <div className="flex flex-col h-[calc(100vh-64px)]">
      {/* Quick actions */}
      <div className="border-b border-[#1e1e2e] px-6 py-3 flex items-center gap-2 flex-wrap">
        <Zap size={14} className="text-yellow-400 shrink-0" />
        {QUICK_ACTIONS.map((a) => (
          <button key={a.label} onClick={() => sendMessage(a.msg)}
            className="pulse-btn-ghost text-xs" disabled={loading}>
            {a.label}
          </button>
        ))}
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-6 space-y-4">
        {messages.map((msg, i) => (
          <div key={i} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
            <div className={`max-w-[75%] rounded-xl px-4 py-3 text-sm leading-relaxed ${
              msg.role === 'user'
                ? 'bg-indigo-500/20 text-indigo-100 border border-indigo-500/30'
                : 'bg-[#12121a] text-slate-300 border border-[#1e1e2e]'
            }`}>
              {msg.role === 'assistant' && (
                <div className="text-xs text-indigo-400 mb-1 uppercase tracking-widest">PULSE</div>
              )}
              <p className="whitespace-pre-wrap">{msg.content}</p>
            </div>
          </div>
        ))}

        {loading && (
          <div className="flex justify-start">
            <div className="bg-[#12121a] border border-[#1e1e2e] rounded-xl px-4 py-3">
              <div className="flex gap-1">
                <span className="w-2 h-2 bg-indigo-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                <span className="w-2 h-2 bg-indigo-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                <span className="w-2 h-2 bg-indigo-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
              </div>
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div className="border-t border-[#1e1e2e] p-4">
        <form
          onSubmit={(e) => { e.preventDefault(); sendMessage(input) }}
          className="flex gap-3"
        >
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Posez une question sur votre portefeuille ou les actualités..."
            disabled={loading}
            className="flex-1 bg-[#12121a] border border-[#1e1e2e] focus:border-indigo-500 rounded-lg px-4 py-2.5 text-sm text-slate-200 placeholder-slate-600 outline-none transition-colors"
          />
          <button type="submit" disabled={!input.trim() || loading}
            className="pulse-btn px-4 disabled:opacity-40">
            <Send size={15} />
          </button>
        </form>
      </div>
    </div>
  )
}
