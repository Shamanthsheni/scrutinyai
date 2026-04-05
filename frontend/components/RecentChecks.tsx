'use client'
// frontend/components/RecentChecks.tsx

import { useRouter } from 'next/navigation'
import { useEffect, useState } from 'react'
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

function EmptyDataIcon() {
  return (
    <svg width="48" height="48" viewBox="0 0 24 24" fill="none" className="text-gray-300">
      <path 
        d="M9 13h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V20a2 2 0 01-2 2z" 
        stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" 
      />
      <circle cx="14" cy="14" r="4" fill="white" stroke="currentColor" strokeWidth="1.5" />
      <path d="M17 17l2 2" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}

function ProgressStepper({ percent }: { percent: number }) {
  const steps = [
    { label: 'Queued', min: 0 },
    { label: 'Reading PDF', min: 10 },
    { label: 'Structuring', min: 30 },
    { label: 'AI Engine', min: 50 },
    { label: 'Finalizing', min: 80 },
  ];

  return (
    <div className="pt-5 pb-3 px-2 border-t border-gray-100 mt-4 animate-slide-up origin-top">
      <div className="flex justify-between items-center relative mb-2 mx-1 lg:mx-4">
        {/* Background Track */}
        <div className="absolute left-[3%] right-[3%] top-2.5 -translate-y-1/2 h-[3px] bg-gray-100 rounded-full z-0" />
        {/* Filled Track */}
        <div 
          className="absolute left-[3%] top-2.5 -translate-y-1/2 h-[3px] bg-teal rounded-full z-0 transition-all duration-500 ease-out"
          style={{ width: `${Math.max(0, percent - 5)}%` }}
        />
        
        {steps.map((step, i) => {
          const isCompleted = percent > step.min || (percent === 100);
          const isActive = percent >= step.min && (i === steps.length - 1 || percent < steps[i+1].min) && percent < 100;
          return (
            <div key={i} className="flex flex-col items-center z-10 gap-2 w-14 sm:w-16">
              <div className={`w-6 h-6 rounded-full flex items-center justify-center transition-all duration-300
                ${isCompleted || isActive ? 'bg-teal' : 'bg-gray-100'} 
                ${isActive ? 'ring-4 ring-teal/20 shadow-md transform scale-110' : ''}
              `}>
                {isCompleted && !isActive ? (
                  <svg className="w-3.5 h-3.5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
                  </svg>
                ) : isActive ? (
                   <span className="w-1.5 h-1.5 bg-white rounded-full animate-ping" />
                ) : (
                   <span className="w-1.5 h-1.5 bg-gray-300 rounded-full" />
                )}
              </div>
              <span className={`text-[10px] sm:text-[11px] font-medium text-center leading-tight transition-colors duration-300
                ${isActive ? 'text-teal font-semibold' : isCompleted ? 'text-[#1a2744]' : 'text-gray-400'}
              `}>
                {step.label}
              </span>
            </div>
          )
        })}
      </div>
    </div>
  )
}

export default function RecentChecks({ checks, onStatusUpdate }: RecentChecksProps) {
  const router = useRouter()
  // Record initial render to prevent slide-in animation on mount for all items
  const [hasMounted, setHasMounted] = useState(false)
  const [expandedId, setExpandedId] = useState<string | null>(null)
  
  useEffect(() => {
    setHasMounted(true)
  }, [])

  if (checks.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-12 px-4 border border-dashed border-gray-300 bg-gray-50/50 rounded-xl">
        <EmptyDataIcon />
        <p className="text-[#1a2744] font-medium text-sm mt-4">
          No checks yet
        </p>
        <p className="text-gray-500 text-xs mt-1">
          Your checked drafts will appear here
        </p>
      </div>
    )
  }

  const toggleExpand = (id: string, isProcessing: boolean) => {
    if (isProcessing) {
      setExpandedId(prev => prev === id ? null : id)
    }
  }

  return (
    <div className="space-y-3">
      {checks.map((check, index) => {
        const isProcessing = check.status === 'processing' || check.status === 'queued';
        const isNew = hasMounted && index === 0 && checks.length > 1; // Assuming prepended
        const isExpanded = expandedId === check.job_id && isProcessing;
        
        const rowClasses = `
          relative overflow-hidden bg-white border rounded-xl px-5 py-4
          flex flex-col transition-all duration-300 transform shadow-sm
          hover:shadow
          ${isProcessing ? 'border-gray-200 cursor-pointer hover:border-teal hover:-translate-y-[1px]' : 'border-gray-200'}
          ${isExpanded ? 'border-teal ring-1 ring-teal/20 pb-5' : ''}
          ${check.status === 'complete' && isNew ? 'animate-slide-in' : ''}
        `;

        return (
          <div 
            key={check.job_id} 
            className={rowClasses}
            onClick={() => toggleExpand(check.job_id, isProcessing)}
          >
            {/* Background layer for processing state shimmer */}
            {isProcessing && !isExpanded && (
              <div 
                className="absolute inset-0 bg-gradient-to-r from-transparent via-white/40 to-transparent animate-shimmer pointer-events-none" 
                style={{ backgroundSize: '200% 100%' }}
              />
            )}
            
            <div className="flex items-center gap-4">
              {/* Document icon */}
              <div className="w-10 h-10 rounded-full bg-teal-light flex items-center
                              justify-center flex-shrink-0 z-10 box-border border-2 border-white shadow-sm">
                <DocIcon />
              </div>

              {/* Middle: filename + date */}
              <div className="flex-1 min-w-0 z-10">
                <p className="text-sm font-semibold text-[#1a2744] truncate flex items-center gap-2">
                  {truncateFilename(check.filename)}
                  {isProcessing && (
                    <span className="text-gray-400 opacity-60 text-xs">
                       {isExpanded ? '(Click to collapse)' : '(Click to view progress)'}
                    </span>
                  )}
                </p>
                <p className="text-xs text-gray-500 mt-1 flex items-center gap-1.5">
                  <span>{formatDate(check.created_at)}</span>
                  {check.progress_percent !== undefined && isProcessing && (
                    <>
                      <span>·</span>
                      <span className="text-teal font-medium">{check.progress_percent}%</span>
                    </>
                  )}
                </p>
              </div>

              {/* Right: badge + action */}
              <div className="flex items-center gap-4 flex-shrink-0 z-10">
                <StatusBadge status={check.status} />
                {check.status === 'complete' && (
                  <button
                    onClick={(e) => { e.stopPropagation(); router.push(`/report/${check.job_id}`) }}
                    className="bg-gray-50 text-teal text-xs font-semibold border border-gray-200 
                               rounded-lg px-3 py-1.5 hover:bg-teal-light hover:border-teal/30 
                               transition-colors focus:ring-2 focus:ring-teal/20 outline-none"
                  >
                    View report
                  </button>
                )}
              </div>
            </div>

            {/* Expanded Progress Stepper */}
            {isExpanded && <ProgressStepper percent={check.progress_percent || 0} />}
          </div>
        )
      })}
    </div>
  )
}
