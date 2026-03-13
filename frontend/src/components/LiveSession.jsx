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
      if (part.text) {
        results.push({
          type: 'transcript',
          role: event.content.role === 'user' ? 'user' : 'assistant',
          text: part.text,
          partial: event.partial ?? false,
        })
      }
      // Inline audio data from model
      if (part.inline_data?.mime_type?.startsWith('audio/')) {
        results.push({
          type: 'audio',
          data: part.inline_data.data,
          mimeType: part.inline_data.mime_type,
        })
      }
    }
  }

  // Input transcription (what the user said)
  if (event.input_transcription) {
    results.push({
      type: 'transcript',
      role: 'user',
      text: event.input_transcription,
      partial: false,
    })
  }

  // Output transcription (what the model said, text version of audio)
  if (event.output_transcription) {
    results.push({
      type: 'transcript',
      role: 'assistant',
      text: event.output_transcription,
      partial: false,
    })
  }

  // Function calls (tool use)
  if (event.content?.parts) {
    for (const part of event.content.parts) {
      if (part.function_call) {
        results.push({
          type: 'tool_call',
          name: part.function_call.name,
          args: part.function_call.args,
        })
      }
      if (part.function_response) {
        results.push({
          type: 'tool_result',
          name: part.function_response.name,
          result: part.function_response.response,
        })
      }
    }
  }

  // Turn complete signal
  if (event.turn_complete) {
    results.push({ type: 'turn_complete' })
  }

  return results
}

export default function LiveSession({ sessionData, onEnd }) {
  const [isMicActive, setIsMicActive] = useState(false)
  const [isSpeakerActive, setIsSpeakerActive] = useState(true)
  const [transcript, setTranscript] = useState([])
  const [isEnding, setIsEnding] = useState(false)
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

  // Process incoming ADK events
  useEffect(() => {
    if (!lastEvent) return

    const parsed = parseAdkEvent(lastEvent)
    for (const item of parsed) {
      if (item.type === 'transcript' && !item.partial) {
        setTranscript((prev) => [...prev, {
          role: item.role,
          text: item.text,
          id: Date.now() + Math.random(),
        }])
      } else if (item.type === 'tool_call') {
        setTranscript((prev) => [...prev, {
          role: 'tool',
          text: `[Calling: ${item.name}]`,
          id: Date.now() + Math.random(),
        }])
      } else if (item.type === 'tool_result') {
        const summary = typeof item.result === 'string'
          ? item.result.slice(0, 200)
          : JSON.stringify(item.result).slice(0, 200)
        setTranscript((prev) => [...prev, {
          role: 'tool',
          text: `[${item.name}] ${summary}`,
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
    } else {
      startCamera()
    }
  }

  function handleEndSession() {
    setIsEnding(true)
    stopAudio()
    stopCamera()
    setIsMicActive(false)
    sendMessage({ type: 'end_session' })
    setTranscript((prev) => [...prev, {
      role: 'assistant',
      text: 'Generating session outputs...',
      id: Date.now(),
    }])
  }

  const statusColor = {
    connecting: 'text-yellow-400',
    connected: 'text-green-400',
    disconnected: 'text-red-400',
  }[connectionState] ?? 'text-gray-400'

  return (
    <div className="h-full flex flex-col lg:flex-row gap-0 overflow-hidden">
      {/* Left panel: camera + controls */}
      <div className="lg:w-96 xl:w-[420px] flex flex-col gap-4 p-4 border-b lg:border-b-0 lg:border-r border-gray-700 shrink-0">
        <CameraFeed
          isActive={isCameraActive}
          onToggle={handleCameraToggle}
          stream={cameraStream}
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
            <div className="text-center text-gray-600 mt-16">
              <p className="text-lg">Session started</p>
              <p className="text-sm mt-1">Enable mic to begin conversation</p>
            </div>
          )}
          {transcript.map((entry) => (
            <div
              key={entry.id}
              className={`flex ${entry.role === 'user' ? 'justify-end' : 'justify-start'}`}
            >
              <div
                className={`max-w-[85%] rounded-2xl px-4 py-3 text-sm leading-relaxed ${
                  entry.role === 'user'
                    ? 'bg-blue-600 text-white rounded-br-sm'
                    : entry.role === 'tool'
                    ? 'bg-gray-700 text-gray-300 font-mono text-xs rounded-bl-sm border border-gray-600'
                    : 'bg-gray-800 text-gray-100 rounded-bl-sm'
                }`}
              >
                {entry.role !== 'user' && (
                  <div className="text-xs text-gray-500 mb-1 font-medium uppercase tracking-wide">
                    {entry.role === 'tool' ? 'Tool' : 'TechLens'}
                  </div>
                )}
                {entry.text}
              </div>
            </div>
          ))}
          <div ref={transcriptEndRef} />
        </div>
      </div>
    </div>
  )
}
