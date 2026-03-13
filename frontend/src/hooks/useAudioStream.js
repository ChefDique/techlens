import { useCallback, useRef, useState } from 'react'

const SAMPLE_RATE = 16000
const CHUNK_INTERVAL_MS = 250

function float32ToInt16(float32Array) {
  const int16 = new Int16Array(float32Array.length)
  for (let i = 0; i < float32Array.length; i++) {
    const s = Math.max(-1, Math.min(1, float32Array[i]))
    int16[i] = s < 0 ? s * 0x8000 : s * 0x7fff
  }
  return int16
}

function int16ToBase64(int16Array) {
  const bytes = new Uint8Array(int16Array.buffer)
  let binary = ''
  for (let i = 0; i < bytes.length; i++) {
    binary += String.fromCharCode(bytes[i])
  }
  return btoa(binary)
}

export default function useAudioStream({ onChunk } = {}) {
  const [isCapturing, setIsCapturing] = useState(false)
  const [audioLevel, setAudioLevel] = useState(0)
  const streamRef = useRef(null)
  const contextRef = useRef(null)
  const processorRef = useRef(null)
  const bufferRef = useRef([])
  const timerRef = useRef(null)

  const startCapture = useCallback(async () => {
    if (isCapturing) return
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: { sampleRate: SAMPLE_RATE, channelCount: 1, echoCancellation: true },
      })
      streamRef.current = stream

      const ctx = new AudioContext({ sampleRate: SAMPLE_RATE })
      contextRef.current = ctx

      const source = ctx.createMediaStreamSource(stream)
      const processor = ctx.createScriptProcessor(4096, 1, 1)
      processorRef.current = processor

      processor.onaudioprocess = (e) => {
        const channelData = e.inputBuffer.getChannelData(0)
        bufferRef.current.push(new Float32Array(channelData))

        // Calculate RMS for audio level
        let sum = 0
        for (let i = 0; i < channelData.length; i++) {
          sum += channelData[i] * channelData[i]
        }
        const rms = Math.sqrt(sum / channelData.length)
        setAudioLevel(Math.min(1, rms * 8))
      }

      source.connect(processor)
      processor.connect(ctx.destination)

      // Flush buffer on interval
      timerRef.current = setInterval(() => {
        if (bufferRef.current.length === 0) return
        const combined = new Float32Array(
          bufferRef.current.reduce((acc, arr) => acc + arr.length, 0)
        )
        let offset = 0
        for (const chunk of bufferRef.current) {
          combined.set(chunk, offset)
          offset += chunk.length
        }
        bufferRef.current = []
        const int16 = float32ToInt16(combined)
        const b64 = int16ToBase64(int16)
        onChunk?.(b64)
      }, CHUNK_INTERVAL_MS)

      setIsCapturing(true)
    } catch (err) {
      console.error('useAudioStream: failed to start capture', err)
    }
  }, [isCapturing, onChunk])

  const stopCapture = useCallback(() => {
    clearInterval(timerRef.current)
    processorRef.current?.disconnect()
    contextRef.current?.close()
    streamRef.current?.getTracks().forEach((t) => t.stop())
    bufferRef.current = []
    processorRef.current = null
    contextRef.current = null
    streamRef.current = null
    setIsCapturing(false)
    setAudioLevel(0)
  }, [])

  return { startCapture, stopCapture, isCapturing, audioLevel }
}
