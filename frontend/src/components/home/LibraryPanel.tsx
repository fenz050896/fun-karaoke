'use client'

import { motion, AnimatePresence } from 'framer-motion'
import EmptyState from '@/components/shared/EmptyState'

interface DownloadedSong {
  videoId: string
  title: string
  artist: string
}

interface LibraryPanelProps {
  songs: DownloadedSong[]
  playQueue: { videoId: string }[]
  onPlay: (videoId: string) => void
  onAddToQueue: (videoId: string, title: string, artist: string) => Promise<void>
}

export default function LibraryPanel({
  songs,
  playQueue,
  onPlay,
  onAddToQueue,
}: LibraryPanelProps) {
  return (
    <section className="mb-8 p-5 rounded-2xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900/60">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <h2 className="text-lg font-bold text-zinc-900 dark:text-zinc-100">
            Downloaded Songs
          </h2>
          {songs.length > 0 && (
            <span className="px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 text-xs font-semibold border border-emerald-500/20">
              {songs.length}
            </span>
          )}
        </div>
      </div>

      {songs.length === 0 ? (
        <EmptyState
          icon={
            <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
              <path d="M9 18V5l12-2v13" />
              <circle cx="6" cy="18" r="3" />
              <circle cx="18" cy="16" r="3" />
              <path d="M12 8v4M10 10h4" />
            </svg>
          }
          title="No downloaded songs yet"
          description="Search and process a song to get started"
        />
      ) : (
        <div className="space-y-2 max-h-[420px] overflow-y-auto pr-1 scrollbar-thin">
          <AnimatePresence mode="popLayout">
            {songs.map((song) => {
              const isInQueue = playQueue.some((q) => q.videoId === song.videoId)

              return (
                <motion.div
                  key={song.videoId}
                  initial={{ opacity: 0, y: 16 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, scale: 0.95 }}
                  whileHover={{ y: -1 }}
                  transition={{ duration: 0.25 }}
                  className="flex items-center gap-3 p-3 rounded-xl border border-zinc-200 dark:border-zinc-800
                    bg-white dark:bg-zinc-900/60 hover:border-emerald-500/20 dark:hover:border-emerald-500/20
                    hover:shadow-md dark:hover:shadow-emerald-500/5 transition-all duration-200"
                >
                  {/* Music note icon */}
                  <div className="w-8 h-8 flex items-center justify-center rounded-lg bg-emerald-500/10 shrink-0">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor" className="text-emerald-500">
                      <path d="M9 18V5l12-2v13" />
                      <circle cx="6" cy="18" r="3" />
                      <circle cx="18" cy="16" r="3" />
                    </svg>
                  </div>

                  {/* Song info */}
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-zinc-900 dark:text-zinc-100 truncate">
                      {song.title}
                    </p>
                    <p className="text-xs text-zinc-500 dark:text-zinc-400 truncate">
                      {song.artist}
                    </p>
                  </div>

                  {/* Actions */}
                  <div className="flex items-center gap-1.5 shrink-0">
                    <motion.button
                      whileHover={{ scale: 1.05 }}
                      whileTap={{ scale: 0.95 }}
                      onClick={() => onPlay(song.videoId)}
                      className="px-3 py-1.5 rounded-lg bg-zinc-900 dark:bg-zinc-100
                        text-zinc-100 dark:text-zinc-900 text-xs font-semibold
                        hover:bg-zinc-800 dark:hover:bg-zinc-200
                        transition-colors uppercase tracking-wider"
                    >
                      Play
                    </motion.button>
                    {!isInQueue && (
                      <motion.button
                        whileHover={{ scale: 1.05 }}
                        whileTap={{ scale: 0.95 }}
                        onClick={() => onAddToQueue(song.videoId, song.title, song.artist)}
                        className="px-3 py-1.5 rounded-lg border border-zinc-300 dark:border-zinc-700
                          text-zinc-600 dark:text-zinc-400 text-xs font-semibold
                          hover:border-fuchsia-500/40 dark:hover:border-fuchsia-500/40
                          hover:text-fuchsia-600 dark:hover:text-fuchsia-400
                          hover:bg-fuchsia-50 dark:hover:bg-fuchsia-500/5
                          transition-all uppercase tracking-wider"
                      >
                        + Queue
                      </motion.button>
                    )}
                    {isInQueue && (
                      <span className="px-3 py-1.5 rounded-lg bg-zinc-100 dark:bg-zinc-800
                        text-zinc-400 dark:text-zinc-500 text-xs font-semibold">
                        In Queue
                      </span>
                    )}
                  </div>
                </motion.div>
              )
            })}
          </AnimatePresence>
        </div>
      )}
    </section>
  )
}
