'use client'

import { AudioProvider, useAudio } from '@/lib/audio-context'
import MiniPlayer from '@/components/MiniPlayer'
import { usePathname } from 'next/navigation'
import type { ReactNode } from 'react'

function ClientLayoutInner({ children }: { children: ReactNode }) {
  const { track } = useAudio()
  const pathname = usePathname()
  const isKaraokePage = pathname.startsWith('/karaoke/')
  const showPadding = track && !isKaraokePage

  return (
    <>
      <div className={`flex-1 ${showPadding ? 'pb-16' : ''}`}>{children}</div>
      <MiniPlayer />
    </>
  )
}

export default function ClientLayout({ children }: { children: ReactNode }) {
  return (
    <AudioProvider>
      <ClientLayoutInner>{children}</ClientLayoutInner>
    </AudioProvider>
  )
}
