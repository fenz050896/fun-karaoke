'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { searchYouTube, checkTrackExists, getLocalFiles, getQueue, addToQueue, removeFromQueue, startProcess } from '@/lib/api'

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
  const [existingMap, setExistingMap] = useState<Record<string, { exists: boolean; status: string }>>({})

  // Load downloaded songs and queue
  useEffect(() => {
    const loadData = async () => {
      try {
        const [localData, queueData] = await Promise.all([
          getLocalFiles(),
          getQueue()
        ])
        setDownloadedSongs(localData.files || [])
        setPlayQueue(queueData.queue || [])
      } catch (error) {
        console.error('Failed to load data:', error)
      }
    }
    loadData()
  }, [])

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!query.trim()) return
    setLoading(true)
    try {
      const data = await searchYouTube(query, 10, searchType)
      const items: SearchResult[] = data.results || []
      setResults(items)
      
      // Check saved status for each result
      const map: Record<string, { exists: boolean; status: string }> = {}
      await Promise.all(
        items.map(async (item) => {
          try {
            const res = await checkTrackExists(item.videoId)
            map[item.videoId] = res
          } catch {
            map[item.videoId] = { exists: false, status: 'not_found' }
          }
        })
      )
      setExistingMap(map)
    } catch (error) {
      console.error('Search error:', error)
      alert('Search failed: ' + error)
    } finally {
      setLoading(false)
    }
  }

  const handleAddToQueue = async (item: SearchResult) => {
    const existing = existingMap[item.videoId]
    
    // Check if already in queue
    if (playQueue.some(q => q.videoId === item.videoId)) {
      alert('Already in queue')
      return
    }

    // Check if downloaded
    if (!existing?.exists || existing.status !== 'ready') {
      alert('Song must be downloaded first')
      return
    }

    try {
      await addToQueue(item.videoId, item.title, item.artist)
      
      // If queue is empty, redirect to karaoke page
      if (playQueue.length === 0) {
        window.location.href = `/karaoke/${item.videoId}?mode=karaoke`
        return
      }
      
      // Refresh queue
      const queueData = await getQueue()
      setPlayQueue(queueData.queue || [])
    } catch (error) {
      alert('Failed to add to queue: ' + error)
    }
  }

  const handleRemoveFromQueue = async (videoId: string) => {
    try {
      await removeFromQueue(videoId)
      setPlayQueue(prev => prev.filter(q => q.videoId !== videoId))
    } catch (error) {
      alert('Failed to remove from queue')
    }
  }

  const handlePlayFromQueue = (videoId: string) => {
    window.location.href = `/karaoke/${videoId}?mode=karaoke`
  }

  const handlePlayDownloaded = (videoId: string) => {
    window.location.href = `/karaoke/${videoId}?mode=karaoke`
  }

  const handleProcess = async (item: SearchResult) => {
    try {
      await startProcess(item.videoId, item.title, item.artist)
      alert('Song added to processing queue. Check Processing page for status.')
    } catch (error) {
      alert('Failed to process: ' + error)
    }
  }

  const formatDuration = (seconds: number) => {
    const m = Math.floor(seconds / 60)
    const s = seconds % 60
    return `${m}:${s.toString().padStart(2, '0')}`
  }

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100 p-6">
      <div className="max-w-3xl mx-auto">
        <h1 className="text-3xl font-bold mb-6 text-center">Fun Karaoke</h1>
        
        {/* Search Form */}
        <form onSubmit={handleSearch} className="flex gap-2 mb-8">
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search song on YouTube..."
            className="flex-1 px-4 py-3 rounded-lg bg-zinc-900 border border-zinc-800 focus:outline-none focus:border-zinc-600"
          />
          <select
            value={searchType}
            onChange={(e) => setSearchType(e.target.value)}
            className="px-4 py-3 rounded-lg bg-zinc-900 border border-zinc-800 focus:outline-none focus:border-zinc-600"
          >
            <option value="all">All</option>
            <option value="artist">Artist</option>
            <option value="title">Title</option>
            <option value="genre">Genre</option>
          </select>
          <button
            type="submit"
            disabled={loading}
            className="px-6 py-3 rounded-lg bg-zinc-100 text-zinc-950 font-medium hover:bg-zinc-200 disabled:opacity-50"
          >
            {loading ? '...' : 'Search'}
          </button>
        </form>

        {/* Play Queue */}
        {playQueue.length > 0 && (
          <div className="mb-8 p-4 rounded-lg bg-zinc-900 border border-zinc-800">
            <div className="flex items-center justify-between mb-3">
              <h2 className="text-lg font-semibold">Queue ({playQueue.length})</h2>
              <button
                onClick={() => handlePlayFromQueue(playQueue[0].videoId)}
                className="px-4 py-2 rounded-md bg-zinc-100 text-zinc-950 text-sm font-medium hover:bg-zinc-200"
              >
                Play Now
              </button>
            </div>
            <div className="space-y-2">
              {playQueue.map((item, index) => (
                <div
                  key={item.videoId}
                  className="flex items-center justify-between p-3 rounded-md bg-zinc-950 border border-zinc-800"
                >
                  <div className="flex items-center gap-3">
                    <span className="w-6 h-6 flex items-center justify-center bg-zinc-800 rounded-full text-xs">
                      {index + 1}
                    </span>
                    <div className="flex-1 min-w-0">
                      <p className="font-medium truncate text-sm">{item.title}</p>
                      <p className="text-xs text-zinc-400 truncate">{item.artist}</p>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => handlePlayFromQueue(item.videoId)}
                      className="px-3 py-1.5 rounded-md bg-zinc-100 text-zinc-950 text-xs font-medium hover:bg-zinc-200"
                    >
                      Play
                    </button>
                    <button
                      onClick={() => handleRemoveFromQueue(item.videoId)}
                      className="px-3 py-1.5 rounded-md bg-zinc-800 text-zinc-100 text-xs font-medium hover:bg-zinc-700"
                    >
                      Remove
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Downloaded Songs */}
        {downloadedSongs.length > 0 && (
          <div className="mb-8 p-4 rounded-lg bg-zinc-900 border border-zinc-800">
            <div className="flex items-center justify-between mb-3">
              <h2 className="text-lg font-semibold">Downloaded Songs ({downloadedSongs.length})</h2>
            </div>
            <div className="space-y-2">
              {downloadedSongs.map((song) => (
                <div
                  key={song.videoId}
                  className="flex items-center justify-between p-3 rounded-md bg-zinc-950 border border-zinc-800"
                >
                  <div className="flex-1 min-w-0">
                    <p className="font-medium truncate text-sm">{song.title}</p>
                    <p className="text-xs text-zinc-400 truncate">{song.artist}</p>
                  </div>
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => handlePlayDownloaded(song.videoId)}
                      className="px-3 py-1.5 rounded-md bg-zinc-100 text-zinc-950 text-xs font-medium hover:bg-zinc-200"
                    >
                      Play
                    </button>
                    <button
                      onClick={async () => {
                        if (playQueue.some(q => q.videoId === song.videoId)) {
                          alert('Already in queue')
                          return
                        }
                        try {
                          await addToQueue(song.videoId, song.title, song.artist)
                          const queueData = await getQueue()
                          setPlayQueue(queueData.queue || [])
                        } catch (error) {
                          alert('Failed to add to queue')
                        }
                      }}
                      className="px-3 py-1.5 rounded-md bg-zinc-800 text-zinc-100 text-xs font-medium hover:bg-zinc-700"
                    >
                      Add to Queue
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Search Results */}
        {results.length > 0 && (
          <div className="space-y-3">
            <h2 className="text-lg font-semibold mb-3">Search Results</h2>
            {results.map((item) => {
              const existing = existingMap[item.videoId]
              const isDownloaded = existing?.exists && existing.status === 'ready'
              const inQueue = playQueue.some(q => q.videoId === item.videoId)
              
              return (
                <div
                  key={item.videoId}
                  className="flex items-center justify-between p-4 rounded-lg bg-zinc-900 border border-zinc-800 hover:border-zinc-700 transition"
                >
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <p className="font-medium truncate">{item.title}</p>
                      {isDownloaded && (
                        <span className="shrink-0 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 px-2 py-0.5 text-[10px] uppercase tracking-wide">
                          Downloaded
                        </span>
                      )}
                    </div>
                    <p className="text-sm text-zinc-400 truncate">{item.artist} · {formatDuration(item.duration)}</p>
                  </div>
                  <div className="flex items-center gap-2 ml-4 shrink-0">
                    {inQueue ? (
                      <span className="px-4 py-2 rounded-md bg-zinc-800 text-zinc-400 text-sm">
                        In Queue
                      </span>
                    ) : isDownloaded ? (
                      <>
                        <button
                          onClick={() => handlePlayDownloaded(item.videoId)}
                          className="px-4 py-2 rounded-md bg-zinc-100 text-zinc-950 text-sm font-medium hover:bg-zinc-200"
                        >
                          Play
                        </button>
                        <button
                          onClick={async () => {
                            try {
                              await addToQueue(item.videoId, item.title, item.artist)
                              if (playQueue.length === 0) {
                                window.location.href = `/karaoke/${item.videoId}?mode=karaoke`
                                return
                              }
                              const queueData = await getQueue()
                              setPlayQueue(queueData.queue || [])
                            } catch (error) {
                              alert('Failed to add to queue')
                            }
                          }}
                          className="px-4 py-2 rounded-md bg-zinc-800 text-zinc-100 text-sm font-medium hover:bg-zinc-700"
                        >
                          Add to Queue
                        </button>
                      </>
                    ) : (
                      <button
                        onClick={() => handleProcess(item)}
                        className="px-4 py-2 rounded-md bg-fuchsia-600 text-white text-sm font-medium hover:bg-fuchsia-700"
                      >
                        Process
                      </button>
                    )}
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </div>
    </div>
  )
}