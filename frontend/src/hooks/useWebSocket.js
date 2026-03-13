import { useCallback, useEffect, useRef, useState } from 'react'

const RECONNECT_DELAY = 2000
const MAX_RECONNECT_ATTEMPTS = 5

/**
 * WebSocket hook for ADK bidi-streaming.
 *
 * @param {string} userId - User identifier for the session
 * @param {string} sessionId - Session identifier
 */
export default function useWebSocket(userId, sessionId) {
  const [connectionState, setConnectionState] = useState('disconnected')
  const [lastEvent, setLastEvent] = useState(null)
  const wsRef = useRef(null)
  const reconnectAttemptsRef = useRef(0)
  const reconnectTimerRef = useRef(null)
  const mountedRef = useRef(true)

  const connect = useCallback(() => {
    if (!userId || !sessionId) return
    if (wsRef.current?.readyState === WebSocket.OPEN) return

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const url = `${protocol}//${window.location.host}/ws/${userId}/${sessionId}`

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
        const parsed = JSON.parse(event.data)
        setLastEvent(parsed)
      } catch {
        // Binary or non-JSON — ignore
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
  }, [userId, sessionId])

  const disconnect = useCallback(() => {
    clearTimeout(reconnectTimerRef.current)
    reconnectAttemptsRef.current = MAX_RECONNECT_ATTEMPTS
    wsRef.current?.close()
    wsRef.current = null
    setConnectionState('disconnected')
  }, [])

  /** Send a JSON text frame */
  const sendMessage = useCallback((data) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(data))
    }
  }, [])

  /** Send raw binary audio bytes */
  const sendBinary = useCallback((arrayBuffer) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(arrayBuffer)
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

  return { sendMessage, sendBinary, lastEvent, connectionState, connect, disconnect }
}
