# Home Page Redesign — Design Spec

**Date:** 2026-06-11
**Status:** approved
**Scope:** Frontend only — `frontend/src/app/page.tsx` + extracted components
**Backend API:** Unchanged

## Goal

Redesign the home page (`/`) with polished UI, extracted components, dark/light theme toggle, toast notifications replacing `alert()`, and micro-animations for a fun, energetic karaoke experience.

## Non-Goals

- Backend changes
- New API endpoints
- Auth, database, or multi-user features
- Other pages (karaoke player, processing page, MiniPlayer) — these are separate phases

---

## Component Tree

```
page.tsx (thin — compose only)
├── SearchForm.tsx
│   Input: query, searchType, onSubmit, loading
│   Output: fires onSubmit(query, searchType)
├── SearchResults.tsx
│   Input: results[], existingMap, playQueue, onProcess, onPlay, onAddToQueue
│   Renders: list of SearchResultItem
│   └── SearchResultItem.tsx
│       Input: item, isDownloaded, isInQueue, onProcess, onPlay, onAddToQueue
│       Renders: thumbnail, title, artist, duration, status badge, action buttons
├── QueuePanel.tsx
│   Input: queue[], onPlay, onRemove
│   Renders: header with count, list of QueueItem
│   └── QueueItem.tsx
│       Input: item, index, isNowPlaying, onPlay, onRemove
├── LibraryPanel.tsx
│   Input: downloadedSongs[], onPlay, onAddToQueue
│   Renders: header with count, list of song rows with action buttons
├── ThemeToggle.tsx (shared)
│   Uses ThemeProvider context, renders sun/moon icon button
├── ToastProvider.tsx + Toast.tsx (shared)
│   Context + container + individual toast component
└── Skeleton.tsx + EmptyState.tsx (shared)
```

## File Changes

### New Files

| File | Purpose |
|---|---|
| `components/home/SearchForm.tsx` | Search input with debounce, search type selector, submit button |
| `components/home/SearchResults.tsx` | Results list with stagger animation |
| `components/home/SearchResultItem.tsx` | Single result with thumbnail, status badge, action buttons |
| `components/home/QueuePanel.tsx` | Play queue section with layout animation |
| `components/home/QueueItem.tsx` | Single queue item with index, title, artist, play/remove |
| `components/home/LibraryPanel.tsx` | Downloaded songs section |
| `components/shared/Toast.tsx` | Toast notification component |
| `components/shared/ToastProvider.tsx` | Toast context + container |
| `components/shared/ThemeProvider.tsx` | Theme context (dark/light), reads localStorage, toggles `<html>` class |
| `components/shared/ThemeToggle.tsx` | Sun/moon icon toggle button |
| `components/shared/Skeleton.tsx` | Loading skeleton placeholder |
| `components/shared/EmptyState.tsx` | Empty state with icon + message + optional CTA |
| `lib/toast-context.ts` | `useToast()` hook, returns `{ toast, success, error, info }` |

### Modified Files

| File | Change |
|---|---|
| `app/page.tsx` | Thin — remove inline UI, compose new components, pass data as props |
| `app/layout.tsx` | Wrap with `ThemeProvider` + `ToastProvider` |
| `app/globals.css` | Add design tokens (CSS custom properties), animation keyframes, light/dark theme variables |

### Unchanged Files

| File | Reason |
|---|---|
| `lib/api.ts` | API contracts stable |
| `lib/audio-context.tsx` | Not in scope |
| `components/MiniPlayer.tsx` | Separate phase |
| `backend/**` | Backend unchanged |

---

## Theme System

Tailwind `dark` class strategy. `ThemeProvider` manages state:

```tsx
type Theme = 'light' | 'dark' | 'system'

interface ThemeContextValue {
  theme: Theme
  resolved: 'light' | 'dark'
  setTheme: (t: Theme) => void
  toggleTheme: () => void
}
```

- Initial value: read `localStorage('theme')`, fallback `'system'`
- On change: write `localStorage`, toggle `document.documentElement.classList`
- System mode: listen to `matchMedia('prefers-color-scheme: dark')` changes
- ThemeToggle button appears in page header. MiniPlayer integration deferred to its own redesign phase.

## Toast System

Replace all `alert()` calls with toast notifications.

```tsx
const { toast, success, error, info } = useToast()

// Usage:
success('Added to queue')
error('Search failed: ' + err.message)
info('Song already in queue')
```

**Behavior:**
- Position: bottom-right, stacked
- Animation: slide-up + fade-in (framer-motion)
- Auto-dismiss: 4 seconds
- Manual dismiss: click X button or swipe away
- Max visible: 5 toasts, older auto-dismiss

**Types:**
| Type | Icon | Color |
|---|---|---|
| success | checkmark circle | emerald |
| error | x circle | red |
| info | info circle | brand (fuchsia) |

## Animations

Use `framer-motion` for all animations. No CSS-only workarounds.

| Element | Animation | Easing |
|---|---|---|
| Search results | Stagger: items fade-in + slide-up 20px, 50ms stagger | ease-out |
| Queue items | `layout` prop for smooth reorder when items added/removed | spring |
| Queue item enter | fade-in + scale 0.95→1 | ease-out |
| Queue item exit | fade-out + scale 1→0.95 + collapse height | ease-in |
| Library items | Same as queue items | — |
| Toast enter | slide-up 40px + fade-in | ease-out |
| Toast exit | fade-out + slide-right 20px | ease-in |
| Buttons (hover) | scale 1.03 | spring |
| Cards (hover) | lift: translateY(-2px) + shadow increase | ease-out |
| Mode toggle | scale pulse 0.9→1.05→1 on click | spring |
| Theme toggle icon | rotate 180° on switch | ease-in-out |

**Principles:**
- Animations ≤ 300ms duration (fast and snappy)
- No animation on `prefers-reduced-motion: reduce`
- Stagger max 10 items then instant (prevents long waits)

## Design Tokens (globals.css)

```css
:root {
  /* Brand */
  --color-brand: #d946ef;        /* fuchsia-500 */
  --color-brand-hover: #c026d3;  /* fuchsia-600 */

  /* Light theme surfaces */
  --color-bg: #fafafa;
  --color-surface: #ffffff;
  --color-surface-hover: #f4f4f5;
  --color-border: #e4e4e7;

  /* Light theme text */
  --color-text: #18181b;
  --color-text-secondary: #52525b;
  --color-text-muted: #a1a1aa;

  /* Radius */
  --radius-sm: 6px;
  --radius-md: 10px;
  --radius-lg: 16px;
  --radius-full: 9999px;

  /* Spacing (Tailwind compatible — use Tailwind classes, tokens for one-off) */
}
```

Dark theme overrides via `.dark` class in `globals.css`.

---

## Responsive Strategy

Mobile-first breakpoints (Tailwind defaults):

| Breakpoint | Layout |
|---|---|
| `< md` (768px) | Single column, full-width cards, search form stacked vertically |
| `md–lg` | Search results 2-across grid (where applicable) |
| `lg+` | Max-width container (`max-w-3xl`), comfortable spacing |

Mobile specifics:
- Touch targets minimum 44×44px on all buttons
- Queue/Library panels collapse to full-width cards
- Search type selector stays inline with input (not dropdown on mobile for discoverability)
- No horizontal scroll — all content reflows

---

## Implementation Phases

### Phase 1: Infrastructure (shared components)
1. Install `framer-motion`
2. Create `lib/toast-context.ts` — `useToast()` hook
3. Create `ToastProvider.tsx` + `Toast.tsx`
4. Create `ThemeProvider.tsx` + `ThemeToggle.tsx`
5. Create `Skeleton.tsx` + `EmptyState.tsx`
6. Update `layout.tsx` — wrap ThemeProvider + ToastProvider
7. Add design tokens + animation keyframes (skeleton pulse, spinner) to `globals.css`

**Verify:** App boots without errors, theme toggle works, toast can be triggered

### Phase 2: Home page components
1. Create `SearchForm.tsx`
2. Create `SearchResultItem.tsx` + `SearchResults.tsx`
3. Create `QueueItem.tsx` + `QueuePanel.tsx`
4. Create `LibraryPanel.tsx`
5. Rewrite `page.tsx` — compose new components, remove old inline UI

**Verify:** Home page renders with new components, search works, queue works, all animations play

### Phase 3: Animations & polish
1. Add stagger animation to SearchResults
2. Add layout animation to QueuePanel
3. Add hover/focus animations to all interactive elements
4. Add enter/exit animations to queue items
5. Replace all `alert()` calls with toast
6. Test `prefers-reduced-motion`

**Verify:** No `alert()` remains in codebase, animations smooth, dark/light toggle works, toasts replace all errors

---

## Verification Checklist

- [ ] Search YouTube, results appear with stagger animation
- [ ] Process a song, toast notification appears
- [ ] Add to queue, item animates in
- [ ] Remove from queue, item animates out
- [ ] Toggle dark/light theme, all components respond
- [ ] Theme persists on page reload (localStorage)
- [ ] Empty states render when no data (no queue, no results, no library)
- [ ] Skeleton loading shown during search
- [ ] No `alert()` calls remain
- [ ] Respects `prefers-reduced-motion: reduce`
- [ ] Mobile: layout stacks vertically, touch targets ≥ 44px
- [ ] Backend API unchanged, all endpoints still function
