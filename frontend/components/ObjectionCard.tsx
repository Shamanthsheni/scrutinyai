'use client'
// frontend/components/ObjectionCard.tsx

import { useState } from 'react'
import type { Objection } from '../types'
import { submitFeedback } from '../lib/api'

interface ObjectionCardProps {
  objection: Objection
  jobId: string
}

const CATEGORY_STYLES: Record<string, string> = {
  FORMAT:    'bg-gray-100 text-gray-600',
  STRUCTURE: 'bg-blue-50 text-blue-600',
  FISCAL:    'bg-purple-50 text-purple-600',
}

const SEVERITY_BADGE: Record<string, string> = {
  CRITICAL: 'bg-red-custom/10 text-red-custom',
  MAJOR:    'bg-amber-custom/10 text-amber-custom',
  MINOR:    'bg-gray-100 text-gray-500',
}

const LEFT_BORDER: Record<string, string> = {
  CRITICAL: '#a32d2d',
  MAJOR:    '#854f0b',
  MINOR:    '#888780',
}

export default function ObjectionCard({ objection, jobId }: ObjectionCardProps) {
  const [feedbackGiven, setFeedbackGiven] = useState(false)
  const [feedbackLoading, setFeedbackLoading] = useState(false)

  const handleFeedback = async (isCorrect: boolean) => {
    if (feedbackGiven || feedbackLoading) return
    setFeedbackLoading(true)
    try {
      await submitFeedback(objection.id, jobId, isCorrect)
      setFeedbackGiven(true)
    } catch {
      // silently fail — feedback is non-critical
    } finally {
      setFeedbackLoading(false)
    }
  }

  return (
    <div
      className="bg-white rounded-lg border border-gray-200 p-4 mb-2"
      style={{ borderLeft: `3px solid ${LEFT_BORDER[objection.severity] ?? '#e2e8f0'}` }}
    >
      {/* Top row: badges */}
      <div className="flex items-start justify-between gap-2 flex-wrap">
        <div className="flex gap-1.5 flex-wrap">
          <span
            className={`inline-block px-2 py-0.5 rounded-full text-xs font-medium ${CATEGORY_STYLES[objection.category] ?? 'bg-gray-100 text-gray-500'}`}
          >
            {objection.category}
          </span>
          <span
            className={`inline-block px-2 py-0.5 rounded-full text-xs font-medium ${SEVERITY_BADGE[objection.severity] ?? 'bg-gray-100 text-gray-500'}`}
          >
            {objection.severity}
          </span>
        </div>

        {objection.requires_manual_verification && (
          <span className="inline-block px-2 py-0.5 rounded-full text-[11px] font-medium
                           bg-amber-custom/10 text-amber-custom whitespace-nowrap">
            Verify manually
          </span>
        )}
      </div>

      {/* Description */}
      <p className="text-sm font-medium text-[#1a2744] mt-2 leading-snug">
        {objection.description}
      </p>

      {/* Rule citation */}
      <p className="text-xs text-gray-text mt-1">{objection.rule_citation}</p>

      {/* Page references */}
      {objection.page_references.length > 0 && (
        <p className="text-xs text-gray-text mt-0.5">
          Pages: {objection.page_references.join(', ')}
        </p>
      )}

      {/* Suggested fix */}
      {objection.suggested_fix && (
        <div
          className="mt-2.5 rounded-r-md px-3 py-2 text-[13px] text-gray-600 leading-snug"
          style={{
            background: '#f8fafc',
            borderLeft: '2px solid #0f6e56',
          }}
        >
          <span className="text-teal font-medium">Suggested fix: </span>
          {objection.suggested_fix}
        </div>
      )}

      {/* Feedback row */}
      <div className="flex items-center justify-between mt-3 pt-2.5 border-t border-gray-100">
        <span className="text-xs text-gray-text">Was this correct?</span>

        {feedbackGiven ? (
          <span className="text-xs text-gray-text italic">Thank you for your feedback</span>
        ) : (
          <div className="flex gap-2">
            <button
              onClick={() => handleFeedback(true)}
              disabled={feedbackLoading}
              className="text-xs border border-gray-300 rounded-md px-2.5 py-1
                         hover:border-teal hover:text-teal transition-colors
                         disabled:opacity-50 disabled:cursor-not-allowed"
            >
              ✓ Correct
            </button>
            <button
              onClick={() => handleFeedback(false)}
              disabled={feedbackLoading}
              className="text-xs border border-gray-300 rounded-md px-2.5 py-1
                         hover:border-red-custom hover:text-red-custom transition-colors
                         disabled:opacity-50 disabled:cursor-not-allowed"
            >
              ✗ Incorrect
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
