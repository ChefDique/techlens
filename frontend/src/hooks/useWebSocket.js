import { useCallback, useEffect, useRef, useState } from 'react'

const RECONNECT_DELAY = 2000
const MAX_RECONNECT_ATTEMPTS = 5

export default function useWebSocket(path) {
  const [connectionState, setConnectionState] = useState('disconnected')
  const [lastMessage, setLastMessage] = useState(null)
  const wsRef = useRef(null)
  const reconnectAttemptsRef = useRef(0)
  const reconnectTimerRef = useRef(null)
  const mountedRef = useRef(true)

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const url = `${protocol}//${window.location.host}${path}`

    setConnectionState('connecting')
    const ws = new WebSocket(url)
    wsRef.current = ws

    ws.onopen = () => {
      if (!mountedRef.current) return
      setConnectionState('connected')
      reconnectAttemptsRef.current = 0
    }

    ws.onmessage = (event) => {
      if (!mountedRef.current) return
      try {
        const msg = JSON.parse(event.data)
        setLastMessage(msg)
      } catch {
        setLastMessage({ type: 'raw', data: event.data })
      }
    }

    ws.onclose = () => {
      if (!mountedRef.current) return
      setConnectionState('disconnected')
      wsRef.current = null

      if (reconnectAttemptsRef.current < MAX_RECONNECT_ATTEMPTS) {
        reconnectAttemptsRef.current += 1
        reconnectTimerRef.current = setTimeout(connect, RECONNECT_DELAY)
      }
    }

    ws.onerror = () => {
      ws.close()
    }
  }, [path])

  const disconnect = useCallback(() => {
    clearTimeout(reconnectTimerRef.current)
    reconnectAttemptsRef.current = MAX_RECONNECT_ATTEMPTS // prevent auto-reconnect
    wsRef.current?.close()
    wsRef.current = null
    setConnectionState('disconnected')
  }, [])

  const sendMessage = useCallback((data) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(data))
    }
  }, [])

  useEffect(() => {
    mountedRef.current = true
    connect()
    return () => {
      mountedRef.current = false
      clearTimeout(reconnectTimerRef.current)
      wsRef.current?.close()
    }
  }, [connect])

  return { sendMessage, lastMessage, connectionState, connect, disconnect }
}
