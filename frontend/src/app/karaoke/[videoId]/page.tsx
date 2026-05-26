'use client'

import { use, useEffect, useMemo, useRef, useState } from 'react'
import { useSearchParams } from 'next/navigation'
import Link from 'next/link'
import { getQueue, removeFromQueue } from '@/lib/api'
import { useAudio } from '@/lib/audio-context'

type QueueItem = {
  videoId: string
  title: string
  artist: string
}

export default function KaraokePage({
  params,
}: {
  params: Promise<{ videoId: string }>
}) {
  const { videoId } = use(params)
  const searchParams = useSearchParams()
  const initialMode = searchParams.get('mode') === 'full' ? 'full' : 'karaoke'

  const {
    videoId: currentVideoId,
    track,
    playbackMode,
    isPlaying,
    currentTime,
    duration,
    loading,
    error,
    playTrack,
    setMode,
    togglePlay,
    seek,
  } = useAudio()

  const activeRef = useRef<HTMLDivElement | null>(null)
  const [queue, setQueue] = useState<QueueItem[]>([])
  const [seekValue, setSeekValue] = useState(0)
  const seekingRef = useRef(false)

  // Play track on mount if different from currently playing
  useEffect(() => {
    if (currentVideoId !== videoId) {
      playTrack(videoId, initialMode)
    }
  }, [videoId]) // eslint-disable-line react-hooks/exhaustive-deps

  // Load queue
  useEffect(() => {
    const loadQueue = async () => {
      try {
        const data = await getQueue()
        setQueue(data.queue || [])
      } catch (err) {
        console.error('Failed to load queue:', err)
      }
    }
    loadQueue()
  }, [])

  // Sync seek bar when not dragging
  useEffect(() => {
    if (!seekingRef.current) {
      setSeekValue(currentTime)
    }
  }, [currentTime])

  const activeIndex = useMemo(() => {
    const lyrics = track?.lyrics ?? []
    if (!lyrics.length) return -1

    for (let i = lyrics.length - 1; i >= 0; i -= 1) {
      if (currentTime >= lyrics[i].start) {
        return i
      }
    }

    return -1
  }, [currentTime, track?.lyrics])

  useEffect(() => {
    activeRef.current?.scrollIntoView({ block: 'center', behavior: 'smooth' })
  }, [activeIndex])

  const handleRemoveFromQueue = async (videoIdToRemove: string) => {
    try {
      await removeFromQueue(videoIdToRemove)
      setQueue(prev => prev.filter(q => q.videoId !== videoIdToRemove))
    } catch (err) {
      console.error('Failed to remove from queue:', err)
    }
  }

  const handlePlayFromQueue = (vid: string) => {
    window.location.href = `/karaoke/${vid}?mode=karaoke`
  }

  const handleSeekStart = () => {
    seekingRef.current = true
  }

  const handleSeekChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setSeekValue(Number(e.target.value))
  }

  const handleSeekEnd = () => {
    seekingRef.current = false
    seek(seekValue)
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-zinc-950 text-zinc-100 grid place-items-center p-6">
        <div className="text-center">
          <p className="text-2xl font-semibold">Loading karaoke...</p>
          <p className="mt-2 text-zinc-400">Fetching track metadata</p>
        </div>
      </div>
    )
  }

  if (error || !track) {
    return (
      <div className="min-h-screen bg-zinc-950 text-zinc-100 grid place-items-center p-6">
        <div className="max-w-md text-center">
          <p className="text-2xl font-semibold">Track unavailable</p>
          <p className="mt-2 text-zinc-400">{error || 'No track data found'}</p>
          <Link
            href="/"
            className="inline-block mt-6 rounded-lg bg-zinc-100 px-4 py-2 font-medium text-zinc-950"
          >
            Back to search
          </Link>
        </div>
      </div>
    )
  }

  return (
    <div className="h-screen bg-black text-zinc-100 flex flex-col overflow-hidden">
      {/* Header */}
      <div className="shrink-0 px-6 pt-4 pb-2">
        <Link href="/" className="text-sm text-zinc-400 hover:text-zinc-200">
          ← Back to Home
        </Link>
        <h1 className="mt-1 text-xl font-bold leading-tight line-clamp-1">{track.title}</h1>
        <p className="text-sm text-zinc-400">{track.artist || 'Unknown artist'}</p>
      </div>

      {/* Audio Controls + Mode Switch */}
      <div className="shrink-0 px-6 py-2">
        <div className="flex items-center gap-3">
          <button
            onClick={togglePlay}
            className="p-2 rounded-full bg-zinc-100 text-zinc-950 hover:bg-zinc-200 transition shrink-0"
            aria-label={isPlaying ? 'Pause' : 'Play'}
          >
            {isPlaying ? (
              <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor">
                <rect x="6" y="4" width="4" height="16" rx="1" />
                <rect x="14" y="4" width="4" height="16" rx="1" />
              </svg>
            ) : (
              <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor">
                <polygon points="5,3 19,12 5,21" />
              </svg>
            )}
          </button>

          <span className="text-sm text-zinc-400 tabular-nums min-w-[80px]">
            {formatTime(currentTime)} / {formatTime(duration)}
          </span>

          <input
            type="range"
            min={0}
            max={duration || 0}
            step={0.1}
            value={seekValue}
            onMouseDown={handleSeekStart}
            onTouchStart={handleSeekStart}
            onChange={handleSeekChange}
            onMouseUp={handleSeekEnd}
            onTouchEnd={handleSeekEnd}
            className="flex-1 h-1.5 rounded-full appearance-none bg-zinc-800 cursor-pointer
              [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-3.5 [&::-webkit-slider-thumb]:h-3.5
              [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-fuchsia-500 [&::-webkit-slider-thumb]:shadow-md
              [&::-moz-range-thumb]:w-3.5 [&::-moz-range-thumb]:h-3.5 [&::-moz-range-thumb]:rounded-full
              [&::-moz-range-thumb]:bg-fuchsia-500 [&::-moz-range-thumb]:border-none"
          />

          {/* Mode switch — right side of seeker */}
          <div className="flex items-center gap-1 rounded-full border border-zinc-800 p-0.5 shrink-0">
            <button
              onClick={() => setMode('karaoke')}
              className={[
                'px-2.5 py-1 text-xs uppercase tracking-wide rounded-full transition',
                playbackMode === 'karaoke'
                  ? 'bg-zinc-100 text-zinc-950 font-medium'
                  : 'text-zinc-500 hover:text-zinc-300',
              ].join(' ')}
            >
              Karaoke
            </button>
            <button
              onClick={() => setMode('full')}
              className={[
                'px-2.5 py-1 text-xs uppercase tracking-wide rounded-full transition',
                playbackMode === 'full'
                  ? 'bg-zinc-100 text-zinc-950 font-medium'
                  : 'text-zinc-500 hover:text-zinc-300',
              ].join(' ')}
            >
              Full
            </button>
          </div>
        </div>
      </div>

      {/* Divider */}
      <div className="shrink-0 mx-6 border-t border-zinc-900" />

      {/* Main Content: Lyrics Left, Queue Right — only these scroll */}
      <div className="flex-1 grid gap-0 md:grid-cols-[1fr_320px] min-h-0">
        {/* Lyrics — with visible container */}
        <div className="flex flex-col min-h-0 m-3 mr-0 rounded-2xl border border-zinc-900 bg-zinc-950/70 overflow-hidden">
          <div className="shrink-0 flex items-center justify-between px-5 pt-3 pb-2">
            <h2 className="text-sm font-semibold text-zinc-500 uppercase tracking-wider">Lyrics</h2>
            <p className="text-xs text-zinc-600">{track.lyrics.length} lines</p>
          </div>

          <div className="flex-1 space-y-2 overflow-y-auto px-5 pb-4 min-h-0">
            {track.lyrics.length === 0 ? (
              <p className="text-zinc-500 text-sm">No lyrics generated.</p>
            ) : (
              track.lyrics.map((line, index) => {
                const active = index === activeIndex
                return (
                  <div
                    key={`${line.start}-${index}`}
                    ref={active ? activeRef : null}
                    className={[
                      'rounded-lg border px-3 py-2 transition-all',
                      active
                        ? 'border-fuchsia-500 bg-fuchsia-500/10 text-white shadow-[0_0_30px_rgba(217,70,239,0.15)]'
                        : 'border-zinc-800/60 bg-zinc-900/40 text-zinc-400',
                    ].join(' ')}
                  >
                    <p className="text-xs text-zinc-500">{formatTimestamp(line.start)}</p>
                    <p className="mt-0.5 text-base leading-relaxed md:text-lg">{line.text}</p>
                  </div>
                )
              })
            )}
          </div>
        </div>

        {/* Queue */}
        <div className="flex flex-col min-h-0 border-l border-zinc-900 px-4 py-3">
          <div className="shrink-0 mb-2 flex items-center justify-between">
            <h2 className="text-sm font-semibold text-zinc-500 uppercase tracking-wider">Queue</h2>
            <span className="text-xs text-zinc-600">{queue.length} songs</span>
          </div>

          {queue.length === 0 ? (
            <p className="text-zinc-500 text-sm">Queue is empty</p>
          ) : (
            <div className="flex-1 space-y-2 overflow-y-auto pr-2 min-h-0">
              {queue.map((item, index) => (
                <div
                  key={item.videoId}
                  className={`p-3 rounded-lg border ${
                    item.videoId === videoId
                      ? 'border-fuchsia-500 bg-fuchsia-500/10'
                      : 'border-zinc-800 bg-zinc-900/50'
                  }`}
                >
                  <div className="flex items-center gap-2 mb-1">
                    <span className="w-5 h-5 flex items-center justify-center bg-zinc-800 rounded-full text-xs shrink-0">
                      {index + 1}
                    </span>
                    <p className="font-medium text-sm truncate">
                      {item.videoId === videoId ? '▶ ' : ''}{item.title}
                    </p>
                  </div>
                  <p className="text-xs text-zinc-400 truncate ml-7">{item.artist}</p>
                  <div className="flex items-center gap-2 mt-2 ml-7">
                    {item.videoId !== videoId && (
                      <button
                        onClick={() => handlePlayFromQueue(item.videoId)}
                        className="px-2 py-1 rounded bg-zinc-100 text-zinc-950 text-xs font-medium hover:bg-zinc-200"
                      >
                        Play
                      </button>
                    )}
                    <button
                      onClick={() => handleRemoveFromQueue(item.videoId)}
                      className="px-2 py-1 rounded bg-zinc-800 text-zinc-200 text-xs font-medium hover:bg-zinc-700"
                    >
                      Remove
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

function formatTimestamp(seconds: number) {
  const mins = Math.floor(seconds / 60)
  const secs = Math.floor(seconds % 60)
  return `${mins}:${secs.toString().padStart(2, '0')}`
}

function formatTime(t: number) {
  if (!isFinite(t)) return '0:00'
  const m = Math.floor(t / 60)
  const s = Math.floor(t % 60)
  return `${m}:${s.toString().padStart(2, '0')}`
}
