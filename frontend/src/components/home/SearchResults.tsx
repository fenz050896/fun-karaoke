'use client'

import { motion, AnimatePresence } from 'framer-motion'
import SearchResultItem from './SearchResultItem'
import EmptyState from '@/components/shared/EmptyState'
import { SkeletonList } from '@/components/shared/Skeleton'

interface SearchResult {
  videoId: string
  title: string
  artist: string
  duration: number
}

interface SearchResultsProps {
  results: SearchResult[]
  existingMap: Record<string, { exists: boolean; status: string }>
  playQueue: { videoId: string }[]
  onProcess: (item: SearchResult) => void
  onPlay: (videoId: string) => void
  onAddToQueue: (item: SearchResult) => void
  loading?: boolean
}

export default function SearchResults({
  results,
  existingMap,
  playQueue,
  onProcess,
  onPlay,
  onAddToQueue,
  loading = false,
}: SearchResultsProps) {
  if (loading) {
    return (
      <div className="mt-6">
        <h2 className="text-lg font-bold text-zinc-900 dark:text-zinc-100 mb-4">
          Searching...
        </h2>
        <SkeletonList count={4} />
      </div>
    )
  }

  if (results.length === 0) return null

  return (
    <section className="mt-6">
      <div className="flex items-center gap-3 mb-4">
        <h2 className="text-lg font-bold text-zinc-900 dark:text-zinc-100">
          Search Results
        </h2>
        <span className="px-2 py-0.5 rounded-full bg-fuchsia-500/10 text-fuchsia-600 dark:text-fuchsia-400 text-xs font-semibold border border-fuchsia-500/20">
          {results.length}
        </span>
      </div>

      <div className="space-y-2">
        <AnimatePresence mode="popLayout">
          {results.map((item) => {
            const existing = existingMap[item.videoId]
            const isDownloaded = existing?.exists && existing.status === 'ready'
            const isInQueue = playQueue.some(
              (q) => q.videoId === item.videoId,
            )

            return (
              <SearchResultItem
                key={item.videoId}
                item={item}
                isDownloaded={isDownloaded}
                isInQueue={isInQueue}
                onProcess={onProcess}
                onPlay={onPlay}
                onAddToQueue={onAddToQueue}
                index={Math.min(results.indexOf(item), 9)}
              />
            )
          })}
        </AnimatePresence>
      </div>
    </section>
  )
}
