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
