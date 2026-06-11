# Home Page Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Redesign the home page (`/`) with extracted components, dark/light theme toggle, toast notifications via framer-motion, and polished UI using /frontend-design skill.

**Architecture:** Three phases. Phase 1 builds shared infrastructure (ThemeProvider, ToastProvider, Skeleton, EmptyState, design tokens). Phase 2 builds home page components (SearchForm, SearchResults, QueuePanel, LibraryPanel) using frontend-design for visual direction. Phase 3 adds animations and replaces all `alert()` calls.

**Tech Stack:** Next.js 15 App Router, React 19, TypeScript, Tailwind CSS, framer-motion

---

### Task 1: Install framer-motion

**Files:**
- Modify: `frontend/package.json`

- [ ] **Step 1: Install framer-motion**

```bash
cd frontend && npm install framer-motion
```

- [ ] **Step 2: Verify install**

Run: `cd frontend && npm ls framer-motion`
Expected: `framer-motion@<version>` listed in dependencies

- [ ] **Step 3: Commit**

```bash
git add frontend/package.json frontend/package-lock.json
git commit -m "chore(deps): add framer-motion"
```

---

### Task 2: Toast context and provider

**Files:**
- Create: `frontend/src/lib/toast-context.ts`
- Create: `frontend/src/components/shared/ToastProvider.tsx`
- Create: `frontend/src/components/shared/Toast.tsx`
- Modify: `frontend/src/app/layout.tsx`

- [ ] **Step 1: Create toast context and hook**

Create `frontend/src/lib/toast-context.ts`:

```tsx
'use client'

import { createContext, useContext } from 'react'

export type ToastType = 'success' | 'error' | 'info'

export interface Toast {
  id: string
  message: string
  type: ToastType
}

export interface ToastContextValue {
  toasts: Toast[]
  addToast: (message: string, type: ToastType) => void
  removeToast: (id: string) => void
}

const ToastContext = createContext<ToastContextValue | null>(null)

export function useToast() {
  const ctx = useContext(ToastContext)
  if (!ctx) throw new Error('useToast must be used within ToastProvider')
  return {
    toast: ctx.addToast,
    success: (msg: string) => ctx.addToast(msg, 'success'),
    error: (msg: string) => ctx.addToast(msg, 'error'),
    info: (msg: string) => ctx.addToast(msg, 'info'),
  }
}

export { ToastContext }
```

- [ ] **Step 2: Create ToastProvider**

Create `frontend/src/components/shared/ToastProvider.tsx`:

```tsx
'use client'

import { useState, useCallback, type ReactNode } from 'react'
import { AnimatePresence } from 'framer-motion'
import { ToastContext, type Toast } from '@/lib/toast-context'
import ToastItem from './Toast'

let nextId = 0

export default function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([])

  const addToast = useCallback((message: string, type: Toast['type']) => {
    const id = String(++nextId)
    setToasts(prev => [...prev.slice(-4), { id, message, type }])
    setTimeout(() => {
      setToasts(prev => prev.filter(t => t.id !== id))
    }, 4000)
  }, [])

  const removeToast = useCallback((id: string) => {
    setToasts(prev => prev.filter(t => t.id !== id))
  }, [])

  return (
    <ToastContext.Provider value={{ toasts, addToast, removeToast }}>
      {children}
      <div
        className="fixed bottom-4 right-4 z-[100] flex flex-col-reverse gap-2 pointer-events-none"
        aria-live="polite"
      >
        <AnimatePresence mode="popLayout">
          {toasts.map(t => (
            <ToastItem key={t.id} toast={t} onDismiss={removeToast} />
          ))}
        </AnimatePresence>
      </div>
    </ToastContext.Provider>
  )
}
```

- [ ] **Step 3: Create Toast component**

Create `frontend/src/components/shared/Toast.tsx`:

```tsx
'use client'

import { motion } from 'framer-motion'
import type { Toast } from '@/lib/toast-context'

const icons: Record<Toast['type'], React.ReactNode> = {
  success: (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M20 6L9 17l-5-5" />
    </svg>
  ),
  error: (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="10" />
      <path d="M15 9l-6 6M9 9l6 6" />
    </svg>
  ),
  info: (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="10" />
      <path d="M12 16v-4M12 8h.01" />
    </svg>
  ),
}

const colors: Record<Toast['type'], string> = {
  success: 'border-emerald-500/30 bg-emerald-500/10 text-emerald-400',
  error: 'border-red-500/30 bg-red-500/10 text-red-400',
  info: 'border-fuchsia-500/30 bg-fuchsia-500/10 text-fuchsia-400',
}

export default function ToastItem({
  toast,
  onDismiss,
}: {
  toast: Toast
  onDismiss: (id: string) => void
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 40, scale: 0.95 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      exit={{ opacity: 0, x: 20, scale: 0.95 }}
      transition={{ duration: 0.2, ease: 'easeOut' }}
      className={`pointer-events-auto flex items-center gap-2.5 px-4 py-3 rounded-lg border text-sm font-medium shadow-lg backdrop-blur-sm ${colors[toast.type]}`}
    >
      <span className="shrink-0">{icons[toast.type]}</span>
      <span className="flex-1">{toast.message}</span>
      <button
        onClick={() => onDismiss(toast.id)}
        className="shrink-0 opacity-60 hover:opacity-100 transition-opacity"
        aria-label="Dismiss"
      >
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
          <path d="M18 6L6 18M6 6l12 12" />
        </svg>
      </button>
    </motion.div>
  )
}
```

- [ ] **Step 4: Wrap layout with ToastProvider**

Read `frontend/src/app/layout.tsx` first, then modify. Add `ToastProvider` wrapping children:

```tsx
// After existing imports, add:
import ToastProvider from '@/components/shared/ToastProvider'

// In the component, wrap {children}:
// <ToastProvider>{children}</ToastProvider>
```

- [ ] **Step 5: Verify — app compiles without errors**

Run: `cd frontend && npm run build 2>&1 | tail -5`
Expected: build succeeds, no TypeScript errors

- [ ] **Step 6: Commit**

```bash
git add frontend/src/lib/toast-context.ts frontend/src/components/shared/ToastProvider.tsx frontend/src/components/shared/Toast.tsx frontend/src/app/layout.tsx
git commit -m "feat(ui): add toast notification system with framer-motion"
```

---

### Task 3: Theme system

**Files:**
- Create: `frontend/src/components/shared/ThemeProvider.tsx`
- Create: `frontend/src/components/shared/ThemeToggle.tsx`
- Modify: `frontend/src/app/layout.tsx`
- Modify: `frontend/src/app/globals.css`

- [ ] **Step 1: Create ThemeProvider**

Create `frontend/src/components/shared/ThemeProvider.tsx`:

```tsx
'use client'

import {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
  type ReactNode,
} from 'react'

type Theme = 'light' | 'dark' | 'system'
type ResolvedTheme = 'light' | 'dark'

interface ThemeContextValue {
  theme: Theme
  resolved: ResolvedTheme
  setTheme: (t: Theme) => void
  toggleTheme: () => void
}

const ThemeContext = createContext<ThemeContextValue | null>(null)

function resolveTheme(theme: Theme): ResolvedTheme {
  if (theme !== 'system') return theme
  if (typeof window === 'undefined') return 'dark'
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
}

function getStoredTheme(): Theme {
  if (typeof window === 'undefined') return 'system'
  return (localStorage.getItem('theme') as Theme) || 'system'
}

export function useTheme() {
  const ctx = useContext(ThemeContext)
  if (!ctx) throw new Error('useTheme must be used within ThemeProvider')
  return ctx
}

export default function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setThemeState] = useState<Theme>(getStoredTheme)
  const [resolved, setResolved] = useState<ResolvedTheme>(() =>
    resolveTheme(getStoredTheme()),
  )

  const apply = useCallback((t: Theme) => {
    const r = resolveTheme(t)
    setResolved(r)
    document.documentElement.classList.toggle('dark', r === 'dark')
  }, [])

  const setTheme = useCallback(
    (t: Theme) => {
      setThemeState(t)
      localStorage.setItem('theme', t)
      apply(t)
    },
    [apply],
  )

  const toggleTheme = useCallback(() => {
    setTheme(resolved === 'dark' ? 'light' : 'dark')
  }, [setTheme, resolved])

  // Apply on mount + listen for system changes
  useEffect(() => {
    apply(theme)

    const mq = window.matchMedia('(prefers-color-scheme: dark)')
    const handler = () => {
      if (theme === 'system') apply('system')
    }
    mq.addEventListener('change', handler)
    return () => mq.removeEventListener('change', handler)
  }, [theme, apply])

  return (
    <ThemeContext.Provider value={{ theme, resolved, setTheme, toggleTheme }}>
      {children}
    </ThemeContext.Provider>
  )
}
```

- [ ] **Step 2: Create ThemeToggle**

Create `frontend/src/components/shared/ThemeToggle.tsx`:

```tsx
'use client'

import { motion } from 'framer-motion'
import { useTheme } from './ThemeProvider'

export default function ThemeToggle() {
  const { resolved, toggleTheme } = useTheme()

  return (
    <motion.button
      onClick={toggleTheme}
      whileTap={{ scale: 0.9 }}
      className="p-2 rounded-lg border border-zinc-200 dark:border-zinc-800 hover:bg-zinc-100 dark:hover:bg-zinc-800 transition-colors"
      aria-label={`Switch to ${resolved === 'dark' ? 'light' : 'dark'} mode`}
    >
      <motion.div
        initial={false}
        animate={{ rotate: resolved === 'dark' ? 180 : 0 }}
        transition={{ duration: 0.3, ease: 'easeInOut' }}
      >
        {resolved === 'dark' ? (
          <svg
            width="18" height="18" viewBox="0 0 24 24" fill="none"
            stroke="currentColor" strokeWidth="2" strokeLinecap="round"
            strokeLinejoin="round" className="text-amber-400"
          >
            <circle cx="12" cy="12" r="5" />
            <path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42" />
          </svg>
        ) : (
          <svg
            width="18" height="18" viewBox="0 0 24 24" fill="none"
            stroke="currentColor" strokeWidth="2" strokeLinecap="round"
            strokeLinejoin="round" className="text-zinc-600"
          >
            <path d="M21 12.79A9 9 0 1111.21 3 7 7 0 0021 12.79z" />
          </svg>
        )}
      </motion.div>
    </motion.button>
  )
}
```

- [ ] **Step 3: Wrap layout with ThemeProvider**

Read current `frontend/src/app/layout.tsx`. Add ThemeProvider import and wrap:

```
import ThemeProvider from '@/components/shared/ThemeProvider'

// Wrap children (ThemeProvider should be inside ToastProvider):
// <ThemeProvider>{children}</ThemeProvider>
```

ThemeProvider goes inside ToastProvider so toasts can adapt to theme. Update layout so providers nest: `ToastProvider > ThemeProvider > {children}`.

- [ ] **Step 4: Add light theme CSS variables to globals.css**

Read current `frontend/src/app/globals.css`. Append at the end:

```css
/* Light theme (default) */
:root {
  --color-brand: #c026d3;
  --color-brand-dim: #d946ef;
}

/* Dark theme overrides handled by Tailwind dark: prefix utilities */

/* Respect reduced motion */
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
  }
}
```

- [ ] **Step 5: Verify — theme toggle works**

```bash
cd frontend && npm run dev &
```
Open `http://localhost:3000`. Click sun/moon icon. Theme should toggle. Check localStorage has `theme` key. Refresh page — theme persists.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/shared/ThemeProvider.tsx frontend/src/components/shared/ThemeToggle.tsx frontend/src/app/layout.tsx frontend/src/app/globals.css
git commit -m "feat(ui): add dark/light theme system with toggle"
```

---

### Task 4: Skeleton and EmptyState shared components

**Files:**
- Create: `frontend/src/components/shared/Skeleton.tsx`
- Create: `frontend/src/components/shared/EmptyState.tsx`

- [ ] **Step 1: Create Skeleton component**

Create `frontend/src/components/shared/Skeleton.tsx`:

```tsx
export function Skeleton({ className = '' }: { className?: string }) {
  return (
    <div
      className={`animate-pulse rounded-md bg-zinc-200 dark:bg-zinc-800 ${className}`}
      aria-hidden="true"
    />
  )
}

export function SkeletonCard() {
  return (
    <div className="p-4 rounded-lg border border-zinc-200 dark:border-zinc-800 space-y-3">
      <Skeleton className="h-4 w-3/4" />
      <Skeleton className="h-3 w-1/2" />
    </div>
  )
}

export function SkeletonList({ count = 3 }: { count?: number }) {
  return (
    <div className="space-y-3">
      {Array.from({ length: count }).map((_, i) => (
        <SkeletonCard key={i} />
      ))}
    </div>
  )
}
```

- [ ] **Step 2: Create EmptyState component**

Create `frontend/src/components/shared/EmptyState.tsx`:

```tsx
import type { ReactNode } from 'react'

interface EmptyStateProps {
  icon?: ReactNode
  title: string
  description?: string
  action?: ReactNode
}

export default function EmptyState({ icon, title, description, action }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center py-12 text-center">
      {icon && (
        <div className="mb-4 text-zinc-300 dark:text-zinc-600">{icon}</div>
      )}
      <p className="text-sm font-medium text-zinc-500 dark:text-zinc-400">
        {title}
      </p>
      {description && (
        <p className="mt-1 text-xs text-zinc-400 dark:text-zinc-500">
          {description}
        </p>
      )}
      {action && <div className="mt-4">{action}</div>}
    </div>
  )
}
```

- [ ] **Step 3: Verify — build compiles**

```bash
cd frontend && npx tsc --noEmit
```
Expected: no errors

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/shared/Skeleton.tsx frontend/src/components/shared/EmptyState.tsx
git commit -m "feat(ui): add Skeleton and EmptyState shared components"
```

---

### Task 5: SearchForm component

**File:** Create `frontend/src/components/home/SearchForm.tsx`

Use `/frontend-design:frontend-design` skill for visual design direction before writing code. The component must:

- Controlled input for search query
- Select dropdown for search type (`all`, `artist`, `title`, `genre`)
- Submit button with loading state
- Accept `onSubmit(query, searchType)` callback prop
- Mobile: stacked layout; desktop: inline row

- [ ] **Step 1: Invoke frontend-design for SearchForm design**

Use the `/frontend-design:frontend-design` skill to generate a visual design for the search form. Prompt: "Design a search form for a karaoke app. Dark/light theme compatible. Contains: text input, select dropdown (All/Artist/Title/Genre), submit button. Should feel fun and energetic — karaoke/music theme. Show loading spinner inside button when searching. Mobile responsive."

- [ ] **Step 2: Implement SearchForm based on design**

Create `frontend/src/components/home/SearchForm.tsx` with the generated design, adapted to match these props:

```tsx
'use client'

import type { FormEvent } from 'react'

interface SearchFormProps {
  query: string
  searchType: string
  loading: boolean
  onQueryChange: (q: string) => void
  onSearchTypeChange: (t: string) => void
  onSubmit: (e: FormEvent) => void
}

// ... implement with frontend-design output
```

- [ ] **Step 3: Verify TypeScript**

```bash
cd frontend && npx tsc --noEmit
```
Expected: no errors

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/home/SearchForm.tsx
git commit -m "feat(ui): add SearchForm component"
```

---

### Task 6: SearchResultItem and SearchResults components

**Files:**
- Create: `frontend/src/components/home/SearchResultItem.tsx`
- Create: `frontend/src/components/home/SearchResults.tsx`

Use `/frontend-design:frontend-design` for visual direction.

- [ ] **Step 1: Invoke frontend-design for search results**

Use the `/frontend-design:frontend-design` skill. Prompt: "Design search result cards for a karaoke app. Each card shows: song title, artist, duration, a 'Downloaded' badge if already processed, and action buttons (Play/Add to Queue if downloaded, Process if not). Cards appear in a vertical list with stagger animation on enter. Dark/light theme. Fun, music-themed aesthetic."

- [ ] **Step 2: Implement SearchResultItem**

Create `frontend/src/components/home/SearchResultItem.tsx` with props:

```tsx
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
```

- [ ] **Step 3: Implement SearchResults**

Create `frontend/src/components/home/SearchResults.tsx` — renders a list of `SearchResultItem` with framer-motion stagger animation using `motion.div` wrapper and `variants` + `staggerChildren`. Props:

```tsx
interface SearchResultsProps {
  results: SearchResult[]
  existingMap: Record<string, { exists: boolean; status: string }>
  playQueue: { videoId: string }[]
  onProcess: (item: SearchResult) => void
  onPlay: (videoId: string) => void
  onAddToQueue: (item: SearchResult) => void
}
```

- [ ] **Step 4: Verify TypeScript**

```bash
cd frontend && npx tsc --noEmit
```
Expected: no errors

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/home/SearchResultItem.tsx frontend/src/components/home/SearchResults.tsx
git commit -m "feat(ui): add SearchResultItem and SearchResults components"
```

---

### Task 7: QueuePanel and QueueItem components

**Files:**
- Create: `frontend/src/components/home/QueueItem.tsx`
- Create: `frontend/src/components/home/QueuePanel.tsx`

Use `/frontend-design:frontend-design` for visual direction.

- [ ] **Step 1: Invoke frontend-design for queue panel**

Prompt: "Design a play queue panel for a karaoke app. It shows upcoming songs in a numbered list. Each item has: position number, title, artist, Play button, Remove button. The currently playing song is highlighted. Items animate in/out with layout animation (framer-motion). Empty state when queue is empty. Dark/light theme."

- [ ] **Step 2: Implement QueueItem**

Create `frontend/src/components/home/QueueItem.tsx`:

```tsx
'use client'

import { motion } from 'framer-motion'

interface QueueItemData {
  videoId: string
  title: string
  artist: string
}

interface QueueItemProps {
  item: QueueItemData
  index: number
  isNowPlaying: boolean
  onPlay: (videoId: string) => void
  onRemove: (videoId: string) => void
}
```

- [ ] **Step 3: Implement QueuePanel**

Create `frontend/src/components/home/QueuePanel.tsx` with `AnimatePresence` and `layout` animations. Props:

```tsx
interface QueuePanelProps {
  queue: QueueItemData[]
  nowPlayingVideoId: string | null
  onPlay: (videoId: string) => void
  onRemove: (videoId: string) => void
}
```

Uses `EmptyState` when queue is empty.

- [ ] **Step 4: Verify TypeScript**

```bash
cd frontend && npx tsc --noEmit
```
Expected: no errors

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/home/QueueItem.tsx frontend/src/components/home/QueuePanel.tsx
git commit -m "feat(ui): add QueueItem and QueuePanel components"
```

---

### Task 8: LibraryPanel component

**File:** Create `frontend/src/components/home/LibraryPanel.tsx`

- [ ] **Step 1: Invoke frontend-design for library panel**

Prompt: "Design a 'Downloaded Songs' library panel for a karaoke app. Shows songs already processed and ready to play. Each item shows title, artist, Play button, Add to Queue button. Empty state when no songs downloaded. Should match the queue panel style. Dark/light theme."

- [ ] **Step 2: Implement LibraryPanel**

Create `frontend/src/components/home/LibraryPanel.tsx`:

```tsx
'use client'

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
```

- [ ] **Step 3: Verify TypeScript**

```bash
cd frontend && npx tsc --noEmit
```
Expected: no errors

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/home/LibraryPanel.tsx
git commit -m "feat(ui): add LibraryPanel component"
```

---

### Task 9: Rewrite page.tsx to compose new components

**Files:**
- Modify: `frontend/src/app/page.tsx`

- [ ] **Step 1: Rewrite page.tsx**

Replace current `page.tsx` content. The new page is a thin composer — imports all home components, keeps all data fetching logic, passes data as props:

```tsx
'use client'

import { useEffect, useState } from 'react'
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

  const { success, error } = useToast()

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
      error('Search failed: ' + (err instanceof Error ? err.message : err))
    } finally {
      setLoading(false)
    }
  }

  const handleAddToQueue = async (item: SearchResult) => {
    if (playQueue.some(q => q.videoId === item.videoId)) {
      error('Already in queue')
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
      const queueData = await getQueue()
      setPlayQueue(queueData.queue || [])
      success('Added to queue')
    } catch (err) {
      error('Failed to add to queue: ' + (err instanceof Error ? err.message : err))
    }
  }

  // ... (keep all other handlers: handleRemoveFromQueue, handlePlayFromQueue,
  //      handlePlayDownloaded, handleProcess, handleAddDownloadedToQueue)

  return (
    <div className="min-h-screen bg-zinc-50 dark:bg-zinc-950 text-zinc-900 dark:text-zinc-100">
      <div className="max-w-3xl mx-auto px-4 py-6 sm:px-6">
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <h1 className="text-2xl sm:text-3xl font-bold">Fun Karaoke</h1>
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
          onPlay={(vid) => {
            window.location.href = `/karaoke/${vid}?mode=karaoke`
          }}
          onRemove={async (vid) => {
            try {
              await removeFromQueue(vid)
              setPlayQueue(prev => prev.filter(q => q.videoId !== vid))
              success('Removed from queue')
            } catch (err) {
              error('Failed to remove')
            }
          }}
        />

        {/* Downloaded Songs */}
        <LibraryPanel
          songs={downloadedSongs}
          playQueue={playQueue}
          onPlay={(vid) => {
            window.location.href = `/karaoke/${vid}?mode=karaoke`
          }}
          onAddToQueue={async (vid, title, artist) => {
            if (playQueue.some(q => q.videoId === vid)) {
              error('Already in queue')
              return
            }
            try {
              await addToQueue(vid, title, artist)
              const queueData = await getQueue()
              setPlayQueue(queueData.queue || [])
              success('Added to queue')
            } catch (err) {
              error('Failed to add to queue')
            }
          }}
        />

        {/* Search Results */}
        <SearchResults
          results={results}
          existingMap={existingMap}
          playQueue={playQueue}
          onProcess={async (item) => {
            try {
              await startProcess(item.videoId, item.title, item.artist)
              success('Processing started. Check Processing page.')
            } catch (err) {
              error('Failed to process')
            }
          }}
          onPlay={(vid) => {
            window.location.href = `/karaoke/${vid}?mode=karaoke`
          }}
          onAddToQueue={handleAddToQueue}
        />
      </div>
    </div>
  )
}
```

Each handler not shown above (handleRemoveFromQueue, handlePlayFromQueue, handlePlayDownloaded, handleProcess, handleAddDownloadedToQueue) keeps the exact same logic from the original page.tsx — only the `alert()` calls become `error()` / `success()` toast calls.

- [ ] **Step 2: Verify — full build passes**

```bash
cd frontend && npm run build 2>&1 | tail -10
```
Expected: build succeeds

- [ ] **Step 3: Verify — manual test**

```bash
cd frontend && npm run dev &
```
Test: search, process, add to queue, remove from queue, play, theme toggle — all work. No `alert()` popups remain.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/app/page.tsx
git commit -m "refactor(ui): rewrite home page with extracted components and toast notifications"
```

---

### Task 10: Animation polish and reduced-motion

**Files:**
- Modify: `frontend/src/components/home/SearchResults.tsx` (if stagger not yet added)
- Modify: `frontend/src/components/home/QueuePanel.tsx` (if layout animations not yet added)
- Modify: `frontend/src/app/globals.css` (verify reduced-motion rule added in Task 3)

- [ ] **Step 1: Verify stagger animation in SearchResults**

SearchResultItem should receive an `index` prop and use it in framer-motion variants for stagger:

```tsx
const itemVariants = {
  hidden: { opacity: 0, y: 20 },
  visible: (i: number) => ({
    opacity: 1,
    y: 0,
    transition: { delay: i * 0.05, duration: 0.25, ease: 'easeOut' },
  }),
}
```

If not present from frontend-design output, add it.

- [ ] **Step 2: Verify layout animation in QueuePanel**

Each QueueItem should have `layout` prop from framer-motion for smooth reorder:

```tsx
<motion.div layout transition={{ type: 'spring', stiffness: 500, damping: 50 }}>
```

If not present from frontend-design output, add it.

- [ ] **Step 3: Verify reduced-motion in globals.css**

Ensure this CSS rule exists in `globals.css`:

```css
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
  }
}
```

Added in Task 3 Step 4. Verify it's still there.

- [ ] **Step 4: Verify no alert() remains**

```bash
grep -rn "alert(" frontend/src/app/page.tsx frontend/src/components/
```
Expected: no matches (or only in commented/disabled code)

- [ ] **Step 5: Full build and smoke test**

```bash
cd frontend && npm run build
```
Expected: build succeeds with no warnings

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "feat(ui): add stagger and layout animations, polish reduced-motion support"
```

---

## Verification Checklist (Final)

Run these before marking plan complete:

- [ ] `npm run build` passes clean (no TS errors, no ESLint warnings)
- [ ] Navigate to `/` — page renders with new design
- [ ] Search YouTube — results appear with stagger animation
- [ ] Process a song — toast notification confirms
- [ ] Add to queue — item animates in
- [ ] Remove from queue — item animates out
- [ ] Toggle dark/light theme — all components respond
- [ ] Theme persists on page reload (check localStorage)
- [ ] Reduce motion setting respected (check OS accessibility setting)
- [ ] Mobile viewport (375px) — layout stacks, no horizontal scroll, buttons ≥ 44px
- [ ] No `alert()` calls remain anywhere in `page.tsx` or home components
- [ ] Backend API still functions — search, process, queue endpoints all work
