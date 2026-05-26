'use client'

import { useAudio } from '@/lib/audio-context'
import { usePathname } from 'next/navigation'
import Link from 'next/link'

export default function MiniPlayer() {
  const { track, isPlaying, currentTime, duration, playbackMode, togglePlay, setMode } = useAudio()
  const pathname = usePathname()

  // Hide on karaoke page (has its own full controls)
  if (!track || pathname.startsWith('/karaoke/')) return null

  const progress = duration > 0 ? (currentTime / duration) * 100 : 0

  return (
    <div className="fixed bottom-0 left-0 right-0 z-50 bg-zinc-900 border-t border-zinc-800">
      {/* Thin progress bar at top of mini-player */}
      <div className="absolute top-0 left-0 right-0 h-0.5 bg-zinc-800">
        <div
          className="h-full bg-fuchsia-500 transition-all duration-300"
          style={{ width: `${progress}%` }}
        />
      </div>

      <div className="flex items-center gap-3 px-4 py-2.5 max-w-4xl mx-auto">
        {/* Track info */}
        <Link
          href={`/karaoke/${track.videoId}?mode=${playbackMode}`}
          className="flex-1 min-w-0 hover:opacity-80 transition"
        >
          <p className="text-sm font-medium truncate text-zinc-100">{track.title}</p>
          <p className="text-xs text-zinc-400 truncate">{track.artist || 'Unknown artist'}</p>
        </Link>

        {/* Time */}
        <span className="text-xs text-zinc-500 tabular-nums min-w-[80px] text-right">
          {formatTime(currentTime)} / {formatTime(duration)}
        </span>

        {/* Play/Pause */}
        <button
          onClick={togglePlay}
          className="p-2 rounded-full bg-zinc-100 text-zinc-950 hover:bg-zinc-200 transition"
          aria-label={isPlaying ? 'Pause' : 'Play'}
        >
          {isPlaying ? (
            <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
              <rect x="6" y="4" width="4" height="16" rx="1" />
              <rect x="14" y="4" width="4" height="16" rx="1" />
            </svg>
          ) : (
            <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
              <polygon points="5,3 19,12 5,21" />
            </svg>
          )}
        </button>

        {/* Mode toggle */}
        <div className="flex items-center rounded-full border border-zinc-700 p-0.5 text-xs">
          <button
            onClick={() => setMode('karaoke')}
            className={`px-2.5 py-1 rounded-full transition ${
              playbackMode === 'karaoke'
                ? 'bg-zinc-100 text-zinc-950 font-medium'
                : 'text-zinc-400 hover:text-zinc-200'
            }`}
          >
            Karaoke
          </button>
          <button
            onClick={() => setMode('full')}
            className={`px-2.5 py-1 rounded-full transition ${
              playbackMode === 'full'
                ? 'bg-zinc-100 text-zinc-950 font-medium'
                : 'text-zinc-400 hover:text-zinc-200'
            }`}
          >
            Full
          </button>
        </div>
      </div>
    </div>
  )
}

function formatTime(t: number) {
  if (!isFinite(t)) return '0:00'
  const m = Math.floor(t / 60)
  const s = Math.floor(t % 60)
  return `${m}:${s.toString().padStart(2, '0')}`
}
