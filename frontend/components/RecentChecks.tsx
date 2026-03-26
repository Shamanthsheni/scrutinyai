'use client'
// frontend/components/RecentChecks.tsx

import { useRouter } from 'next/navigation'
import type { JobStatus, RecentCheck } from '../types'
import StatusBadge from './StatusBadge'

interface RecentChecksProps {
  checks: RecentCheck[]
  onStatusUpdate: (jobId: string, status: JobStatus) => void
}

function formatDate(dateStr: string): string {
  const d = new Date(dateStr)
  return d.toLocaleDateString('en-IN', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  }) + ', ' + d.toLocaleTimeString('en-IN', {
    hour: '2-digit',
    minute: '2-digit',
  })
}

function truncateFilename(name: string, maxLen = 42): string {
  if (name.length <= maxLen) return name
  const ext = name.lastIndexOf('.')
  if (ext > 0) {
    return name.substring(0, maxLen - 4) + '…' + name.substring(ext)
  }
  return name.substring(0, maxLen - 1) + '…'
}

// Inline document icon
function DocIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
      <path
        d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8l-6-6z"
        stroke="#0f6e56"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <path
        d="M14 2v6h6M16 13H8M16 17H8M10 9H8"
        stroke="#0f6e56"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  )
}

export default function RecentChecks({ checks, onStatusUpdate }: RecentChecksProps) {
  const router = useRouter()

  if (checks.length === 0) {
    return (
      <div className="text-center py-10">
        <p className="text-gray-text text-sm">
          No checks yet. Upload a draft above to get started.
        </p>
      </div>
    )
  }

  return (
    <div className="space-y-2">
      {checks.map((check) => (
        <div
          key={check.job_id}
          className="bg-white border border-gray-200 rounded-lg px-4 py-3
                     flex items-center gap-4"
        >
          {/* Document icon */}
          <div className="w-8 h-8 rounded-full bg-teal-light flex items-center
                          justify-center flex-shrink-0">
            <DocIcon />
          </div>

          {/* Middle: filename + date */}
          <div className="flex-1 min-w-0">
            <p className="text-sm font-medium text-[#1a2744] truncate">
              {truncateFilename(check.filename)}
            </p>
            <p className="text-xs text-gray-text mt-0.5">
              {formatDate(check.created_at)}
            </p>
          </div>

          {/* Right: badge + action */}
          <div className="flex items-center gap-3 flex-shrink-0">
            <StatusBadge status={check.status} />
            {check.status === 'complete' && (
              <button
                onClick={() => router.push(`/report/${check.job_id}`)}
                className="text-teal text-xs font-medium hover:underline whitespace-nowrap"
              >
                View report →
              </button>
            )}
          </div>
        </div>
      ))}
    </div>
  )
}
