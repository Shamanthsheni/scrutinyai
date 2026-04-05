'use client'
// frontend/app/(dashboard)/report/[job_id]/page.tsx

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import NavBar from '../../../../components/NavBar'
import ReportViewer from '../../../../components/ReportViewer'
import LoadingSkeleton from '../../../../components/LoadingSkeleton'
import PrintChecklist from '../../../../components/PrintChecklist'
import { supabase } from '../../../../lib/supabase'
import { getReport } from '../../../../lib/api'
import type { CheckResult } from '../../../../types'

function formatDate(dateStr: string): string {
  return new Date(dateStr).toLocaleDateString('en-IN', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  }) + ', ' + new Date(dateStr).toLocaleTimeString('en-IN', {
    hour: '2-digit',
    minute: '2-digit',
  })
}

// Simple effect-driven count-up logic
function AnimatedCount({ value }: { value: number }) {
  const [count, setCount] = useState(0)
  
  useEffect(() => {
    let current = 0
    if (value === 0) return
    const step = Math.max(1, Math.floor(value / 20)) // Adjust increment speed
    const ms = 40 // Adjust interval frame rate

    const timerId = setInterval(() => {
      current += step
      if (current >= value) {
        current = value
        clearInterval(timerId)
      }
      setCount(current)
    }, ms)
    
    return () => clearInterval(timerId)
  }, [value])
  
  return <>{count}</>
}

interface PageProps {
  params: { job_id: string }
}

export default function ReportPage({ params }: PageProps) {
  const router = useRouter()
  const { job_id } = params

  const [report, setReport] = useState<CheckResult | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [copied, setCopied] = useState(false)

  useEffect(() => {
    // Auth guard
    supabase.auth.getSession().then(({ data }) => {
      if (!data.session) {
        router.replace('/login')
        return
      }
      fetchReport()
    })
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [job_id])

  const fetchReport = async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await getReport(job_id)
      setReport(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load report.')
    } finally {
      setLoading(false)
    }
  }

  const handleCopyReport = async () => {
    if (!report) return
    const txt = [
      `ScrutinyAI Report — ${report.filename}`,
      `Checked: ${formatDate(report.checked_at)}`,
      `Overall checks processed against Checklist v${report.checklist_version}`,
      `Critical: ${report.critical_count} | Major: ${report.major_count} | Minor: ${report.minor_count}`,
      '',
      ...report.objections.map(o => `[${o.severity}] ${o.checklist_point_id}: ${o.description} | ${o.requires_manual_verification ? '(Manual Verify)' : ''}\n  Suggested Fix: ${o.suggested_fix}\n  Rule Citation: ${o.rule_citation}`)
    ].join('\n')
    try {
      await navigator.clipboard.writeText(txt)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch (err) {
      alert("Failed to copy clipboard content.")
    }
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50">
        <NavBar />
        <LoadingSkeleton />
      </div>
    )
  }

  if (error) {
    return (
      <div className="min-h-screen bg-gray-50">
        <NavBar />
        <div className="max-w-3xl mx-auto px-4 py-12">
          <div className="bg-white border border-gray-200 rounded-lg p-8 text-center shadow-lg">
            <div className="inline-flex items-center justify-center w-12 h-12 rounded-full
                            bg-red-custom/10 mb-4 ring-2 ring-red-custom/20">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
                <circle cx="12" cy="12" r="10" stroke="#a32d2d" strokeWidth="1.5" />
                <path d="M12 8v4M12 16h.01" stroke="#a32d2d" strokeWidth="1.5" strokeLinecap="round" />
              </svg>
            </div>
            <h2 className="text-sm font-semibold text-[#1a2744] mb-1">Something went wrong</h2>
            <p className="text-xs text-gray-text mb-6">{error}</p>
            <div className="flex justify-center gap-3">
              <button
                onClick={fetchReport}
                className="text-sm bg-teal text-white font-medium rounded-lg px-5 py-2.5
                           hover:bg-teal-dark transition-all transform hover:-translate-y-0.5 shadow-sm"
              >
                Retry
              </button>
              <button
                onClick={() => router.push('/dashboard')}
                className="text-sm border border-gray-300 bg-white text-gray-700 font-medium
                           rounded-lg px-5 py-2.5 hover:border-gray-400 focus:outline-none transition-all"
              >
                Back to dashboard
              </button>
            </div>
          </div>
        </div>
      </div>
    )
  }

  if (!report) return null

  const hasCritical = report.critical_count > 0
  const hasMajor    = report.major_count > 0
  const hasMinor    = report.minor_count > 0
  const allClear    = !hasCritical && !hasMajor && !hasMinor

  return (
    <div className="min-h-screen bg-gray-50">
      <NavBar />

      {/* Report header — navy */}
      <div className="bg-[#0b172a] px-6 py-8 relative shadow-inner overflow-hidden">
        <div className="absolute inset-0 grid-pattern-overlay opacity-30 pointer-events-none" />
        <div className="max-w-3xl mx-auto relative z-10">
          
          <div className="flex flex-col md:flex-row md:items-start md:justify-between gap-6 mb-2">
            <div>
              {/* Back link */}
              <button
                onClick={() => router.push('/dashboard')}
                className="text-slate text-xs mb-5 flex items-center gap-1.5 hover:text-white transition-colors
                           font-semibold tracking-wide"
              >
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
                  <path d="M19 12H5M5 12l7-7M5 12l7 7" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
                Back to dashboard
              </button>

              {/* Filename */}
              <h1 className="text-white text-xl md:text-2xl font-semibold mb-1 break-words">
                {report.filename}
              </h1>

              {/* Meta */}
              <p className="text-slate text-xs opacity-90 mb-5">
                Checked on {formatDate(report.checked_at)} · Checklist v{report.checklist_version}
              </p>
            </div>

            {/* Copy & Print Report Actions */}
            <div className="flex-shrink-0 flex items-center gap-2">
               <button
                  onClick={handleCopyReport}
                  title="Copy the report as plain-text to your clipboard"
                  className="bg-white/10 hover:bg-white/20 border border-white/20 hover:border-white/40
                             text-white text-xs font-semibold px-4 py-2 rounded-lg 
                             transition-all flex items-center gap-2"
                >
                  <svg width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    {copied 
                      ? <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                      : <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
                    }
                  </svg>
                  {copied ? 'Copied!' : 'Copy report'}
                </button>

                <PrintChecklist result={report} filename={report.filename} />
            </div>
          </div>

          {/* Summary pills */}
          <div className="flex flex-wrap gap-2 animate-slide-in">
            {allClear && (
              <span className="text-xs font-semibold px-3 py-1.5 rounded-full bg-teal text-white shadow-sm border border-teal-dark">
                No objections found
              </span>
            )}
            {hasCritical && (
              <span className="text-xs font-semibold px-3 py-1.5 rounded-full border border-[#dc2626]"
                style={{ background: '#7f1d1d', color: '#fef2f2' }}>
                <AnimatedCount value={report.critical_count} /> Critical
              </span>
            )}
            {hasMajor && (
              <span className="text-xs font-semibold px-3 py-1.5 rounded-full border border-[#d97706]"
                style={{ background: '#78350f', color: '#fffbeb' }}>
                <AnimatedCount value={report.major_count} /> Major
              </span>
            )}
            {hasMinor && (
              <span className="text-xs font-semibold px-3 py-1.5 rounded-full border border-[#52525b]"
                style={{ background: '#27272a', color: '#f4f4f5' }}>
                <AnimatedCount value={report.minor_count} /> Minor
              </span>
            )}
          </div>
        </div>
      </div>

      {/* Report body */}
      <ReportViewer objections={report.objections} jobId={job_id} />
    </div>
  )
}
