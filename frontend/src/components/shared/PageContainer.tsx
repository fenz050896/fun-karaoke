import type { ReactNode } from 'react'

interface PageContainerProps {
  children: ReactNode
}

export default function PageContainer({ children }: PageContainerProps) {
  return (
    <div className="min-h-screen bg-zinc-50 dark:bg-zinc-950 text-zinc-900 dark:text-zinc-100">
      {/* Subtle background gradient */}
      <div className="fixed inset-0 pointer-events-none bg-[radial-gradient(ellipse_80%_50%_at_50%_-20%,rgba(217,70,239,0.06),transparent)] dark:bg-[radial-gradient(ellipse_80%_50%_at_50%_-20%,rgba(217,70,239,0.08),transparent)]" />

      <div className="relative max-w-7xl mx-auto px-4 py-6 sm:px-6 lg:px-8">
        {children}
      </div>
    </div>
  )
}
