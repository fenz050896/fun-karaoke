'use client'

import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { useRouter } from 'next/navigation'
import { getTrack, getInstrumentalUrl, getVocalsUrl, getQueue, removeFromQueue } from '@/lib/api'

type LyricLine = { start: number; text: string }

type Track = {
  videoId: string
  title: string
  artist: string
  status: string
  lyrics: LyricLine[]
  lyricsSource?: 'lrclib' | 'whisper' | 'none'
  lyricsStatus?: 'synced' | 'generated' | 'unavailable'
  lyricsWarning?: string
  lyricsMatch?: {
    id?: number
    strategy: 'exact' | 'search'
    trackName: string
    artistName: string
    duration: number
    durationDelta: number
  }
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
  audioLoading: boolean
  error: string | null
  audioError: string | null
  playTrack: (videoId: string, mode?: PlaybackMode) => void
  reloadTrackMetadata: (videoId: string) => Promise<void>
  setMode: (mode: PlaybackMode) => void
  togglePlay: () => void
  seek: (time: number) => void
}

const AudioCtx = createContext<AudioContextValue | null>(null)
const MASTER_GAIN = 0.95
const MODE_FADE_SECONDS = 0.04
const DRIFT_CHECK_MS = 1000
const DRIFT_CORRECTION_SECONDS = 0.1

function getCtx(): AudioContext {
  if (typeof window === 'undefined') throw new Error('AudioContext not available')
  return new AudioContext()
}

function waitForMediaEvent(
  media: HTMLMediaElement,
  eventName: 'loadedmetadata' | 'canplay' | 'seeked',
  isReady: () => boolean,
  timeoutMs: number = 30000,
) {
  if (media.error) return Promise.reject(new Error('Audio stream could not be loaded.'))
  if (isReady()) return Promise.resolve()

  return new Promise<void>((resolve, reject) => {
    const cleanup = () => {
      window.clearTimeout(timeoutId)
      media.removeEventListener(eventName, handleReady)
      media.removeEventListener('error', handleError)
    }
    const handleReady = () => {
      cleanup()
      resolve()
    }
    const handleError = () => {
      cleanup()
      reject(new Error('Audio stream could not be loaded.'))
    }
    const timeoutId = window.setTimeout(() => {
      cleanup()
      reject(new Error('Audio stream timed out.'))
    }, timeoutMs)

    media.addEventListener(eventName, handleReady, { once: true })
    media.addEventListener('error', handleError, { once: true })
  })
}

function isAutoplayBlock(error: unknown) {
  return error instanceof DOMException && error.name === 'NotAllowedError'
}

export function AudioProvider({ children }: { children: ReactNode }) {
  const router = useRouter()

  const ctxRef = useRef<AudioContext | null>(null)
  const instrumentalRef = useRef<HTMLAudioElement | null>(null)
  const vocalsRef = useRef<HTMLAudioElement | null>(null)
  const instrumentalSourceRef = useRef<MediaElementAudioSourceNode | null>(null)
  const vocalsSourceRef = useRef<MediaElementAudioSourceNode | null>(null)
  const instrumentalGainRef = useRef<GainNode | null>(null)
  const vocalsGainRef = useRef<GainNode | null>(null)
  const masterGainRef = useRef<GainNode | null>(null)
  const modeRef = useRef<PlaybackMode>('karaoke')
  const isPlayingRef = useRef(false)
  const wantsPlaybackRef = useRef(false)
  const endedGuardRef = useRef(false)
  const seekingRef = useRef(false)
  const seekTokenRef = useRef(0)
  const loadTokenRef = useRef(0)
  const playTokenRef = useRef(0)
  const playPendingRef = useRef(false)
  const tickRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const driftRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const [videoId, setVideoId] = useState<string | null>(null)
  const [track, setTrack] = useState<Track | null>(null)
  const [playbackMode, setPlaybackMode] = useState<PlaybackMode>('karaoke')
  const [isPlaying, setIsPlaying] = useState(false)
  const [currentTime, setCurrentTime] = useState(0)
  const [duration, setDuration] = useState(0)
  const [loading, setLoading] = useState(false)
  const [audioLoading, setAudioLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [audioError, setAudioError] = useState<string | null>(null)

  const videoIdRef = useRef(videoId)
  const loadingIdRef = useRef<string | null>(null)

  const ensureAudioGraph = useCallback(() => {
    if (ctxRef.current && ctxRef.current.state !== 'closed') return ctxRef.current

    const ctx = getCtx()
    const instrumental = new Audio()
    const vocals = new Audio()

    for (const media of [instrumental, vocals]) {
      media.crossOrigin = 'anonymous'
      media.preload = 'auto'
      media.setAttribute('playsinline', '')
    }

    const instrumentalSource = ctx.createMediaElementSource(instrumental)
    const vocalsSource = ctx.createMediaElementSource(vocals)
    const instrumentalGain = ctx.createGain()
    const vocalsGain = ctx.createGain()
    const masterGain = ctx.createGain()

    instrumentalSource.connect(instrumentalGain)
    vocalsSource.connect(vocalsGain)
    instrumentalGain.connect(masterGain)
    vocalsGain.connect(masterGain)
    masterGain.connect(ctx.destination)

    instrumentalGain.gain.value = 1
    vocalsGain.gain.value = modeRef.current === 'full' ? 1 : 0
    masterGain.gain.value = MASTER_GAIN

    ctxRef.current = ctx
    instrumentalRef.current = instrumental
    vocalsRef.current = vocals
    instrumentalSourceRef.current = instrumentalSource
    vocalsSourceRef.current = vocalsSource
    instrumentalGainRef.current = instrumentalGain
    vocalsGainRef.current = vocalsGain
    masterGainRef.current = masterGain

    return ctx
  }, [])

  const clearTimers = useCallback(() => {
    if (tickRef.current) {
      clearInterval(tickRef.current)
      tickRef.current = null
    }
    if (driftRef.current) {
      clearInterval(driftRef.current)
      driftRef.current = null
    }
  }, [])

  const pauseBoth = useCallback(() => {
    instrumentalRef.current?.pause()
    vocalsRef.current?.pause()
  }, [])

  const setVocalGain = useCallback((value: number, immediate: boolean = false) => {
    const ctx = ctxRef.current
    const gain = vocalsGainRef.current?.gain
    if (!ctx || !gain) return

    const now = ctx.currentTime
    gain.cancelScheduledValues(now)
    gain.setValueAtTime(gain.value, now)
    if (immediate) {
      gain.setValueAtTime(value, now)
    } else {
      gain.linearRampToValueAtTime(value, now + MODE_FADE_SECONDS)
    }
  }, [])

  const alignVocals = useCallback(() => {
    const instrumental = instrumentalRef.current
    const vocals = vocalsRef.current
    if (!instrumental || !vocals || vocals.seeking || !Number.isFinite(instrumental.currentTime)) return

    const drift = Math.abs(vocals.currentTime - instrumental.currentTime)
    if (drift > DRIFT_CORRECTION_SECONDS) {
      setVocalGain(0, true)
      vocals.currentTime = instrumental.currentTime
    }
  }, [setVocalGain])

  const setPaused = useCallback(() => {
    playTokenRef.current += 1
    playPendingRef.current = false
    wantsPlaybackRef.current = false
    isPlayingRef.current = false
    seekingRef.current = false
    seekTokenRef.current += 1
    pauseBoth()
    clearTimers()
    setIsPlaying(false)
    setAudioLoading(false)
  }, [clearTimers, pauseBoth])

  const resetPlayback = useCallback(() => {
    setPaused()
    setVocalGain(0, true)
  }, [setPaused, setVocalGain])

  const advanceQueue = useCallback(() => {
    if (endedGuardRef.current) return
    endedGuardRef.current = true
    resetPlayback()

    const currentVideoId = videoIdRef.current
    const loadToken = loadTokenRef.current
    if (!currentVideoId) return

    removeFromQueue(currentVideoId).then(() =>
      getQueue().then(data => {
        if (loadTokenRef.current !== loadToken) return
        const queue: { videoId: string }[] = data.queue || []
        if (queue.length > 0) {
          router.push(`/karaoke/${queue[0].videoId}?mode=${modeRef.current}`)
        }
      })
    ).catch(err => console.error('Auto-advance failed:', err))
  }, [resetPlayback, router])

  const startTimers = useCallback(() => {
    clearTimers()
    tickRef.current = setInterval(() => {
      const instrumental = instrumentalRef.current
      if (!instrumental) return
      setCurrentTime(instrumental.currentTime || 0)
    }, 100)

    driftRef.current = setInterval(() => {
      if (!isPlayingRef.current || seekingRef.current || modeRef.current !== 'full') return
      alignVocals()
    }, DRIFT_CHECK_MS)
  }, [alignVocals, clearTimers])

  const playBoth = useCallback(async (autoplay: boolean = false) => {
    if (playPendingRef.current) return false
    const instrumental = instrumentalRef.current
    const vocals = vocalsRef.current
    if (!instrumental || !vocals || !instrumental.src || !vocals.src ||
        instrumental.readyState < HTMLMediaElement.HAVE_METADATA ||
        vocals.readyState < HTMLMediaElement.HAVE_METADATA) return false

    const token = ++playTokenRef.current
    playPendingRef.current = true
    wantsPlaybackRef.current = true
    setAudioLoading(true)

    try {
      alignVocals()
      const ctx = ensureAudioGraph()
      // Start both media elements while the user gesture is still active.
      const resume = ctx.state === 'suspended' ? ctx.resume() : Promise.resolve()
      setVocalGain(0, true)
      const vocalsPlay = vocals.play()
      const instrumentalPlay = instrumental.play()
      const vocalsReady = vocalsPlay.catch(error => {
        if (modeRef.current === 'full') throw error
      })
      await Promise.all([resume, instrumentalPlay, vocalsReady])
      if (playTokenRef.current !== token) return false

      wantsPlaybackRef.current = true
      isPlayingRef.current = true
      if (modeRef.current === 'full' && vocals.readyState >= HTMLMediaElement.HAVE_CURRENT_DATA) {
        alignVocals()
        if (!vocals.paused && !vocals.seeking) setVocalGain(1)
      }
      setIsPlaying(true)
      setAudioLoading(false)
      setAudioError(null)
      startTimers()
      return true
    } catch (playError) {
      if (playTokenRef.current !== token) return false
      pauseBoth()
      isPlayingRef.current = false
      setIsPlaying(false)
      clearTimers()
      wantsPlaybackRef.current = false
      setAudioLoading(false)
      if (!autoplay || !isAutoplayBlock(playError)) {
        setAudioError(playError instanceof Error ? playError.message : 'Audio playback failed.')
      }
      return false
    } finally {
      if (playTokenRef.current === token) playPendingRef.current = false
    }
  }, [alignVocals, clearTimers, ensureAudioGraph, pauseBoth, setVocalGain, startTimers])

  useEffect(() => {
    ensureAudioGraph()
    const instrumental = instrumentalRef.current
    const vocals = vocalsRef.current
    if (!instrumental || !vocals) return

    const handleEnded = () => {
      if (seekingRef.current) return
      advanceQueue()
    }
    const handleInstrumentalWaiting = () => {
      if (!wantsPlaybackRef.current || seekingRef.current || playPendingRef.current) return
      setAudioLoading(true)
      isPlayingRef.current = false
      setIsPlaying(false)
      clearTimers()
      pauseBoth()
    }
    const handleInstrumentalCanPlay = () => {
      if (!wantsPlaybackRef.current || seekingRef.current || playPendingRef.current || !instrumental.paused) return
      void playBoth()
    }
    const handleVocalsWaiting = () => {
      if (modeRef.current === 'full') setVocalGain(0)
    }
    const handleVocalsSeeked = () => {
      if (modeRef.current !== 'full' || !wantsPlaybackRef.current || !isPlayingRef.current || vocals.paused || seekingRef.current) return
      if (vocals.readyState >= HTMLMediaElement.HAVE_CURRENT_DATA) setVocalGain(1)
    }
    const handleVocalsCanPlay = () => {
      if (modeRef.current !== 'full' || !wantsPlaybackRef.current || !isPlayingRef.current || vocals.readyState < HTMLMediaElement.HAVE_CURRENT_DATA) return
      const token = playTokenRef.current
      alignVocals()
      void vocals.play().then(() => {
        if (playTokenRef.current === token && modeRef.current === 'full' && !vocals.seeking) setVocalGain(1)
      }).catch(() => undefined)
    }
    const handleInstrumentalError = () => {
      if (!instrumental.src) return
      setAudioError('Instrumental stream could not be loaded.')
      resetPlayback()
    }
    const handleVocalsError = () => {
      if (modeRef.current === 'full' && vocals.src) {
        setAudioError('Vocals stream could not be loaded.')
        resetPlayback()
      }
    }

    instrumental.addEventListener('ended', handleEnded)
    instrumental.addEventListener('waiting', handleInstrumentalWaiting)
    instrumental.addEventListener('canplay', handleInstrumentalCanPlay)
    instrumental.addEventListener('error', handleInstrumentalError)
    vocals.addEventListener('waiting', handleVocalsWaiting)
    vocals.addEventListener('seeked', handleVocalsSeeked)
    vocals.addEventListener('canplay', handleVocalsCanPlay)
    vocals.addEventListener('error', handleVocalsError)

    return () => {
      loadTokenRef.current += 1
      loadingIdRef.current = null
      setPaused()
      instrumental.removeEventListener('ended', handleEnded)
      instrumental.removeEventListener('waiting', handleInstrumentalWaiting)
      instrumental.removeEventListener('canplay', handleInstrumentalCanPlay)
      instrumental.removeEventListener('error', handleInstrumentalError)
      vocals.removeEventListener('waiting', handleVocalsWaiting)
      vocals.removeEventListener('seeked', handleVocalsSeeked)
      vocals.removeEventListener('canplay', handleVocalsCanPlay)
      vocals.removeEventListener('error', handleVocalsError)
      pauseBoth()
      for (const media of [instrumental, vocals]) {
        media.removeAttribute('src')
        media.load()
      }
      instrumentalSourceRef.current?.disconnect()
      vocalsSourceRef.current?.disconnect()
      instrumentalGainRef.current?.disconnect()
      vocalsGainRef.current?.disconnect()
      masterGainRef.current?.disconnect()
      void ctxRef.current?.close()
      ctxRef.current = null
      instrumentalRef.current = null
      vocalsRef.current = null
      instrumentalSourceRef.current = null
      vocalsSourceRef.current = null
      instrumentalGainRef.current = null
      vocalsGainRef.current = null
      masterGainRef.current = null
    }
  }, [advanceQueue, alignVocals, clearTimers, ensureAudioGraph, pauseBoth, playBoth, resetPlayback, setPaused, setVocalGain])

  const playTrack = useCallback(async (vid: string, mode?: PlaybackMode) => {
    const instrumental = instrumentalRef.current
    if (vid === loadingIdRef.current) return
    if (vid === videoIdRef.current && instrumental?.src && !instrumental.error && !vocalsRef.current?.error && !audioError) {
      if (!isPlayingRef.current && !playPendingRef.current) void playBoth()
      return
    }

    const token = loadTokenRef.current + 1
    loadTokenRef.current = token
    loadingIdRef.current = vid
    resetPlayback()
    for (const media of [instrumentalRef.current, vocalsRef.current]) {
      if (!media) continue
      media.removeAttribute('src')
      media.load()
    }
    endedGuardRef.current = false
    seekingRef.current = false
    videoIdRef.current = null
    setTrack(null)
    setVideoId(null)
    setDuration(0)
    setCurrentTime(0)
    setLoading(true)
    setAudioLoading(false)
    setError(null)
    setAudioError(null)

    const selectedMode = mode || 'karaoke'
    modeRef.current = selectedMode
    setPlaybackMode(selectedMode)

    let data: Track
    try {
      data = await getTrack(vid)
    } catch {
      if (loadTokenRef.current === token) {
        loadingIdRef.current = null
        setError('Track metadata could not be loaded.')
        setLoading(false)
      }
      return
    }

    if (loadTokenRef.current !== token) return

    if (!mode && data.mode) {
      const trackMode = data.mode as PlaybackMode
      modeRef.current = trackMode
      setPlaybackMode(trackMode)
    }

    videoIdRef.current = vid
    setVideoId(vid)
    setTrack(data)
    setLoading(false)
    setAudioLoading(true)

    ensureAudioGraph()
    const nextInstrumental = instrumentalRef.current
    const nextVocals = vocalsRef.current
    if (!nextInstrumental || !nextVocals) return

    nextInstrumental.src = getInstrumentalUrl(vid)
    nextVocals.src = getVocalsUrl(vid)
    nextInstrumental.load()
    nextVocals.load()

    try {
      await Promise.all([
        waitForMediaEvent(
          nextInstrumental,
          'loadedmetadata',
          () => nextInstrumental.readyState >= HTMLMediaElement.HAVE_METADATA,
        ),
        waitForMediaEvent(
          nextVocals,
          'loadedmetadata',
          () => nextVocals.readyState >= HTMLMediaElement.HAVE_METADATA,
        ),
      ])
      if (loadTokenRef.current !== token) return

      setDuration(nextInstrumental.duration || 0)
      setCurrentTime(0)
      await playBoth(true)
    } catch (mediaError) {
      if (loadTokenRef.current !== token) return
      setAudioLoading(false)
      setAudioError(mediaError instanceof Error ? mediaError.message : 'Audio stream could not be loaded.')
    } finally {
      if (loadTokenRef.current === token) loadingIdRef.current = null
    }
  }, [audioError, ensureAudioGraph, playBoth, resetPlayback])

  const reloadTrackMetadata = useCallback(async (vid: string) => {
    const data: Track = await getTrack(vid)
    if (videoIdRef.current === vid) {
      setTrack(data)
    }
  }, [])

  const setMode = useCallback((mode: PlaybackMode) => {
    if (mode === modeRef.current || !videoIdRef.current) return

    modeRef.current = mode
    setPlaybackMode(mode)
    if (mode === 'karaoke') {
      setVocalGain(0)
      setAudioError(null)
      return
    }

    const vocals = vocalsRef.current
    if (!vocals) return
    setVocalGain(0, true)
    alignVocals()
    if (wantsPlaybackRef.current && isPlayingRef.current) {
      const token = playTokenRef.current
      void vocals.play().then(() => {
        if (playTokenRef.current === token && modeRef.current === 'full' && !vocals.seeking) setVocalGain(1)
      }).catch(error => {
        if (playTokenRef.current === token && modeRef.current === 'full') {
          setAudioError(error instanceof Error ? error.message : 'Vocals stream could not be played.')
        }
      })
    }
  }, [alignVocals, setVocalGain])

  const togglePlay = useCallback(() => {
    if (isPlayingRef.current || wantsPlaybackRef.current) {
      setPaused()
      return
    }
    void playBoth()
  }, [playBoth, setPaused])

  const seek = useCallback(async (time: number) => {
    const instrumental = instrumentalRef.current
    const vocals = vocalsRef.current
    if (!instrumental || !vocals || instrumental.readyState < HTMLMediaElement.HAVE_METADATA) return

    const wasPlaying = isPlayingRef.current || wantsPlaybackRef.current
    playTokenRef.current += 1
    playPendingRef.current = false
    const loadToken = loadTokenRef.current
    const seekToken = ++seekTokenRef.current
    seekingRef.current = true
    pauseBoth()
    clearTimers()
    isPlayingRef.current = false
    setIsPlaying(false)
    setAudioLoading(true)
    endedGuardRef.current = false

    const target = Math.max(0, Math.min(time, Number.isFinite(instrumental.duration) ? instrumental.duration : time))
    try {
      instrumental.currentTime = target
      vocals.currentTime = target
      setCurrentTime(target)
      const waits = [waitForMediaEvent(instrumental, 'seeked', () => !instrumental.seeking)]
      if (modeRef.current === 'full' && vocals.readyState >= HTMLMediaElement.HAVE_METADATA) {
        waits.push(waitForMediaEvent(vocals, 'seeked', () => !vocals.seeking))
      }
      await Promise.all(waits)
      if (seekTokenRef.current !== seekToken || loadTokenRef.current !== loadToken) return
      setCurrentTime(instrumental.currentTime)
      setAudioLoading(false)
      seekingRef.current = false
      if (wasPlaying) await playBoth()
    } catch (seekError) {
      if (seekTokenRef.current !== seekToken || loadTokenRef.current !== loadToken) return
      wantsPlaybackRef.current = false
      setAudioLoading(false)
      setAudioError(seekError instanceof Error ? seekError.message : 'Audio seek failed.')
    } finally {
      if (seekTokenRef.current === seekToken) seekingRef.current = false
    }
  }, [clearTimers, pauseBoth, playBoth])

  const value = useMemo(() => ({
    videoId, track, playbackMode, isPlaying, currentTime, duration, loading, audioLoading,
    error, audioError, playTrack, reloadTrackMetadata, setMode, togglePlay, seek,
  }), [videoId, track, playbackMode, isPlaying, currentTime, duration, loading, audioLoading,
      error, audioError, playTrack, reloadTrackMetadata, setMode, togglePlay, seek])

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
