'use client'

import { motion } from 'framer-motion'

interface QueueItemData {
  videoId: string
  title: string
  artist: string
}

interface QueueItemProps {
  item: QueueItemData
  index: number
  isNowPlaying: boolean
  onPlay: (videoId: string) => void
  onRemove: (videoId: string) => void
}

export default function QueueItem({
  item,
  index,
  isNowPlaying,
  onPlay,
  onRemove,
}: QueueItemProps) {
  return (
    <motion.div
      layout
      initial={{ opacity: 0, scale: 0.95, height: 0 }}
      animate={{ opacity: 1, scale: 1, height: 'auto' }}
      exit={{ opacity: 0, scale: 0.95, height: 0 }}
      transition={{ type: 'spring', stiffness: 500, damping: 50 }}
      className={`flex items-center gap-3 p-3 rounded-xl border transition-colors duration-200 ${
        isNowPlaying
          ? 'border-fuchsia-500 bg-fuchsia-500/10 shadow-[0_0_20px_-5px_rgba(217,70,239,0.2)]'
          : 'border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900/60 hover:border-zinc-300 dark:hover:border-zinc-700'
      }`}
    >
      {/* Position number */}
      <span
        className={`w-7 h-7 flex items-center justify-center rounded-full text-xs font-bold shrink-0 ${
          isNowPlaying
            ? 'bg-fuchsia-500 text-white shadow-lg shadow-fuchsia-500/30'
            : 'bg-zinc-100 dark:bg-zinc-800 text-zinc-500 dark:text-zinc-400'
        }`}
      >
        {isNowPlaying ? (
          <svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor">
            <polygon points="6,3 20,12 6,21" />
          </svg>
        ) : (
          index + 1
        )}
      </span>

      {/* Song info */}
      <div className="flex-1 min-w-0">
        <p className={`text-sm font-medium truncate ${
          isNowPlaying
            ? 'text-fuchsia-600 dark:text-fuchsia-400'
            : 'text-zinc-900 dark:text-zinc-100'
        }`}>
          {item.title}
        </p>
        <p className="text-xs text-zinc-500 dark:text-zinc-400 truncate">
          {item.artist}
        </p>
      </div>

      {/* Actions */}
      <div className="flex items-center gap-1 shrink-0">
        {!isNowPlaying && (
          <motion.button
            whileHover={{ scale: 1.1 }}
            whileTap={{ scale: 0.9 }}
            onClick={() => onPlay(item.videoId)}
            className="p-1.5 rounded-lg text-zinc-400 hover:text-fuchsia-500
              hover:bg-fuchsia-500/10 transition-colors"
            aria-label="Play"
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
              <polygon points="6,3 20,12 6,21" />
            </svg>
          </motion.button>
        )}
        <motion.button
          whileHover={{ scale: 1.1 }}
          whileTap={{ scale: 0.9 }}
          onClick={() => onRemove(item.videoId)}
          className="p-1.5 rounded-lg text-zinc-400 hover:text-red-500
            hover:bg-red-500/10 transition-colors"
          aria-label="Remove"
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
            <path d="M18 6L6 18M6 6l12 12" />
          </svg>
        </motion.button>
      </div>
    </motion.div>
  )
}
