import { useEffect, useRef, useState, useMemo } from 'react'
import AudioControls from './AudioControls'
import CameraFeed from './CameraFeed'
import useWebSocket from '../hooks/useWebSocket'
import useAudioStream from '../hooks/useAudioStream'
import useCameraStream from '../hooks/useCameraStream'

/** Generate a simple unique ID */
function makeId() {
  return Math.random().toString(36).slice(2) + Date.now().toString(36)
}

/**
 * Extract displayable content from an ADK event.
 * ADK events have a complex structure — we pull out what matters for the UI.
 */
function parseAdkEvent(event) {
  const results = []

  // Text content from model
  if (event.content?.parts) {
    for (const part of event.content.parts) {
      if (part.text && !part.thought) {
        results.push({
          type: 'transcript',
          role: event.content.role === 'user' ? 'user' : 'assistant',
          text: part.text,
          partial: event.partial ?? false,
        })
      }
      // Inline audio data from model (ADK serializes with camelCase aliases)
      const inlineData = part.inlineData || part.inline_data
      if (inlineData?.mimeType?.startsWith('audio/') || inlineData?.mime_type?.startsWith('audio/')) {
        results.push({
          type: 'audio',
          data: inlineData.data,
          mimeType: inlineData.mimeType || inlineData.mime_type,
        })
      }
    }
  }

  // Input transcription (what the user said) — may be camelCase from ADK
  const inputTranscription = event.inputTranscription || event.input_transcription
  if (inputTranscription) {
    const text = typeof inputTranscription === 'string' ? inputTranscription : inputTranscription.text
    if (text) {
      results.push({
        type: 'transcript',
        role: 'user',
        text,
        partial: inputTranscription.finished === false,
      })
    }
  }

  // Output transcription (what the model said, text version of audio)
  const outputTranscription = event.outputTranscription || event.output_transcription
  if (outputTranscription) {
    const text = typeof outputTranscription === 'string' ? outputTranscription : outputTranscription.text
    if (text) {
      results.push({
        type: 'transcript',
        role: 'assistant',
        text,
        partial: outputTranscription.finished === false,
      })
    }
  }

  // Function calls (tool use) — ADK uses camelCase aliases
  if (event.content?.parts) {
    for (const part of event.content.parts) {
      const fnCall = part.functionCall || part.function_call
      if (fnCall) {
        results.push({
          type: 'tool_call',
          name: fnCall.name,
          args: fnCall.args,
        })
      }
      const fnResp = part.functionResponse || part.function_response
      if (fnResp) {
        results.push({
          type: 'tool_result',
          name: fnResp.name,
          result: fnResp.response,
        })
      }
    }
  }

  // Turn complete signal (camelCase from ADK)
  if (event.turnComplete || event.turn_complete) {
    results.push({ type: 'turn_complete' })
  }

  return results
}

export default function LiveSession({ sessionData, onEnd }) {
  const [isMicActive, setIsMicActive] = useState(false)
  const [isSpeakerActive, setIsSpeakerActive] = useState(true)
  const [transcript, setTranscript] = useState([])
  const [isEnding, setIsEnding] = useState(false)
  const [intakeStatus, setIntakeStatus] = useState('pending') // 'pending' | 'loading' | 'ready'
  const [intakeContext, setIntakeContext] = useState(null)
  const [cameraCountdown, setCameraCountdown] = useState(null)
  const [isThinking, setIsThinking] = useState(false)
  const cameraTimerRef = useRef(null)
  const countdownIntervalRef = useRef(null)
  const transcriptEndRef = useRef(null)
  const audioContextRef = useRef(null)

  // Generate stable user/session IDs for this session
  const userId = useMemo(() => 'tech-' + makeId(), [])
  const sessionId = useMemo(() => 'session-' + makeId(), [])

  const { sendMessage, sendBinary, lastEvent, connectionState } = useWebSocket(userId, sessionId)
  const { startCapture: startAudio, stopCapture: stopAudio, isCapturing: isAudioCapturing, audioLevel } = useAudioStream({
    onBinary: (buffer) => sendBinary(buffer),
  })
  const { startCapture: startCamera, stopCapture: stopCamera, isCapturing: isCameraActive, stream: cameraStream } = useCameraStream({
    onFrame: (b64) => sendMessage({ type: 'video_frame', data: b64 }),
  })

  // Send start_session when connected
  useEffect(() => {
    if (connectionState === 'connected') {
      sendMessage({
        type: 'start_session',
        vehicle: sessionData.vehicle,
        ro_number: sessionData.roNumber,
        customer_concern: sessionData.customerConcern,
      })
    }
  }, [connectionState])

  // Accumulate streaming transcriptions
  const pendingRef = useRef({ user: '', assistant: '' })

  // Process incoming ADK events
  useEffect(() => {
    if (!lastEvent) return

    // Handle orchestrator events (not ADK events)
    if (lastEvent.type === 'intake_started') {
      setIntakeStatus('loading')
      return
    }
    if (lastEvent.type === 'intake_complete') {
      setIntakeStatus('ready')
      setIntakeContext(lastEvent.context)
      return
    }
    if (lastEvent.type === 'generating_outputs') {
      setIsEnding(true)
      setTranscript((prev) => [...prev, {
        role: 'assistant',
        text: 'Generating session documents...',
        id: Date.now(),
      }])
      return
    }
    if (lastEvent.type === 'session_outputs') {
      onEnd(lastEvent.outputs)
      return
    }
    if (lastEvent.type === 'error') {
      setTranscript((prev) => [...prev, {
        role: 'assistant',
        text: `Connection issue: ${lastEvent.message || 'Unknown error'}. You can try ending the session.`,
        id: Date.now(),
      }])
      return
    }

    const parsed = parseAdkEvent(lastEvent)
    for (const item of parsed) {
      if (item.type === 'transcript') {
        // Accumulate transcription text until turn completes
        pendingRef.current[item.role] += item.text
        if (item.role === 'user') setIsThinking(true)
        if (item.role === 'assistant') setIsThinking(false)
      } else if (item.type === 'turn_complete') {
        setIsThinking(false)
        // Flush accumulated transcription as complete messages
        for (const role of ['user', 'assistant']) {
          const text = pendingRef.current[role].trim()
          if (text) {
            setTranscript((prev) => [...prev, {
              role,
              text,
              id: Date.now() + Math.random(),
            }])
          }
          pendingRef.current[role] = ''
        }
      } else if (item.type === 'tool_call') {
        const label = item.name === 'search_knowledge_base' ? 'Searching KB...'
          : item.name === 'log_finding' ? 'Logging finding...'
          : `Running ${item.name}...`
        setTranscript((prev) => [...prev, {
          role: 'tool',
          toolType: 'call',
          toolName: item.name,
          text: label,
          id: Date.now() + Math.random(),
        }])
      } else if (item.type === 'tool_result') {
        const label = item.name === 'log_finding' ? 'Finding logged'
          : item.name === 'search_knowledge_base' ? 'KB results loaded'
          : `${item.name} complete`
        setTranscript((prev) => [...prev, {
          role: 'tool',
          toolType: 'result',
          toolName: item.name,
          text: label,
          id: Date.now() + Math.random(),
        }])
      } else if (item.type === 'audio' && isSpeakerActive) {
        playAudioChunk(item.data, item.mimeType)
      }
    }
  }, [lastEvent, isSpeakerActive])

  // Auto-scroll transcript
  useEffect(() => {
    transcriptEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [transcript])

  // Cleanup camera timers on unmount
  useEffect(() => {
    return () => {
      if (cameraTimerRef.current) clearTimeout(cameraTimerRef.current)
      if (countdownIntervalRef.current) clearInterval(countdownIntervalRef.current)
    }
  }, [])

  /** Play base64-encoded audio from the model */
  function playAudioChunk(b64Data, mimeType) {
    try {
      if (!audioContextRef.current) {
        audioContextRef.current = new AudioContext({ sampleRate: 24000 })
      }
      const ctx = audioContextRef.current
      const raw = atob(b64Data)
      const bytes = new Uint8Array(raw.length)
      for (let i = 0; i < raw.length; i++) bytes[i] = raw.charCodeAt(i)

      // PCM 16-bit signed integer at 24kHz (ADK output format)
      const int16 = new Int16Array(bytes.buffer)
      const float32 = new Float32Array(int16.length)
      for (let i = 0; i < int16.length; i++) {
        float32[i] = int16[i] / 32768
      }

      const buffer = ctx.createBuffer(1, float32.length, 24000)
      buffer.getChannelData(0).set(float32)
      const source = ctx.createBufferSource()
      source.buffer = buffer
      source.connect(ctx.destination)
      source.start()
    } catch (err) {
      console.error('Failed to play audio chunk:', err)
    }
  }

  function handleMicToggle() {
    if (isMicActive) {
      stopAudio()
      setIsMicActive(false)
    } else {
      startAudio()
      setIsMicActive(true)
    }
  }

  function handleCameraToggle() {
    if (isCameraActive) {
      stopCamera()
      sendMessage({ type: 'camera_stopped' })
      setCameraCountdown(null)
      if (cameraTimerRef.current) {
        clearTimeout(cameraTimerRef.current)
        cameraTimerRef.current = null
      }
      if (countdownIntervalRef.current) {
        clearInterval(countdownIntervalRef.current)
        countdownIntervalRef.current = null
      }
    } else {
      startCamera()
      setCameraCountdown(15)
      countdownIntervalRef.current = setInterval(() => {
        setCameraCountdown((prev) => {
          if (prev <= 0) {
            clearInterval(countdownIntervalRef.current)
            countdownIntervalRef.current = null
            return null
          }
          return prev - 1
        })
      }, 1000)
      cameraTimerRef.current = setTimeout(() => {
        stopCamera()
        sendMessage({ type: 'camera_stopped' })
        setCameraCountdown(null)
        if (countdownIntervalRef.current) {
          clearInterval(countdownIntervalRef.current)
          countdownIntervalRef.current = null
        }
        cameraTimerRef.current = null
      }, 15000)
    }
  }

  function handleEndSession() {
    setIsEnding(true)
    stopAudio()
    stopCamera()
    setIsMicActive(false)
    sendMessage({ type: 'end_session' })
  }

  const statusColor = {
    connecting: 'text-yellow-400',
    connected: 'text-green-400',
    disconnected: 'text-red-400',
  }[connectionState] ?? 'text-gray-400'

  return (
    <div className="h-full flex flex-col lg:flex-row gap-0 overflow-hidden relative">
      {intakeStatus !== 'ready' && (
        <div className="absolute inset-0 bg-gray-900/95 z-10 flex items-center justify-center">
          <div className="text-center max-w-sm">
            <div className="relative w-16 h-16 mx-auto mb-6">
              <div className="absolute inset-0 rounded-full border-4 border-gray-700" />
              <div className="absolute inset-0 rounded-full border-4 border-blue-500 border-t-transparent animate-spin" />
            </div>
            <p className="text-xl font-semibold text-white mb-2">Preparing Session</p>
            <p className="text-sm text-gray-400 leading-relaxed">
              {intakeStatus === 'pending' ? 'Connecting to TechLens...' : 'Analyzing vehicle history, matching TSBs, and building diagnostic context...'}
            </p>
          </div>
        </div>
      )}

      {/* Left panel: camera + controls */}
      <div className="lg:w-96 xl:w-[420px] flex flex-col gap-4 p-4 border-b lg:border-b-0 lg:border-r border-gray-700 shrink-0">
        <CameraFeed
          isActive={isCameraActive}
          onToggle={handleCameraToggle}
          stream={cameraStream}
          autoStopSeconds={cameraCountdown}
        />

        <AudioControls
          isMicActive={isMicActive}
          onMicToggle={handleMicToggle}
          isSpeakerActive={isSpeakerActive}
          onSpeakerToggle={() => setIsSpeakerActive((v) => !v)}
          audioLevel={audioLevel}
        />

        {/* Status indicators */}
        <div className="bg-gray-800 rounded-xl px-5 py-3 border border-gray-700 space-y-2">
          <div className="flex items-center justify-between text-sm">
            <span className="text-gray-400">Connection</span>
            <span className={`font-medium capitalize ${statusColor}`}>{connectionState}</span>
          </div>
          <div className="flex items-center justify-between text-sm">
            <span className="text-gray-400">Recording</span>
            <span className={`font-medium ${isMicActive ? 'text-green-400' : 'text-gray-500'}`}>
              {isMicActive ? 'Active' : 'Paused'}
            </span>
          </div>
          <div className="flex items-center justify-between text-sm">
            <span className="text-gray-400">Camera</span>
            <span className={`font-medium ${isCameraActive ? 'text-green-400' : 'text-gray-500'}`}>
              {isCameraActive ? 'Active' : 'Off'}
            </span>
          </div>
        </div>

        {intakeContext && !intakeContext.error && (
          <div className="bg-gray-800 rounded-xl px-5 py-3 border border-gray-700 text-sm text-gray-300 space-y-2">
            <div className="flex items-center justify-between">
              <span className="font-medium text-white">Context Loaded</span>
              <span className="text-xs text-green-400 font-medium">Ready</span>
            </div>
            <div className="flex gap-3 text-xs">
              <span className="bg-gray-700 px-2 py-1 rounded">{intakeContext.tsb_count} TSBs</span>
              <span className="bg-gray-700 px-2 py-1 rounded">{intakeContext.issue_count} Issues</span>
            </div>
          </div>
        )}

        {/* End session */}
        <button
          onClick={handleEndSession}
          disabled={isEnding}
          className="w-full bg-red-700 hover:bg-red-600 active:bg-red-800 disabled:opacity-50 disabled:cursor-not-allowed text-white font-semibold py-4 rounded-xl text-base transition-colors min-h-[56px] cursor-pointer mt-auto"
        >
          {isEnding ? 'Ending Session...' : 'End Session'}
        </button>
      </div>

      {/* Right panel: transcript */}
      <div className="flex-1 flex flex-col overflow-hidden">
        <div className="px-4 py-3 border-b border-gray-700 shrink-0">
          <h2 className="text-sm font-medium text-gray-400 uppercase tracking-wider">Conversation</h2>
        </div>

        <div className="flex-1 overflow-y-auto p-4 space-y-3">
          {transcript.length === 0 && (
            <div className="text-center text-gray-600 mt-16 space-y-4">
              <div className="text-4xl">🔧</div>
              <p className="text-lg text-gray-400">Ready to diagnose</p>
              <div className="text-sm space-y-1 text-gray-600">
                <p>Tap the mic to start talking</p>
                <p>Tap the camera to show a component</p>
              </div>
            </div>
          )}
          {transcript.map((entry) => (
            <div
              key={entry.id}
              className={`flex ${entry.role === 'user' ? 'justify-end' : entry.role === 'tool' ? 'justify-center' : 'justify-start'}`}
            >
              {entry.role === 'tool' ? (
                <div className="flex items-center gap-2 text-xs text-gray-500 py-1">
                  <span className={`w-1.5 h-1.5 rounded-full ${entry.toolType === 'call' ? 'bg-yellow-500 animate-pulse' : 'bg-green-500'}`} />
                  <span>{entry.text}</span>
                </div>
              ) : (
              <div
                className={`max-w-[85%] rounded-2xl px-4 py-3 text-sm leading-relaxed ${
                  entry.role === 'user'
                    ? 'bg-blue-600 text-white rounded-br-sm'
                    : 'bg-gray-800 text-gray-100 rounded-bl-sm'
                }`}
              >
                {entry.role !== 'user' && (
                  <div className="text-xs text-gray-500 mb-1 font-medium uppercase tracking-wide">TechLens</div>
                )}
                {entry.text}
              </div>
              )}
            </div>
          ))}
          {isThinking && (
            <div className="flex justify-start">
              <div className="bg-gray-800 rounded-2xl px-4 py-3 rounded-bl-sm">
                <div className="text-xs text-gray-500 mb-1 font-medium uppercase tracking-wide">TechLens</div>
                <div className="flex gap-1">
                  <span className="w-2 h-2 bg-gray-500 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                  <span className="w-2 h-2 bg-gray-500 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                  <span className="w-2 h-2 bg-gray-500 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
                </div>
              </div>
            </div>
          )}
          <div ref={transcriptEndRef} />
        </div>
      </div>
    </div>
  )
}
