import { useState } from 'react'
import SessionStart from './components/SessionStart'
import LiveSession from './components/LiveSession'
import SessionOutputs from './components/SessionOutputs'

export default function App() {
  const [phase, setPhase] = useState('setup') // 'setup' | 'active' | 'review'
  const [sessionData, setSessionData] = useState({
    vehicle: null,
    roNumber: '',
    customerConcern: '',
    outputs: null,
  })

  function handleStartSession(formData) {
    setSessionData((prev) => ({
      ...prev,
      vehicle: {
        year: formData.year,
        make: formData.make,
        model: formData.model,
      },
      roNumber: formData.roNumber,
      customerConcern: formData.customerConcern,
    }))
    setPhase('active')
  }

  function handleEndSession(outputs) {
    setSessionData((prev) => ({ ...prev, outputs }))
    setPhase('review')
  }

  function handleNewSession() {
    setSessionData({ vehicle: null, roNumber: '', customerConcern: '', outputs: null })
    setPhase('setup')
  }

  return (
    <div className="min-h-screen bg-gray-900 text-white flex flex-col">
      {/* Header */}
      <header className="bg-gray-800 border-b border-gray-700 px-6 py-3 flex items-center justify-between shrink-0">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 bg-blue-500 rounded-lg flex items-center justify-center font-bold text-sm">
            TL
          </div>
          <span className="text-xl font-semibold tracking-wide">TechLens</span>
          <span className="text-gray-500 text-sm hidden sm:inline">AI Diagnostic Assistant</span>
        </div>
        {sessionData.roNumber && (
          <div className="text-sm text-gray-400">
            RO: <span className="text-white font-mono">{sessionData.roNumber}</span>
          </div>
        )}
        {sessionData.vehicle && (
          <div className="text-sm text-gray-400 hidden md:block">
            {sessionData.vehicle.year} {sessionData.vehicle.make} {sessionData.vehicle.model}
          </div>
        )}
      </header>

      {/* Main content */}
      <main className="flex-1 overflow-hidden">
        {phase === 'setup' && (
          <SessionStart onStart={handleStartSession} />
        )}
        {phase === 'active' && (
          <LiveSession
            sessionData={sessionData}
            onEnd={handleEndSession}
          />
        )}
        {phase === 'review' && (
          <SessionOutputs
            outputs={sessionData.outputs}
            onNewSession={handleNewSession}
          />
        )}
      </main>
    </div>
  )
}
