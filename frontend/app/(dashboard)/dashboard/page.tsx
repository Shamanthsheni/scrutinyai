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
      <div className="bg-navy px-6 py-10">
        <div className="max-w-3xl mx-auto">
          <p className="text-slate text-xs font-medium tracking-widest uppercase mb-2">
            Karnataka High Court
          </p>
          <h1 className="text-white text-2xl font-medium mb-2">
            Pre-filing scrutiny checker
          </h1>
          <p className="text-slate text-sm mb-6 max-w-md leading-relaxed">
            Upload your civil draft and receive a ranked objection report before you file.
          </p>
          {/* Stat pills */}
          <div className="flex flex-wrap gap-2">
            {[
              '31 checklist points',
              'Results in 2–5 minutes',
              'Rs. 2–4 AI cost per check',
            ].map((stat) => (
              <span
                key={stat}
                className="text-xs text-white px-3 py-1.5 rounded-full"
                style={{ background: 'rgba(255,255,255,0.10)' }}
              >
                {stat}
              </span>
            ))}
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
