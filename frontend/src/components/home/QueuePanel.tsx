'use client'

import { AnimatePresence } from 'framer-motion'
import QueueItem from './QueueItem'
import EmptyState from '@/components/shared/EmptyState'

interface QueueItemData {
  videoId: string
  title: string
  artist: string
}

interface QueuePanelProps {
  queue: QueueItemData[]
  nowPlayingVideoId: string | null
  onPlay: (videoId: string) => void
  onRemove: (videoId: string) => void
  onPlayAll?: () => void
}

export default function QueuePanel({
  queue,
  nowPlayingVideoId,
  onPlay,
  onRemove,
  onPlayAll,
}: QueuePanelProps) {
  return (
    <section className="mb-8 p-5 rounded-2xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900/60">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <h2 className="text-lg font-bold text-zinc-900 dark:text-zinc-100">
            Queue
          </h2>
          {queue.length > 0 && (
            <span className="px-2 py-0.5 rounded-full bg-cyan-400/10 text-cyan-600 dark:text-cyan-400 text-xs font-semibold border border-cyan-400/20">
              {queue.length}
            </span>
          )}
        </div>
        {queue.length > 0 && onPlayAll && (
          <button
            onClick={onPlayAll}
            className="px-3 py-1.5 rounded-lg text-xs font-semibold text-fuchsia-600 dark:text-fuchsia-400
              hover:bg-fuchsia-500/10 transition-colors uppercase tracking-wider"
          >
            Play All
          </button>
        )}
      </div>

      {/* Queue items */}
      {queue.length === 0 ? (
        <EmptyState
          icon={
            <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round">
              <path d="M9 18V5l12-2v13" />
              <circle cx="6" cy="18" r="3" />
              <circle cx="18" cy="16" r="3" />
            </svg>
          }
          title="Queue is empty"
          description="Search for a song and add it to the queue"
        />
      ) : (
        <div className="space-y-2 max-h-[420px] overflow-y-auto pr-1 scrollbar-thin">
          <AnimatePresence mode="popLayout">
            {queue.map((item, index) => (
              <QueueItem
                key={item.videoId}
                item={item}
                index={index}
                isNowPlaying={item.videoId === nowPlayingVideoId}
                onPlay={onPlay}
                onRemove={onRemove}
              />
            ))}
          </AnimatePresence>
        </div>
      )}
    </section>
  )
}
