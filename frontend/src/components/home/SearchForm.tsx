'use client'

import { motion } from 'framer-motion'
import type { FormEvent } from 'react'

interface SearchFormProps {
  query: string
  searchType: string
  loading: boolean
  onQueryChange: (q: string) => void
  onSearchTypeChange: (t: string) => void
  onSubmit: (e: FormEvent) => void
}

export default function SearchForm({
  query,
  searchType,
  loading,
  onQueryChange,
  onSearchTypeChange,
  onSubmit,
}: SearchFormProps) {
  return (
    <form onSubmit={onSubmit} className="mb-8">
      <div className="flex flex-col sm:flex-row gap-2">
        {/* Search input */}
        <div className="flex-1 relative">
          <input
            type="text"
            value={query}
            onChange={(e) => onQueryChange(e.target.value)}
            placeholder="What do you want to sing?"
            className="w-full px-5 py-3.5 rounded-xl bg-zinc-100 dark:bg-zinc-900/80
              border-2 border-zinc-200 dark:border-zinc-800
              text-zinc-900 dark:text-zinc-100
              placeholder:text-zinc-400 dark:placeholder:text-zinc-500
              focus:outline-none focus:border-fuchsia-500/60
              focus:ring-4 focus:ring-fuchsia-500/10
              shadow-[0_0_0_0_rgba(217,70,239,0)]
              focus:shadow-[0_0_30px_-5px_rgba(217,70,239,0.3)]
              transition-all duration-300 text-base"
          />
          {/* Glow underline on focus */}
          <div className="absolute bottom-0 left-4 right-4 h-px bg-gradient-to-r from-transparent via-fuchsia-400/0 to-transparent transition-all duration-500 peer-focus:via-fuchsia-400/60" />
        </div>

        {/* Search type select */}
        <select
          value={searchType}
          onChange={(e) => onSearchTypeChange(e.target.value)}
          className="px-4 py-3.5 rounded-xl bg-zinc-100 dark:bg-zinc-900/80
            border-2 border-zinc-200 dark:border-zinc-800
            text-zinc-900 dark:text-zinc-100
            focus:outline-none focus:border-cyan-400/60
            focus:ring-4 focus:ring-cyan-400/10
            transition-all duration-300 text-sm font-medium
            appearance-none cursor-pointer
            bg-[url('data:image/svg+xml;charset=utf-8,%3Csvg%20xmlns%3D%22http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg%22%20width%3D%2216%22%20height%3D%2216%22%20viewBox%3D%220%200%2024%2024%22%20fill%3D%22none%22%20stroke%3D%22%2394a3b8%22%20stroke-width%3D%222%22%3E%3Cpath%20d%3D%22m6%209%206%206%206-6%22%2F%3E%3C%2Fsvg%3E')]
            bg-no-repeat bg-[right_12px_center] pr-10"
        >
          <option value="all">🎵 All</option>
          <option value="artist">🎤 Artist</option>
          <option value="title">🎶 Title</option>
          <option value="genre">🎸 Genre</option>
        </select>

        {/* Submit button */}
        <motion.button
          type="submit"
          disabled={loading}
          whileHover={{ scale: 1.02 }}
          whileTap={{ scale: 0.98 }}
          className="relative px-6 py-3.5 rounded-xl font-bold text-sm uppercase tracking-wider
            bg-fuchsia-600 hover:bg-fuchsia-500
            dark:bg-fuchsia-600 dark:hover:bg-fuchsia-500
            text-white disabled:opacity-60 disabled:cursor-not-allowed
            shadow-lg shadow-fuchsia-500/25 hover:shadow-fuchsia-500/40
            transition-all duration-300 min-w-[120px] flex items-center justify-center gap-2"
        >
          {loading ? (
            <>
              <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24" fill="none">
                <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" strokeDasharray="31.4 31.4" strokeLinecap="round" className="opacity-25" />
                <path d="M12 2a10 10 0 019.95 9" stroke="currentColor" strokeWidth="3" strokeLinecap="round" />
              </svg>
              <span>Searching</span>
            </>
          ) : (
            <>
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
                <circle cx="11" cy="11" r="8" />
                <path d="m21 21-4.3-4.3" />
              </svg>
              <span>Search</span>
            </>
          )}
        </motion.button>
      </div>
    </form>
  )
}
