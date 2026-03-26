'use client'
// frontend/app/(dashboard)/report/[job_id]/page.tsx

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import NavBar from '../../../../components/NavBar'
import ReportViewer from '../../../../components/ReportViewer'
import LoadingSkeleton from '../../../../components/LoadingSkeleton'
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

interface PageProps {
  params: { job_id: string }
}

export default function ReportPage({ params }: PageProps) {
  const router = useRouter()
  const { job_id } = params

  const [report, setReport] = useState<CheckResult | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

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
          <div className="bg-white border border-gray-200 rounded-lg p-8 text-center">
            <div className="inline-flex items-center justify-center w-12 h-12 rounded-full
                            bg-red-custom/10 mb-4">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
                <circle cx="12" cy="12" r="10" stroke="#a32d2d" strokeWidth="1.5" />
                <path d="M12 8v4M12 16h.01" stroke="#a32d2d" strokeWidth="1.5" strokeLinecap="round" />
              </svg>
            </div>
            <h2 className="text-sm font-medium text-[#1a2744] mb-1">Something went wrong</h2>
            <p className="text-xs text-gray-text mb-6">{error}</p>
            <div className="flex justify-center gap-3">
              <button
                onClick={fetchReport}
                className="text-sm bg-teal text-white font-medium rounded-lg px-4 py-2
                           hover:bg-teal-dark transition-colors"
              >
                Retry
              </button>
              <button
                onClick={() => router.push('/dashboard')}
                className="text-sm border border-gray-300 text-gray-600 font-medium
                           rounded-lg px-4 py-2 hover:border-gray-400 transition-colors"
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
      <div className="bg-navy px-6 py-8">
        <div className="max-w-3xl mx-auto">
          {/* Back link */}
          <button
            onClick={() => router.push('/dashboard')}
            className="text-slate text-xs mb-4 flex items-center gap-1.5 hover:text-white transition-colors"
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
              <path d="M19 12H5M5 12l7-7M5 12l7 7" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
            Back to dashboard
          </button>

          {/* Filename */}
          <h1 className="text-white text-lg font-medium mb-1 break-words">
            {report.filename}
          </h1>

          {/* Meta */}
          <p className="text-slate text-xs mb-5">
            Checked on {formatDate(report.checked_at)} · Checklist v{report.checklist_version}
          </p>

          {/* Summary pills */}
          <div className="flex flex-wrap gap-2">
            {allClear && (
              <span className="text-xs font-medium px-3 py-1.5 rounded-full bg-teal text-white">
                No objections found
              </span>
            )}
            {hasCritical && (
              <span className="text-xs font-medium px-3 py-1.5 rounded-full"
                style={{ background: '#a32d2d', color: '#fcebeb' }}>
                {report.critical_count} Critical
              </span>
            )}
            {hasMajor && (
              <span className="text-xs font-medium px-3 py-1.5 rounded-full"
                style={{ background: '#854f0b', color: '#faeeda' }}>
                {report.major_count} Major
              </span>
            )}
            {hasMinor && (
              <span className="text-xs font-medium px-3 py-1.5 rounded-full"
                style={{ background: '#3f3f46', color: '#e4e4e7' }}>
                {report.minor_count} Minor
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
