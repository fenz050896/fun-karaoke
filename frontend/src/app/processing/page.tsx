'use client'

import { useEffect, useRef, useState } from 'react'
import { clearFailedProcessingJobs, getProcessingQueue } from '@/lib/api'
import PageContainer from '@/components/shared/PageContainer'

interface ProcessingJob {
  jobId?: string
  videoId: string
  title: string
  artist: string
  status: string
  error?: string
  errorCode?: string
  errorMessage?: string
  errorDetail?: string
  lyricsWarning?: string
  mode: string
}

export default function ProcessingPage() {
  const [processing, setProcessing] = useState<ProcessingJob[]>([])
  const [loading, setLoading] = useState(true)
  const [clearingFailed, setClearingFailed] = useState(false)
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
      case 'encoding': return 'Encoding Audio'
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
      case 'separating': return '55%'
      case 'encoding': return '70%'
      case 'fetching_lyrics': return '85%'
      case 'ready': return '100%'
      default: return '0%'
    }
  }

  const getProgressColor = (status: string) => {
    if (status === 'error') return 'bg-red-500'
    if (status === 'ready') return 'bg-emerald-500'
    return 'bg-fuchsia-500'
  }

  const getJobErrorMessage = (job: ProcessingJob) => {
    return job.errorMessage || job.error || 'Processing failed. Try another video or retry this track.'
  }

  const getJobErrorDetail = (job: ProcessingJob) => {
    return job.errorDetail || job.lyricsWarning || null
  }

  const failedJobs = processing.filter((job) => job.status === 'error')

  const handleClearFailed = async () => {
    setClearingFailed(true)
    try {
      await clearFailedProcessingJobs()
      const data = await getProcessingQueue()
      setProcessing(data.processing || [])
    } catch (error) {
      console.error('Failed to clear failed jobs:', error)
    } finally {
      setClearingFailed(false)
    }
  }

  if (loading) {
    return (
      <PageContainer>
        <h1 className="text-3xl font-bold mb-6">Processing Queue</h1>
        <div className="flex items-center justify-center py-12">
          <p className="text-lg text-zinc-500 dark:text-zinc-400">Loading...</p>
        </div>
      </PageContainer>
    )
  }

  return (
    <PageContainer>
      <div className="mb-6 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <h1 className="text-3xl font-bold text-zinc-900 dark:text-zinc-100">Processing Queue</h1>
        {failedJobs.length > 0 && (
          <button
            onClick={handleClearFailed}
            disabled={clearingFailed}
            className="self-start rounded-lg border border-red-500/30 px-3 py-2 text-sm font-medium text-red-600 hover:bg-red-500/10 disabled:cursor-not-allowed disabled:opacity-60 dark:text-red-400"
          >
            {clearingFailed ? 'Clearing...' : 'Clear failed (' + failedJobs.length + ')'}
          </button>
        )}
      </div>

      {processing.length === 0 ? (
        <div className="text-center py-12">
          <p className="text-zinc-500 dark:text-zinc-400">No songs being processed</p>
          <p className="text-zinc-400 dark:text-zinc-500 mt-2 text-sm">Add songs from the search page</p>
        </div>
      ) : (
        <div className="space-y-4">
          {processing.map((job, index) => (
            <div
              key={job.jobId || job.videoId}
              className="p-4 rounded-xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900/60"
            >
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-3">
                  <span className="w-8 h-8 flex items-center justify-center bg-zinc-100 dark:bg-zinc-800 rounded-full text-sm text-zinc-600 dark:text-zinc-400">
                    {index + 1}
                  </span>
                  <div>
                    <p className="font-medium text-zinc-900 dark:text-zinc-100">{job.title}</p>
                    <p className="text-sm text-zinc-500 dark:text-zinc-400">{job.artist}</p>
                  </div>
                </div>
                <span className="text-sm text-zinc-500 dark:text-zinc-400">
                  {getStatusLabel(job.status)}
                </span>
              </div>

              {/* Progress Bar */}
              <div className="mt-3 h-2 bg-zinc-100 dark:bg-zinc-800 rounded-full overflow-hidden">
                <div
                  className={`h-full ${getProgressColor(job.status)} transition-all duration-500`}
                  style={{ width: getProgressWidth(job.status) }}
                />
              </div>

              {job.status === 'error' && (
                <div className="mt-3 rounded-lg border border-red-500/20 bg-red-500/5 px-3 py-2">
                  <p className="text-sm font-medium text-red-600 dark:text-red-400">
                    {getJobErrorMessage(job)}
                  </p>
                  {getJobErrorDetail(job) && (
                    <p className="mt-1 text-xs text-red-500/80 dark:text-red-400/80 break-words">
                      {getJobErrorDetail(job)}
                    </p>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </PageContainer>
  )
}
