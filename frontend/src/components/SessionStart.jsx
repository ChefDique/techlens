import { useState } from 'react'

const YEARS = Array.from({ length: 9 }, (_, i) => 2026 - i)
const MAKES = ['Subaru']
const MODELS = {
  Subaru: ['Outback', 'Forester', 'Crosstrek'],
}

export default function SessionStart({ onStart }) {
  const [form, setForm] = useState({
    year: '2023',
    make: 'Subaru',
    model: 'Outback',
    roNumber: '',
    customerConcern: '',
  })

  function handleChange(e) {
    const { name, value } = e.target
    setForm((prev) => {
      const updated = { ...prev, [name]: value }
      // Reset model when make changes
      if (name === 'make') {
        updated.model = MODELS[value]?.[0] ?? ''
      }
      return updated
    })
  }

  function handleSubmit(e) {
    e.preventDefault()
    if (!form.roNumber.trim()) return
    onStart(form)
  }

  const selectClass =
    'w-full bg-gray-700 border border-gray-600 rounded-lg px-4 py-3 text-white text-base focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 min-h-[48px]'
  const inputClass =
    'w-full bg-gray-700 border border-gray-600 rounded-lg px-4 py-3 text-white placeholder-gray-400 text-base focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 min-h-[48px]'
  const labelClass = 'block text-sm font-medium text-gray-300 mb-2'

  return (
    <div className="flex items-center justify-center min-h-full p-6">
      <div className="w-full max-w-lg">
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold text-white mb-2">New Diagnostic Session</h1>
          <p className="text-gray-400">Enter vehicle information to begin</p>
        </div>

        <form onSubmit={handleSubmit} className="bg-gray-800 rounded-2xl p-8 space-y-6 border border-gray-700">
          {/* Vehicle row */}
          <div className="grid grid-cols-3 gap-4">
            <div>
              <label className={labelClass}>Year</label>
              <select name="year" value={form.year} onChange={handleChange} className={selectClass}>
                {YEARS.map((y) => (
                  <option key={y} value={y}>{y}</option>
                ))}
              </select>
            </div>
            <div>
              <label className={labelClass}>Make</label>
              <select name="make" value={form.make} onChange={handleChange} className={selectClass}>
                {MAKES.map((m) => (
                  <option key={m} value={m}>{m}</option>
                ))}
              </select>
            </div>
            <div>
              <label className={labelClass}>Model</label>
              <select name="model" value={form.model} onChange={handleChange} className={selectClass}>
                {(MODELS[form.make] ?? []).map((m) => (
                  <option key={m} value={m}>{m}</option>
                ))}
              </select>
            </div>
          </div>

          {/* RO Number */}
          <div>
            <label className={labelClass}>
              RO Number <span className="text-red-400">*</span>
            </label>
            <input
              type="text"
              name="roNumber"
              value={form.roNumber}
              onChange={handleChange}
              placeholder="e.g. RO-2024-001"
              className={inputClass}
              required
            />
          </div>

          {/* Customer Concern */}
          <div>
            <label className={labelClass}>Customer Concern</label>
            <textarea
              name="customerConcern"
              value={form.customerConcern}
              onChange={handleChange}
              placeholder="Describe the customer's complaint or concern..."
              rows={4}
              className={`${inputClass} resize-none min-h-0`}
            />
          </div>

          <button
            type="submit"
            className="w-full bg-blue-600 hover:bg-blue-500 active:bg-blue-700 text-white font-semibold py-4 px-6 rounded-xl text-lg transition-colors min-h-[56px] cursor-pointer"
          >
            Start Session
          </button>
        </form>
      </div>
    </div>
  )
}
