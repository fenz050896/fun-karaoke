'use client'

import { useEffect, useState, useCallback } from 'react'
import {
  searchYouTube,
  checkTrackExists,
  getLocalFiles,
  getQueue,
  addToQueue,
  removeFromQueue,
  startProcess,
} from '@/lib/api'
import { useToast } from '@/lib/toast-context'
import SearchForm from '@/components/home/SearchForm'
import SearchResults from '@/components/home/SearchResults'
import QueuePanel from '@/components/home/QueuePanel'
import LibraryPanel from '@/components/home/LibraryPanel'
import ThemeToggle from '@/components/shared/ThemeToggle'

interface SearchResult {
  videoId: string
  title: string
  artist: string
  duration: number
}

interface DownloadedSong {
  videoId: string
  title: string
  artist: string
}

export default function Home() {
  const [query, setQuery] = useState('')
  const [searchType, setSearchType] = useState('all')
  const [results, setResults] = useState<SearchResult[]>([])
  const [loading, setLoading] = useState(false)
  const [downloadedSongs, setDownloadedSongs] = useState<DownloadedSong[]>([])
  const [playQueue, setPlayQueue] = useState<DownloadedSong[]>([])
  const [existingMap, setExistingMap] = useState<
    Record<string, { exists: boolean; status: string }>
  >({})

  const { success, error, info } = useToast()

  // Load downloaded songs and queue on mount
  useEffect(() => {
    const loadData = async () => {
      try {
        const [localData, queueData] = await Promise.all([
          getLocalFiles(),
          getQueue(),
        ])
        setDownloadedSongs(localData.files || [])
        setPlayQueue(queueData.queue || [])
      } catch (err) {
        console.error('Failed to load data:', err)
      }
    }
    loadData()
  }, [])

  const refreshQueue = useCallback(async () => {
    try {
      const queueData = await getQueue()
      setPlayQueue(queueData.queue || [])
    } catch (err) {
      console.error('Failed to refresh queue:', err)
    }
  }, [])

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!query.trim()) return
    setLoading(true)
    try {
      const data = await searchYouTube(query, 10, searchType)
      const items: SearchResult[] = data.results || []
      setResults(items)

      const map: Record<string, { exists: boolean; status: string }> = {}
      await Promise.all(
        items.map(async (item) => {
          try {
            const res = await checkTrackExists(item.videoId)
            map[item.videoId] = res
          } catch {
            map[item.videoId] = { exists: false, status: 'not_found' }
          }
        }),
      )
      setExistingMap(map)
    } catch (err) {
      error('Search failed: ' + (err instanceof Error ? err.message : 'Unknown error'))
    } finally {
      setLoading(false)
    }
  }

  const handleAddToQueue = async (item: SearchResult) => {
    if (playQueue.some((q) => q.videoId === item.videoId)) {
      info('Already in queue')
      return
    }
    const existing = existingMap[item.videoId]
    if (!existing?.exists || existing.status !== 'ready') {
      error('Song must be downloaded first')
      return
    }
    try {
      await addToQueue(item.videoId, item.title, item.artist)
      if (playQueue.length === 0) {
        window.location.href = `/karaoke/${item.videoId}?mode=karaoke`
        return
      }
      await refreshQueue()
      success('Added to queue')
    } catch (err) {
      error('Failed to add to queue: ' + (err instanceof Error ? err.message : 'Unknown error'))
    }
  }

  const handleLibraryAddToQueue = async (videoId: string, title: string, artist: string) => {
    if (playQueue.some((q) => q.videoId === videoId)) {
      info('Already in queue')
      return
    }
    try {
      await addToQueue(videoId, title, artist)
      await refreshQueue()
      success('Added to queue')
    } catch (err) {
      error('Failed to add to queue: ' + (err instanceof Error ? err.message : 'Unknown error'))
    }
  }

  const handleRemoveFromQueue = async (videoId: string) => {
    try {
      await removeFromQueue(videoId)
      setPlayQueue((prev) => prev.filter((q) => q.videoId !== videoId))
      success('Removed from queue')
    } catch (err) {
      error('Failed to remove from queue')
    }
  }

  const handleProcess = async (item: SearchResult) => {
    try {
      await startProcess(item.videoId, item.title, item.artist)
      success('Processing started. Visit the Processing page to track progress.')
    } catch (err) {
      error('Failed to process: ' + (err instanceof Error ? err.message : 'Unknown error'))
    }
  }

  const navigateToKaraoke = (videoId: string) => {
    window.location.href = `/karaoke/${videoId}?mode=karaoke`
  }

  return (
    <div className="min-h-screen bg-zinc-50 dark:bg-zinc-950 text-zinc-900 dark:text-zinc-100">
      {/* Subtle background gradient */}
      <div className="fixed inset-0 pointer-events-none bg-[radial-gradient(ellipse_80%_50%_at_50%_-20%,rgba(217,70,239,0.06),transparent)] dark:bg-[radial-gradient(ellipse_80%_50%_at_50%_-20%,rgba(217,70,239,0.08),transparent)]" />

      <div className="relative max-w-3xl mx-auto px-4 py-6 sm:px-6">
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-3xl sm:text-4xl font-black text-zinc-900 dark:text-zinc-100 tracking-tight">
              Fun{' '}
              <span className="bg-gradient-to-r from-fuchsia-500 to-fuchsia-400 bg-clip-text text-transparent">
                Karaoke
              </span>
            </h1>
            <p className="text-sm text-zinc-500 dark:text-zinc-400 mt-0.5">
              Search, process, and sing your heart out
            </p>
          </div>
          <ThemeToggle />
        </div>

        {/* Search Form */}
        <SearchForm
          query={query}
          searchType={searchType}
          loading={loading}
          onQueryChange={setQuery}
          onSearchTypeChange={setSearchType}
          onSubmit={handleSearch}
        />

        {/* Play Queue */}
        <QueuePanel
          queue={playQueue}
          nowPlayingVideoId={null}
          onPlay={navigateToKaraoke}
          onRemove={handleRemoveFromQueue}
          onPlayAll={
            playQueue.length > 0
              ? () => navigateToKaraoke(playQueue[0].videoId)
              : undefined
          }
        />

        {/* Downloaded Songs */}
        <LibraryPanel
          songs={downloadedSongs}
          playQueue={playQueue}
          onPlay={navigateToKaraoke}
          onAddToQueue={handleLibraryAddToQueue}
        />

        {/* Search Results */}
        <SearchResults
          results={results}
          existingMap={existingMap}
          playQueue={playQueue}
          onProcess={handleProcess}
          onPlay={navigateToKaraoke}
          onAddToQueue={handleAddToQueue}
          loading={loading}
        />
      </div>
    </div>
  )
}
