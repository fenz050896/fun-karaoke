'use client'

import { useEffect, useRef, useState } from 'react'
import { getProcessingQueue, getStatus } from '@/lib/api'

interface ProcessingJob {
  videoId: string
  title: string
  artist: string
  status: string
  error?: string
  mode: string
}

export default function ProcessingPage() {
  const [processing, setProcessing] = useState<ProcessingJob[]>([])
  const [loading, setLoading] = useState(true)
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)

  useEffect(() => {
    const loadProcessing = async () => {
      try {
        const data = await getProcessingQueue()
        setProcessing(data.processing || [])
        setLoading(false)
      } catch (error) {
        console.error('Failed to load processing:', error)
        setLoading(false)
      }
    }

    loadProcessing()
    pollRef.current = setInterval(loadProcessing, 2000)

    return () => {
      if (pollRef.current) clearInterval(pollRef.current)
    }
  }, [])

  const getStatusLabel = (status: string) => {
    switch (status) {
      case 'queued': return 'Queued'
      case 'downloading': return 'Downloading'
      case 'separating': return 'Separating Stems'
      case 'fetching_lyrics': return 'Fetching Lyrics'
      case 'ready': return 'Ready'
      case 'error': return 'Error'
      default: return status
    }
  }

  const getProgressWidth = (status: string) => {
    switch (status) {
      case 'queued': return '10%'
      case 'downloading': return '30%'
      case 'separating': return '60%'
      case 'fetching_lyrics': return '80%'
      case 'ready': return '100%'
      default: return '0%'
    }
  }

  const getProgressColor = (status: string) => {
    if (status === 'error') return 'bg-red-500'
    if (status === 'ready') return 'bg-emerald-500'
    return 'bg-fuchsia-500'
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-zinc-950 text-zinc-100 flex items-center justify-center">
        <p className="text-xl">Loading...</p>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100 p-6">
      <div className="max-w-3xl mx-auto">
        <h1 className="text-3xl font-bold mb-6">Processing Queue</h1>
        
        {processing.length === 0 ? (
          <div className="text-center py-12">
            <p className="text-zinc-400">No songs being processed</p>
            <p className="text-zinc-500 mt-2">Add songs from the search page</p>
          </div>
        ) : (
          <div className="space-y-4">
            {processing.map((job, index) => (
              <div
                key={job.videoId}
                className="p-4 rounded-lg bg-zinc-900 border border-zinc-800"
              >
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-3">
                    <span className="w-8 h-8 flex items-center justify-center bg-zinc-800 rounded-full text-sm">
                      {index + 1}
                    </span>
                    <div>
                      <p className="font-medium">{job.title}</p>
                      <p className="text-sm text-zinc-400">{job.artist}</p>
                    </div>
                  </div>
                  <span className="text-sm text-zinc-400">
                    {getStatusLabel(job.status)}
                  </span>
                </div>
                
                {/* Progress Bar */}
                <div className="mt-3 h-2 bg-zinc-800 rounded-full overflow-hidden">
                  <div
                    className={`h-full ${getProgressColor(job.status)} transition-all duration-500`}
                    style={{ width: getProgressWidth(job.status) }}
                  />
                </div>
                
                {job.error && (
                  <p className="mt-2 text-sm text-red-400">{job.error}</p>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}