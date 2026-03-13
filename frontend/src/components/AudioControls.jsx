export default function AudioControls({
  onMicToggle,
  isMicActive,
  isSpeakerActive,
  onSpeakerToggle,
  audioLevel = 0,
}) {
  return (
    <div className="flex items-center gap-4 bg-gray-800 rounded-xl px-5 py-3 border border-gray-700">
      {/* Mic toggle */}
      <button
        onClick={onMicToggle}
        className={`flex items-center gap-2 px-4 py-2 rounded-lg font-medium text-sm transition-colors min-h-[44px] cursor-pointer ${
          isMicActive
            ? 'bg-green-600 hover:bg-green-500 text-white'
            : 'bg-gray-700 hover:bg-gray-600 text-gray-300'
        }`}
        title={isMicActive ? 'Mute microphone' : 'Unmute microphone'}
      >
        <span className="text-lg">{isMicActive ? '🎙️' : '🔇'}</span>
        <span>{isMicActive ? 'Mic On' : 'Mic Off'}</span>
        {isMicActive && (
          <span className="w-2 h-2 rounded-full bg-green-300 animate-pulse" />
        )}
      </button>

      {/* Audio level bar */}
      <div className="flex items-end gap-0.5 h-8" title="Audio level">
        {Array.from({ length: 8 }).map((_, i) => {
          const threshold = (i + 1) / 8
          const active = isMicActive && audioLevel >= threshold
          return (
            <div
              key={i}
              className={`w-1.5 rounded-sm transition-colors ${
                active ? 'bg-green-400' : 'bg-gray-600'
              }`}
              style={{ height: `${40 + i * 8}%` }}
            />
          )
        })}
      </div>

      {/* Speaker toggle */}
      <button
        onClick={onSpeakerToggle}
        className={`flex items-center gap-2 px-4 py-2 rounded-lg font-medium text-sm transition-colors min-h-[44px] cursor-pointer ${
          isSpeakerActive
            ? 'bg-blue-600 hover:bg-blue-500 text-white'
            : 'bg-gray-700 hover:bg-gray-600 text-gray-300'
        }`}
        title={isSpeakerActive ? 'Mute speaker' : 'Unmute speaker'}
      >
        <span className="text-lg">{isSpeakerActive ? '🔊' : '🔈'}</span>
        <span>{isSpeakerActive ? 'Speaker On' : 'Speaker Off'}</span>
      </button>
    </div>
  )
}
