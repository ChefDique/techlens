import { useEffect, useRef } from 'react'

export default function CameraFeed({ isActive, onToggle, stream, autoStopSeconds = null }) {
  const videoRef = useRef(null)

  useEffect(() => {
    if (videoRef.current && stream) {
      videoRef.current.srcObject = stream
      videoRef.current.play().catch(() => {})
    } else if (videoRef.current) {
      videoRef.current.srcObject = null
    }
  }, [stream])

  return (
    <div className="bg-gray-900 rounded-xl overflow-hidden border border-gray-700 flex flex-col">
      {/* Video area */}
      <div className="relative bg-black aspect-video flex items-center justify-center">
        {isActive && stream ? (
          <video
            ref={videoRef}
            autoPlay
            muted
            playsInline
            className="w-full h-full object-cover"
          />
        ) : (
          <div className="text-center text-gray-500">
            <div className="text-5xl mb-3">📷</div>
            <p className="text-sm">Camera off</p>
          </div>
        )}

        {/* Status badge */}
        {isActive && (
          <div className="absolute top-3 left-3 flex items-center gap-1.5 bg-black/60 px-2.5 py-1 rounded-full text-xs text-green-400">
            <span className="w-1.5 h-1.5 rounded-full bg-green-400 animate-pulse" />
            LIVE
          </div>
        )}
        {isActive && autoStopSeconds !== null && (
          <div className="absolute top-3 right-3 bg-black/60 px-2.5 py-1 rounded-full text-xs text-yellow-400 font-mono">
            {autoStopSeconds}s
          </div>
        )}
      </div>

      {/* Controls */}
      <div className="px-4 py-3 flex items-center justify-between">
        <span className="text-xs text-gray-400">Camera Feed</span>
        <button
          onClick={onToggle}
          className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors min-h-[40px] cursor-pointer ${
            isActive
              ? 'bg-red-700 hover:bg-red-600 text-white'
              : 'bg-blue-600 hover:bg-blue-500 text-white'
          }`}
        >
          {isActive ? 'Stop Camera' : 'Start Camera'}
        </button>
      </div>
    </div>
  )
}
