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

function applyDocumentTheme(resolved: ResolvedTheme) {
  document.documentElement.classList.toggle('dark', resolved === 'dark')
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
    applyDocumentTheme(r)
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
    applyDocumentTheme(resolved)

    const mq = window.matchMedia('(prefers-color-scheme: dark)')
    const handler = () => {
      if (theme === 'system') {
        setResolved(resolveTheme('system'))
      }
    }
    mq.addEventListener('change', handler)
    return () => mq.removeEventListener('change', handler)
  }, [theme, resolved])

  return (
    <ThemeContext.Provider value={{ theme, resolved, setTheme, toggleTheme }}>
      {children}
    </ThemeContext.Provider>
  )
}
