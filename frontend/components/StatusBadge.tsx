'use client'
// frontend/components/StatusBadge.tsx

interface StatusBadgeProps {
  status: string
}

export default function StatusBadge({ status }: StatusBadgeProps) {
  if (status === 'queued') {
    return (
      <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full
                       bg-gray-100 text-gray-500 text-xs font-medium">
        <span className="w-1.5 h-1.5 rounded-full bg-gray-400" />
        Queued
      </span>
    )
  }

  if (status === 'processing') {
    return (
      <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full
                       bg-blue-50 text-blue-600 text-xs font-medium">
        <span className="w-1.5 h-1.5 rounded-full bg-blue-400 animate-pulse" />
        Processing…
      </span>
    )
  }

  if (status === 'complete') {
    return (
      <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full
                       bg-teal-light text-teal text-xs font-medium">
        <span className="w-1.5 h-1.5 rounded-full bg-teal" />
        Complete
      </span>
    )
  }

  if (status === 'failed') {
    return (
      <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full
                       bg-red-custom/10 text-red-custom text-xs font-medium">
        <span className="w-1.5 h-1.5 rounded-full bg-red-custom" />
        Failed
      </span>
    )
  }

  return (
    <span className="inline-flex items-center px-2 py-0.5 rounded-full
                     bg-gray-100 text-gray-400 text-xs font-medium">
      {status}
    </span>
  )
}
