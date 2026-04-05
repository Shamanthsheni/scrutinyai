'use client'
// frontend/components/ReportViewer.tsx

import type { Objection } from '../types'
import ObjectionCard from './ObjectionCard'

interface ReportViewerProps {
  objections: Objection[]
  jobId: string
}

type Severity = 'CRITICAL' | 'MAJOR' | 'MINOR'

const SECTION_CONFIG: Record<Severity, { label: string; headerBg: string; textColor: string; countBg: string }> = {
  CRITICAL: {
    label: 'Critical Objections',
    headerBg: 'bg-red-custom/5 border-red-custom/20 border-l-[3px] border-l-red-custom',
    textColor: 'text-red-custom',
    countBg: 'bg-red-custom text-white',
  },
  MAJOR: {
    label: 'Major Objections',
    headerBg: 'bg-amber-custom/5 border-amber-custom/20 border-l-[3px] border-l-amber-custom',
    textColor: 'text-amber-custom',
    countBg: 'bg-amber-custom text-white',
  },
  MINOR: {
    label: 'Minor Objections',
    headerBg: 'bg-gray-50 border-gray-200 border-l-[3px] border-l-gray-400',
    textColor: 'text-gray-600',
    countBg: 'bg-gray-400 text-white',
  },
}

export default function ReportViewer({ objections, jobId }: ReportViewerProps) {
  const grouped: Record<Severity, Objection[]> = {
    CRITICAL: objections.filter((o) => o.severity === 'CRITICAL'),
    MAJOR:    objections.filter((o) => o.severity === 'MAJOR'),
    MINOR:    objections.filter((o) => o.severity === 'MINOR'),
  }

  const severities: Severity[] = ['CRITICAL', 'MAJOR', 'MINOR']
  const hasSections = severities.some((s) => grouped[s].length > 0)

  if (!hasSections) {
    return (
      <div className="max-w-3xl mx-auto px-4 py-12 text-center animate-slide-up">
        <div className="inline-flex items-center justify-center w-14 h-14 rounded-full
                        bg-teal-light mb-4 ring-4 ring-teal/5">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
            <path
              d="M5 13l4 4L19 7"
              stroke="#0f6e56"
              strokeWidth="1.5"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        </div>
        <h3 className="text-base font-medium text-[#1a2744] mb-1">
          No objections found
        </h3>
        <p className="text-gray-text text-sm">
          This draft passed all checklist points. You may proceed to file.
        </p>
      </div>
    )
  }

  let globalCardIndex = 0;

  return (
    <div className="max-w-3xl mx-auto px-4 py-6 space-y-6">
      {severities.map((severity) => {
        const items = grouped[severity]
        if (items.length === 0) return null
        const cfg = SECTION_CONFIG[severity]

        return (
          <section key={severity}>
            {/* Section header */}
            <div
              className={`flex items-center justify-between px-4 py-2.5 rounded-lg
                          border mb-4 shadow-sm animate-pop-in ${cfg.headerBg}`}
            >
              <span className={`text-sm font-semibold ${cfg.textColor}`}>
                {cfg.label}
              </span>
              <span
                className={`text-xs font-semibold px-2.5 py-0.5 rounded-full ${cfg.countBg}`}
              >
                {items.length}
              </span>
            </div>

            {/* Objection cards with staggered entrance animation */}
            <div className="space-y-4">
              {items.map((objection) => {
                const currentIndex = globalCardIndex++;
                return (
                  <div 
                    key={objection.id}
                    className="animate-slide-up"
                    style={{ 
                      animationDelay: `${currentIndex * 60}ms`, 
                      animationFillMode: 'both' 
                    }}
                  >
                    <ObjectionCard
                      objection={objection}
                      jobId={jobId}
                    />
                  </div>
                )
              })}
            </div>
          </section>
        )
      })}
    </div>
  )
}
