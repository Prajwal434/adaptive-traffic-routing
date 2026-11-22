// WebSocket hook — connects to backend ws://localhost:8000/ws
// and returns the latest world state broadcast.
import { useEffect, useRef, useState } from 'react'

export function useTrafficSocket(url = 'ws://localhost:8001/ws') {
  const [state, setState] = useState(null)
  const [connected, setConnected] = useState(false)
  const wsRef = useRef(null)

  useEffect(() => {
    function connect() {
      const ws = new WebSocket(url)
      wsRef.current = ws

      ws.onopen = () => setConnected(true)
      ws.onclose = () => {
        setConnected(false)
        // Auto-reconnect after 2s
        setTimeout(connect, 2000)
      }
      ws.onerror = () => ws.close()
      ws.onmessage = (e) => {
        try {
          setState(JSON.parse(e.data))
        } catch (_) {}
      }
    }
    connect()
    return () => wsRef.current?.close()
  }, [url])

  return { state, connected }
}
