import { useState } from 'react'

const TABS = [
  { key: 'tech_notes', label: 'Tech Notes' },
  { key: 'customer_summary', label: 'Customer Summary' },
  { key: 'escalation_brief', label: 'Escalation Brief' },
]

export default function SessionOutputs({ outputs, onNewSession }) {
  const [activeTab, setActiveTab] = useState('tech_notes')
  const [copied, setCopied] = useState(false)

  const content = outputs?.[activeTab] ?? null

  async function handleCopy() {
    if (!content) return
    try {
      await navigator.clipboard.writeText(content)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch {
      // Fallback for older browsers
      const textarea = document.createElement('textarea')
      textarea.value = content
      document.body.appendChild(textarea)
      textarea.select()
      document.execCommand('copy')
      document.body.removeChild(textarea)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    }
  }

  return (
    <div className="flex flex-col h-full overflow-hidden">
      {/* Tab bar */}
      <div className="border-b border-gray-700 px-4 pt-4 shrink-0 flex items-end justify-between">
        <div className="flex gap-1">
          {TABS.map((tab) => (
            <button
              key={tab.key}
              onClick={() => { setActiveTab(tab.key); setCopied(false) }}
              className={`px-5 py-2.5 rounded-t-lg text-sm font-medium transition-colors cursor-pointer ${
                activeTab === tab.key
                  ? 'bg-gray-800 text-white border border-b-0 border-gray-700'
                  : 'text-gray-400 hover:text-gray-200'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>

        <div className="flex gap-2 pb-1">
          <button
            onClick={handleCopy}
            disabled={!content}
            className="px-4 py-2 bg-gray-700 hover:bg-gray-600 disabled:opacity-40 disabled:cursor-not-allowed text-gray-200 text-sm rounded-lg transition-colors cursor-pointer min-w-[90px]"
          >
            {copied ? 'Copied!' : 'Copy'}
          </button>
          <button
            onClick={onNewSession}
            className="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white text-sm font-medium rounded-lg transition-colors cursor-pointer"
          >
            New Session
          </button>
        </div>
      </div>

      {/* Content area */}
      <div className="flex-1 overflow-y-auto p-6">
        {content ? (
          <div className="max-w-3xl mx-auto">
            <pre className="whitespace-pre-wrap font-sans text-gray-100 text-sm leading-relaxed bg-gray-800 rounded-xl p-6 border border-gray-700">
              {content}
            </pre>
          </div>
        ) : (
          <div className="flex flex-col items-center justify-center h-full text-gray-600">
            <p className="text-lg">No {TABS.find((t) => t.key === activeTab)?.label} generated</p>
            <p className="text-sm mt-1">This document was not produced in this session</p>
          </div>
        )}
      </div>
    </div>
  )
}
