'use client'

import { motion } from 'framer-motion'

interface SearchResult {
  videoId: string
  title: string
  artist: string
  duration: number
}

interface SearchResultItemProps {
  item: SearchResult
  isDownloaded: boolean
  isInQueue: boolean
  onProcess: (item: SearchResult) => void
  onPlay: (videoId: string) => void
  onAddToQueue: (item: SearchResult) => void
  index: number
}

function formatDuration(seconds: number) {
  const m = Math.floor(seconds / 60)
  const s = seconds % 60
  return `${m}:${s.toString().padStart(2, '0')}`
}

export default function SearchResultItem({
  item,
  isDownloaded,
  isInQueue,
  onProcess,
  onPlay,
  onAddToQueue,
  index,
}: SearchResultItemProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 24 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{
        delay: index * 0.06,
        duration: 0.35,
        ease: [0.25, 0.46, 0.45, 0.94],
      }}
      whileHover={{ y: -2 }}
      className="group flex flex-col sm:flex-row sm:items-center justify-between gap-3 p-4
        rounded-xl border border-zinc-200 dark:border-zinc-800
        bg-white dark:bg-zinc-900/80
        hover:border-fuchsia-500/30 dark:hover:border-fuchsia-500/30
        hover:shadow-lg hover:shadow-fuchsia-500/5
        dark:hover:shadow-fuchsia-500/10
        transition-colors duration-200"
    >
      {/* Left: Song info */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 flex-wrap">
          <h3 className="font-semibold text-zinc-900 dark:text-zinc-100 truncate text-sm sm:text-base">
            {item.title}
          </h3>
          {isDownloaded && (
            <span className="shrink-0 inline-flex items-center gap-1 px-2 py-0.5 rounded-full
              bg-emerald-500/10 text-emerald-600 dark:text-emerald-400
              border border-emerald-500/20 text-[10px] font-semibold uppercase tracking-wider">
              <span className="w-1 h-1 rounded-full bg-emerald-500" />
              Ready
            </span>
          )}
        </div>
        <p className="text-sm text-zinc-500 dark:text-zinc-400 truncate mt-0.5">
          {item.artist}
          <span className="mx-1.5 text-zinc-300 dark:text-zinc-600">·</span>
          {formatDuration(item.duration)}
        </p>
      </div>

      {/* Right: Actions */}
      <div className="flex items-center gap-2 shrink-0">
        {isInQueue ? (
          <span className="px-4 py-2 rounded-lg bg-zinc-100 dark:bg-zinc-800
            text-zinc-400 dark:text-zinc-500 text-xs font-semibold uppercase tracking-wider">
            In Queue
          </span>
        ) : isDownloaded ? (
          <>
            <motion.button
              whileHover={{ scale: 1.05 }}
              whileTap={{ scale: 0.95 }}
              onClick={() => onPlay(item.videoId)}
              className="px-4 py-2 rounded-lg bg-zinc-900 dark:bg-zinc-100
                text-zinc-100 dark:text-zinc-900 text-xs font-semibold
                hover:bg-zinc-800 dark:hover:bg-zinc-200
                transition-colors uppercase tracking-wider"
            >
              Play
            </motion.button>
            <motion.button
              whileHover={{ scale: 1.05 }}
              whileTap={{ scale: 0.95 }}
              onClick={() => onAddToQueue(item)}
              className="px-4 py-2 rounded-lg border border-zinc-300 dark:border-zinc-700
                text-zinc-700 dark:text-zinc-300 text-xs font-semibold
                hover:bg-zinc-100 dark:hover:bg-zinc-800
                hover:border-fuchsia-500/40 dark:hover:border-fuchsia-500/40
                hover:text-fuchsia-600 dark:hover:text-fuchsia-400
                transition-all uppercase tracking-wider"
            >
              + Queue
            </motion.button>
          </>
        ) : (
          <motion.button
            whileHover={{ scale: 1.05 }}
            whileTap={{ scale: 0.95 }}
            onClick={() => onProcess(item)}
            className="px-5 py-2 rounded-lg
              bg-gradient-to-r from-fuchsia-600 to-fuchsia-500
              hover:from-fuchsia-500 hover:to-fuchsia-400
              text-white text-xs font-bold
              shadow-lg shadow-fuchsia-500/25 hover:shadow-fuchsia-500/40
              transition-all uppercase tracking-wider"
          >
            Process
          </motion.button>
        )}
      </div>
    </motion.div>
  )
}
