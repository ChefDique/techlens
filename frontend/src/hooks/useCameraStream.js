import { useCallback, useEffect, useRef, useState } from 'react'

const DEFAULT_FPS = 1
const JPEG_QUALITY = 0.7

export default function useCameraStream({ onFrame, fps = DEFAULT_FPS } = {}) {
  const [isCapturing, setIsCapturing] = useState(false)
  const [currentFrame, setCurrentFrame] = useState(null)
  const [stream, setStream] = useState(null)
  const streamRef = useRef(null)
  const intervalRef = useRef(null)
  const canvasRef = useRef(null)
  const videoRef = useRef(null)

  // Lazy-init canvas
  function getCanvas() {
    if (!canvasRef.current) {
      canvasRef.current = document.createElement('canvas')
    }
    return canvasRef.current
  }

  // Lazy-init offscreen video element for frame capture
  function getVideo() {
    if (!videoRef.current) {
      videoRef.current = document.createElement('video')
      videoRef.current.muted = true
      videoRef.current.playsInline = true
    }
    return videoRef.current
  }

  const startCapture = useCallback(async () => {
    if (isCapturing) return
    try {
      const mediaStream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: 'environment', width: { ideal: 1280 }, height: { ideal: 720 } },
      })
      streamRef.current = mediaStream
      setStream(mediaStream)

      const video = getVideo()
      video.srcObject = mediaStream
      await video.play()

      const canvas = getCanvas()
      canvas.width = video.videoWidth || 1280
      canvas.height = video.videoHeight || 720

      intervalRef.current = setInterval(() => {
        if (!video.videoWidth) return
        canvas.width = video.videoWidth
        canvas.height = video.videoHeight
        const ctx = canvas.getContext('2d')
        ctx.drawImage(video, 0, 0)
        const dataUrl = canvas.toDataURL('image/jpeg', JPEG_QUALITY)
        const b64 = dataUrl.split(',')[1]
        setCurrentFrame(dataUrl)
        onFrame?.(b64)
      }, 1000 / fps)

      setIsCapturing(true)
    } catch (err) {
      console.error('useCameraStream: failed to start capture', err)
    }
  }, [isCapturing, onFrame, fps])

  const stopCapture = useCallback(() => {
    clearInterval(intervalRef.current)
    streamRef.current?.getTracks().forEach((t) => t.stop())
    const video = videoRef.current
    if (video) {
      video.srcObject = null
    }
    streamRef.current = null
    setStream(null)
    setIsCapturing(false)
    setCurrentFrame(null)
  }, [])

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      clearInterval(intervalRef.current)
      streamRef.current?.getTracks().forEach((t) => t.stop())
    }
  }, [])

  return { startCapture, stopCapture, isCapturing, currentFrame, stream }
}
