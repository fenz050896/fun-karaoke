'use client'

import { AnimatePresence } from 'framer-motion'
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
  hasSearched?: boolean
  errorMessage?: string | null
}

export default function SearchResults({
  results,
  existingMap,
  playQueue,
  onProcess,
  onPlay,
  onAddToQueue,
  loading = false,
  hasSearched = false,
  errorMessage = null,
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

  if (errorMessage) {
    return (
      <div className="mt-6 rounded-2xl border border-red-500/20 bg-red-500/5">
        <EmptyState
          title="Search failed"
          description={errorMessage}
        />
      </div>
    )
  }

  if (hasSearched && results.length === 0) {
    return (
      <div className="mt-6 rounded-2xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900/60">
        <EmptyState
          title="No results found"
          description="Try a different song title, artist, or search type."
        />
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
          {results.map((item, index) => {
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
                index={Math.min(index, 9)}
              />
            )
          })}
        </AnimatePresence>
      </div>
    </section>
  )
}
