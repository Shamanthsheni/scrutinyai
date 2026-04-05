'use client'
// frontend/app/(dashboard)/dashboard/page.tsx

import { useCallback, useEffect, useRef, useState } from 'react'
import { useRouter } from 'next/navigation'
import NavBar from '../../../components/NavBar'
import UploadZone from '../../../components/UploadZone'
import RecentChecks from '../../../components/RecentChecks'
import { supabase } from '../../../lib/supabase'
import { getStatus } from '../../../lib/api'
import type { JobStatus, RecentCheck } from '../../../types'

const STORAGE_KEY = 'scrutinyai_recent_checks'
const MAX_STORED_CHECKS = 50
const POLL_INTERVAL_MS = 5000

function loadFromStorage(): RecentCheck[] {
  if (typeof window === 'undefined') return []
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    return raw ? JSON.parse(raw) : []
  } catch {
    return []
  }
}

function saveToStorage(checks: RecentCheck[]) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(checks))
  } catch {
    /* quota exceeded — silently ignore */
  }
}

export default function DashboardPage() {
  const router = useRouter()
  const [checks, setChecks] = useState<RecentCheck[]>([])
  const [authChecked, setAuthChecked] = useState(false)
  const intervalRef = useRef<NodeJS.Timeout | null>(null)

  // Auth guard
  useEffect(() => {
    supabase.auth.getSession().then(({ data }) => {
      if (!data.session) {
        router.replace('/login')
      } else {
        setChecks(loadFromStorage())
        setAuthChecked(true)
      }
    })
  }, [router])

  // Polling: update status for every queued/processing job
  const pollStatuses = useCallback(async (current: RecentCheck[]) => {
    const active = current.filter(
      (c) => c.status === 'queued' || c.status === 'processing'
    )
    if (active.length === 0) return current

    const updates = await Promise.allSettled(
      active.map((c) => getStatus(c.job_id))
    )

    let changed = false
    const updated = current.map((check) => {
      const idx = active.findIndex((a) => a.job_id === check.job_id)
      if (idx === -1) return check
      const result = updates[idx]
      if (result.status === 'fulfilled') {
        const latest = result.value
        if (latest.status !== check.status || latest.progress_percent !== check.progress_percent) {
          changed = true
          return {
            ...check,
            status: latest.status,
            progress_percent: latest.progress_percent,
          }
        }
      }
      return check
    })

    return changed ? updated : current
  }, [])

  useEffect(() => {
    if (!authChecked) return

    const run = async () => {
      setChecks((prev) => {
        const stillActive = prev.some(
          (c) => c.status === 'queued' || c.status === 'processing'
        )
        if (!stillActive && intervalRef.current) {
          clearInterval(intervalRef.current)
          intervalRef.current = null
        }
        return prev
      })

      setChecks((prev) => {
        pollStatuses(prev).then((next) => {
          if (next !== prev) {
            setChecks(next)
            saveToStorage(next)
          }
        })
        return prev
      })
    }

    intervalRef.current = setInterval(run, POLL_INTERVAL_MS)
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current)
    }
  }, [authChecked, pollStatuses])

  const handleUploadSuccess = (job: RecentCheck) => {
    setChecks((prev) => {
      const updated = [job, ...prev].slice(0, MAX_STORED_CHECKS)
      saveToStorage(updated)
      return updated
    })
  }

  const handleStatusUpdate = (jobId: string, status: JobStatus) => {
    setChecks((prev) => {
      const updated = prev.map((c) =>
        c.job_id === jobId ? { ...c, status: status.status, progress_percent: status.progress_percent } : c
      )
      saveToStorage(updated)
      return updated
    })
  }

  if (!authChecked) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="w-6 h-6 border-2 border-teal border-t-transparent rounded-full animate-spin" />
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <NavBar />

      {/* Navy hero */}
      <div className="bg-[#0b172a] relative overflow-hidden px-6 py-12 md:py-16">
        <div className="absolute inset-0 grid-pattern-overlay opacity-30 pointer-events-none" />
        <div className="max-w-3xl mx-auto relative z-10 flex flex-col md:flex-row md:items-end md:justify-between gap-6">
          <div className="flex-1">
            <p className="text-teal-light text-xs font-bold tracking-[0.15em] uppercase mb-2.5">
              Karnataka High Court
            </p>
            <h1 className="text-white text-3xl sm:text-4xl font-semibold mb-3 tracking-tight">
              Pre-filing Scrutiny Checker
            </h1>
            <p className="text-slate text-sm sm:text-base mb-8 max-w-lg leading-relaxed opacity-90">
              Upload your civil draft and receive a ranked objection report instantly. Eliminate manual oversight and file with confidence.
            </p>
            
            {/* Stat pills */}
            <div className="flex flex-wrap gap-2.5">
              {[
                { label: '21 checklist points', icon: 'M5 13l4 4L19 7' },
                { label: 'Results in 1–2 minutes', icon: 'M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z' },
                { label: 'Secured', icon: 'M13 10V3L4 14h7v7l9-11h-7z' },
              ].map((stat) => (
                <span
                  key={stat.label}
                  className="inline-flex items-center gap-1.5 text-xs text-white font-medium px-3.5 py-1.5 rounded-full border border-white/20 hover:border-white/40 hover:bg-white/10 transition-colors shadow-sm"
                  style={{ background: 'rgba(255,255,255,0.05)' }}
                >
                  <svg className="w-3.5 h-3.5 text-teal-light" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d={stat.icon} />
                  </svg>
                  {stat.label}
                </span>
              ))}
            </div>
          </div>
          
          {/* Live counter */}
          <div className="bg-white/5 border border-white/10 rounded-2xl p-5 text-center min-w-[140px] shadow-sm backdrop-blur-sm">
            <div className="text-3xl font-bold text-white mb-1 tracking-tight">
              {checks.length.toLocaleString()}
            </div>
            <div className="text-xs font-semibold text-slate uppercase tracking-wider">
              Checks Processed
            </div>
          </div>
        </div>
      </div>

      {/* Main content */}
      <div className="max-w-3xl mx-auto px-4 py-6">
        <UploadZone onUploadSuccess={handleUploadSuccess} />

        {/* Recent checks section */}
        <div>
          <p className="text-xs font-medium text-gray-text tracking-widest uppercase mb-3">
            Recent Checks
          </p>
          <RecentChecks checks={checks} onStatusUpdate={handleStatusUpdate} />
        </div>
      </div>
    </div>
  )
}
