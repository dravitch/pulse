import { useEffect, useRef, useCallback, useState } from 'react'

type WSMessage = { event: string; data?: unknown }
type MessageHandler = (msg: WSMessage) => void

export function useWebSocket(url: string, onMessage?: MessageHandler) {
  const ws = useRef<WebSocket | null>(null)
  const [connected, setConnected] = useState(false)

  const connect = useCallback(() => {
    if (ws.current?.readyState === WebSocket.OPEN) return

    ws.current = new WebSocket(url)

    ws.current.onopen = () => setConnected(true)
    ws.current.onclose = () => {
      setConnected(false)
      // Reconnect after 3s
      setTimeout(connect, 3000)
    }
    ws.current.onmessage = (e) => {
      try {
        const msg = JSON.parse(e.data) as WSMessage
        if (msg.event === 'ping') {
          ws.current?.send(JSON.stringify({ type: 'ping' }))
          return
        }
        onMessage?.(msg)
      } catch (_) {}
    }
  }, [url, onMessage])

  useEffect(() => {
    connect()
    return () => ws.current?.close()
  }, [connect])

  return { connected }
}
