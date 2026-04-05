'use client'
// frontend/components/StatusBadge.tsx

interface StatusBadgeProps {
  status: string
}

export default function StatusBadge({ status }: StatusBadgeProps) {
  if (status === 'queued') {
    return (
      <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full
                       bg-gray-100 text-gray-500 text-xs font-semibold shadow-sm border border-gray-200">
        <span className="relative flex h-2 w-2">
          <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-gray-400 opacity-75"></span>
          <span className="relative inline-flex rounded-full h-2 w-2 bg-gray-500"></span>
        </span>
        Queued...
      </span>
    )
  }

  if (status === 'processing') {
    return (
      <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full
                       bg-blue-50 text-blue-600 border border-blue-200 text-xs font-semibold shadow-sm">
        <svg className="animate-spin h-3 w-3 text-blue-600" viewBox="0 0 24 24" fill="none">
          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
        </svg>
        Processing
      </span>
    )
  }

  if (status === 'complete') {
    return (
      <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full
                       bg-teal-light text-teal border border-teal/20 text-xs font-semibold shadow-sm">
        <svg className="w-3 h-3 text-teal" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 13l4 4L19 7" />
        </svg>
        Complete
      </span>
    )
  }

  if (status === 'failed') {
    return (
      <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full
                       bg-red-custom/10 text-red-custom border border-red-custom/20 text-xs font-semibold shadow-sm">
        <svg className="w-3 h-3 text-red-custom" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M6 18L18 6M6 6l12 12" />
        </svg>
        Failed
      </span>
    )
  }

  return (
    <span className="inline-flex items-center px-2 py-0.5 rounded-full
                     bg-gray-100 text-gray-500 text-xs font-medium">
      {status}
    </span>
  )
}
