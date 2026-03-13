import { useEffect, useRef, useState } from 'react'
import AudioControls from './AudioControls'
import CameraFeed from './CameraFeed'
import useWebSocket from '../hooks/useWebSocket'
import useAudioStream from '../hooks/useAudioStream'
import useCameraStream from '../hooks/useCameraStream'

export default function LiveSession({ sessionData, onEnd }) {
  const [isMicActive, setIsMicActive] = useState(false)
  const [isSpeakerActive, setIsSpeakerActive] = useState(true)
  const [transcript, setTranscript] = useState([])
  const transcriptEndRef = useRef(null)

  const { sendMessage, lastMessage, connectionState } = useWebSocket('/ws/session')
  const { startCapture: startAudio, stopCapture: stopAudio, isCapturing: isAudioCapturing, audioLevel } = useAudioStream({
    onChunk: (b64) => sendMessage({ type: 'audio', data: b64 }),
  })
  const { startCapture: startCamera, stopCapture: stopCamera, isCapturing: isCameraActive, stream: cameraStream } = useCameraStream({
    onFrame: (b64) => sendMessage({ type: 'video_frame', data: b64 }),
  })

  // Start session on mount
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

  // Handle incoming messages
  useEffect(() => {
    if (!lastMessage) return
    const msg = lastMessage
    if (msg.type === 'transcript') {
      setTranscript((prev) => [...prev, { role: msg.role ?? 'assistant', text: msg.text, id: Date.now() }])
    } else if (msg.type === 'tool_result') {
      setTranscript((prev) => [...prev, { role: 'tool', text: `[Tool: ${msg.tool}] ${msg.result}`, id: Date.now() }])
    } else if (msg.type === 'session_outputs') {
      onEnd(msg.outputs)
    }
  }, [lastMessage])

  // Auto-scroll transcript
  useEffect(() => {
    transcriptEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [transcript])

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
    stopAudio()
    stopCamera()
    sendMessage({ type: 'end_session' })
    // onEnd will be called when we receive session_outputs, or immediately with null
    onEnd(null)
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
          className="w-full bg-red-700 hover:bg-red-600 active:bg-red-800 text-white font-semibold py-4 rounded-xl text-base transition-colors min-h-[56px] cursor-pointer mt-auto"
        >
          End Session
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
                    {entry.role === 'tool' ? 'Tool Result' : 'TechLens'}
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
