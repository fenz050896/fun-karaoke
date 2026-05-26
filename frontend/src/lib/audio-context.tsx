'use client'

import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { useRouter } from 'next/navigation'
import { getTrack, getInstrumentalUrl, getFullAudioUrl, getQueue, removeFromQueue } from '@/lib/api'

type LyricLine = { start: number; text: string }

type Track = {
  videoId: string
  title: string
  artist: string
  status: string
  lyrics: LyricLine[]
  mode?: string
  saved?: boolean
}

type PlaybackMode = 'karaoke' | 'full'

interface AudioContextValue {
  videoId: string | null
  track: Track | null
  playbackMode: PlaybackMode
  isPlaying: boolean
  currentTime: number
  duration: number
  loading: boolean
  error: string | null
  playTrack: (videoId: string, mode?: PlaybackMode) => void
  setMode: (mode: PlaybackMode) => void
  togglePlay: () => void
  seek: (time: number) => void
}

const AudioCtx = createContext<AudioContextValue | null>(null)

function getCtx(): AudioContext {
  if (typeof window === 'undefined') throw new Error('AudioContext not available')
  const ctx = new AudioContext()
  // Resume if suspended (autoplay policy). This must happen inside a user gesture.
  if (ctx.state === 'suspended') ctx.resume()
  return ctx
}

export function AudioProvider({ children }: { children: ReactNode }) {
  const router = useRouter()

  // Web Audio refs
  const ctxRef = useRef<AudioContext | null>(null)
  const karaokeBufferRef = useRef<AudioBuffer | null>(null)
  const fullBufferRef = useRef<AudioBuffer | null>(null)
  const karaokeSourceRef = useRef<AudioBufferSourceNode | null>(null)
  const fullSourceRef = useRef<AudioBufferSourceNode | null>(null)
  const karaokeGainRef = useRef<GainNode | null>(null)
  const fullGainRef = useRef<GainNode | null>(null)
  const startTimeRef = useRef(0) // AudioContext.currentTime when playback started
  const startOffsetRef = useRef(0) // seek offset at start
  const modeRef = useRef<PlaybackMode>('karaoke')
  const isPlayingRef = useRef(false)
  const endedGuardRef = useRef(false)
  const tickRef = useRef<ReturnType<typeof setInterval> | null>(null)

  // React state
  const [videoId, setVideoId] = useState<string | null>(null)
  const [track, setTrack] = useState<Track | null>(null)
  const [playbackMode, setPlaybackMode] = useState<PlaybackMode>('karaoke')
  const [isPlaying, setIsPlaying] = useState(false)
  const [currentTime, setCurrentTime] = useState(0)
  const [duration, setDuration] = useState(0)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const videoIdRef = useRef(videoId)
  videoIdRef.current = videoId
  const loadingIdRef = useRef<string | null>(null)

  // ---- internal helpers ----

  const ensureCtx = useCallback((): AudioContext => {
    if (!ctxRef.current || ctxRef.current.state === 'closed') {
      ctxRef.current = getCtx()
    }
    return ctxRef.current
  }, [])

  const stopSources = useCallback(() => {
    try { karaokeSourceRef.current?.stop() } catch { /* already stopped */ }
    try { fullSourceRef.current?.stop() } catch { /* already stopped */ }
    try { karaokeSourceRef.current?.disconnect() } catch { /* already disconnected */ }
    try { fullSourceRef.current?.disconnect() } catch { /* already disconnected */ }
    karaokeSourceRef.current = null
    fullSourceRef.current = null
  }, [])

  const createSources = useCallback((offset: number) => {
    const ctx = ctxRef.current
    const kBuf = karaokeBufferRef.current
    const fBuf = fullBufferRef.current
    if (!ctx || !kBuf || !fBuf) return

    // Create gain nodes on first run
    if (!karaokeGainRef.current) {
      karaokeGainRef.current = ctx.createGain()
      karaokeGainRef.current.connect(ctx.destination)
    }
    if (!fullGainRef.current) {
      fullGainRef.current = ctx.createGain()
      fullGainRef.current.connect(ctx.destination)
    }

    // Apply current mode gains
    karaokeGainRef.current.gain.value = modeRef.current === 'karaoke' ? 1 : 0
    fullGainRef.current.gain.value = modeRef.current === 'full' ? 1 : 0

    // Create source nodes
    const kSrc = ctx.createBufferSource()
    kSrc.buffer = kBuf
    kSrc.connect(karaokeGainRef.current!)
    karaokeSourceRef.current = kSrc

    const fSrc = ctx.createBufferSource()
    fSrc.buffer = fBuf
    fSrc.connect(fullGainRef.current!)
    fullSourceRef.current = fSrc

    // Both start at same time with same offset — perfect sync via AudioContext clock
    const now = ctx.currentTime
    kSrc.start(now, offset)
    fSrc.start(now, offset)

    startTimeRef.current = now
    startOffsetRef.current = offset
  }, [])

  const startTick = useCallback(() => {
    if (tickRef.current) clearInterval(tickRef.current)
    tickRef.current = setInterval(() => {
      const ctx = ctxRef.current
      if (!ctx || ctx.state === 'closed') {
        if (tickRef.current) { clearInterval(tickRef.current); tickRef.current = null }
        return
      }

      // Auto-detect external suspend (tab background)
      if (ctx.state === 'suspended' && isPlayingRef.current) {
        setIsPlaying(false)
        isPlayingRef.current = false
        if (tickRef.current) { clearInterval(tickRef.current); tickRef.current = null }
        return
      }

      if (!isPlayingRef.current) return

      const t = startOffsetRef.current + (ctx.currentTime - startTimeRef.current)
      setCurrentTime(t)

      // Check ended
      const dur = karaokeBufferRef.current?.duration
      if (dur && t >= dur && !endedGuardRef.current) {
        endedGuardRef.current = true
        setIsPlaying(false)
        isPlayingRef.current = false
        stopSources()
        if (tickRef.current) { clearInterval(tickRef.current); tickRef.current = null }

        const vid = videoIdRef.current
        if (vid) {
          removeFromQueue(vid).then(() =>
            getQueue().then(data => {
              const queue: { videoId: string }[] = data.queue || []
              if (queue.length > 0) {
                router.push(`/karaoke/${queue[0].videoId}?mode=${modeRef.current}`)
              }
            })
          ).catch(err => console.error('Auto-advance failed:', err))
        }
      }
    }, 100)
  }, [stopSources, router])

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (tickRef.current) { clearInterval(tickRef.current); tickRef.current = null }
      stopSources()
      ctxRef.current?.close()
    }
  }, [stopSources])

  // ---- public API ----

  const playTrack = useCallback(async (vid: string, mode?: PlaybackMode) => {
    if (loadingIdRef.current === vid) return

    // Same track — resume
    if (vid === videoIdRef.current && karaokeBufferRef.current) {
      const ctx = ensureCtx()
      if (ctx.state === 'suspended') ctx.resume()
      if (isPlayingRef.current) return // already playing

      // Recreate sources from current offset
      stopSources()
      createSources(startOffsetRef.current)
      isPlayingRef.current = true
      setIsPlaying(true)
      startTick()
      return
    }

    loadingIdRef.current = vid
    videoIdRef.current = vid

    stopSources()
    endedGuardRef.current = false
    setLoading(true)
    setError(null)

    const m = mode || 'karaoke'
    modeRef.current = m
    setPlaybackMode(m)

    try {
      const ctx = ensureCtx()
      if (ctx.state === 'suspended') await ctx.resume()

      // Fetch both audio files in parallel
      const [instResp, fullResp] = await Promise.all([
        fetch(getInstrumentalUrl(vid)),
        fetch(getFullAudioUrl(vid)),
      ])

      if (!instResp.ok || !fullResp.ok) {
        throw new Error('Failed to fetch audio files')
      }

      const [instBuf, fullBuf] = await Promise.all([
        instResp.arrayBuffer(),
        fullResp.arrayBuffer(),
      ])

      // Decode in parallel
      const [instAudio, fullAudio] = await Promise.all([
        ctx.decodeAudioData(instBuf),
        ctx.decodeAudioData(fullBuf),
      ])

      karaokeBufferRef.current = instAudio
      fullBufferRef.current = fullAudio

      setDuration(instAudio.duration)

      // Start playback
      startOffsetRef.current = 0
      createSources(0)
      isPlayingRef.current = true
      setIsPlaying(true)
      startTick()

      // Load metadata
      try {
        const data = await getTrack(vid)
        setTrack(data)
        setVideoId(vid)
        if (!mode && data.mode) {
          const trackMode = data.mode as PlaybackMode
          modeRef.current = trackMode
          setPlaybackMode(trackMode)
          // Update gains
          if (karaokeGainRef.current && fullGainRef.current) {
            karaokeGainRef.current.gain.value = trackMode === 'karaoke' ? 1 : 0
            fullGainRef.current.gain.value = trackMode === 'full' ? 1 : 0
          }
        }
      } catch {
        setError('Failed to load track metadata')
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load audio')
    } finally {
      setLoading(false)
      loadingIdRef.current = null
    }
  }, [ensureCtx, stopSources, createSources, startTick])

  const setMode = useCallback((mode: PlaybackMode) => {
    if (mode === modeRef.current) return
    if (!videoIdRef.current) return

    modeRef.current = mode
    setPlaybackMode(mode)

    // Toggle gains — instant, no seeking needed
    if (karaokeGainRef.current) {
      karaokeGainRef.current.gain.value = mode === 'karaoke' ? 1 : 0
    }
    if (fullGainRef.current) {
      fullGainRef.current.gain.value = mode === 'full' ? 1 : 0
    }
  }, [])

  const togglePlay = useCallback(() => {
    const ctx = ctxRef.current
    if (!ctx || ctx.state === 'closed') return

    if (isPlayingRef.current) {
      ctx.suspend()
      isPlayingRef.current = false
      setIsPlaying(false)
    } else {
      if (ctx.state === 'suspended') ctx.resume()
      // If no sources (first play after load, or context was closed),
      // create sources from current offset
      if (!karaokeSourceRef.current && !fullSourceRef.current) {
        if (!karaokeBufferRef.current) return
        createSources(startOffsetRef.current)
      }
      isPlayingRef.current = true
      setIsPlaying(true)
      startTick()
    }
  }, [createSources, startTick])

  const seek = useCallback((time: number) => {
    stopSources()
    startOffsetRef.current = time
    setCurrentTime(time)
    endedGuardRef.current = false // allow re-ended after seeking back

    if (isPlayingRef.current) {
      createSources(time)
      startTick()
    }
  }, [stopSources, createSources, startTick])

  const value = useMemo(() => ({
    videoId, track, playbackMode, isPlaying, currentTime, duration, loading, error,
    playTrack, setMode, togglePlay, seek,
  }), [videoId, track, playbackMode, isPlaying, currentTime, duration, loading, error,
      playTrack, setMode, togglePlay, seek])

  return (
    <AudioCtx.Provider value={value}>
      {children}
    </AudioCtx.Provider>
  )
}

export function useAudio() {
  const ctx = useContext(AudioCtx)
  if (!ctx) throw new Error('useAudio must be used within AudioProvider')
  return ctx
}
