'use client'
// frontend/components/LoadingSkeleton.tsx

export default function LoadingSkeleton() {
  return (
    <div className="animate-pulse">
      {/* Header skeleton — navy with shimmer */}
      <div className="bg-navy px-6 py-8">
        <div className="h-4 w-24 rounded bg-white/10 mb-4" />
        <div className="h-5 w-64 rounded bg-white/20 mb-2" />
        <div className="h-3 w-48 rounded bg-white/10 mb-6" />
        <div className="flex gap-2">
          <div className="h-7 w-24 rounded-full bg-white/10" />
          <div className="h-7 w-20 rounded-full bg-white/10" />
          <div className="h-7 w-20 rounded-full bg-white/10" />
        </div>
      </div>

      {/* Objection card skeletons */}
      <div className="max-w-3xl mx-auto px-4 py-6 space-y-3">
        {[1, 2, 3].map((i) => (
          <div
            key={i}
            className="bg-white border border-gray-200 rounded-lg p-4 space-y-3"
            style={{ borderLeft: '3px solid #e2e8f0' }}
          >
            <div className="flex gap-2">
              <div className="h-5 w-16 rounded-full bg-gray-200" />
              <div className="h-5 w-16 rounded-full bg-gray-200" />
            </div>
            <div className="h-4 w-3/4 rounded bg-gray-200" />
            <div className="h-3 w-1/2 rounded bg-gray-100" />
            <div className="h-12 rounded-lg bg-gray-100" />
          </div>
        ))}
      </div>
    </div>
  )
}
