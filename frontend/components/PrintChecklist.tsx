'use client'
// frontend/components/PrintChecklist.tsx

import type { CheckResult } from '../types'

interface PrintChecklistProps {
  result: CheckResult
  filename: string
}

function formatDateForPrint(dateStr: string): string {
  const d = new Date(dateStr)
  return d.toLocaleDateString('en-IN', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  }) + ' ' + d.toLocaleTimeString('en-IN', {
    hour: '2-digit',
    minute: '2-digit',
  })
}

export default function PrintChecklist({ result, filename }: PrintChecklistProps) {
  const total = result.critical_count + result.major_count + result.minor_count
  const hasStoppingObjections = result.critical_count > 0 || result.major_count > 0

  // Sort logically: CRITICAL -> MAJOR -> MINOR
  const sortedObjections = [...result.objections].sort((a, b) => {
    const weights = { CRITICAL: 1, MAJOR: 2, MINOR: 3 }
    return weights[a.severity] - weights[b.severity]
  })

  return (
    <>
      {/* On-screen Print Button */}
      <button
        onClick={() => window.print()}
        title="Print checklist form"
        className="bg-white/10 hover:bg-white/20 border border-white/20 hover:border-white/40
                   text-white text-xs font-semibold px-4 py-2 rounded-lg 
                   transition-all flex items-center gap-2"
      >
        <svg width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} 
                d="M17 17h2a2 2 0 002-2v-4a2 2 0 00-2-2H5a2 2 0 00-2 2v4a2 2 0 002 2h2m2 4h6a2 2 0 002-2v-4a2 2 0 00-2-2H9a2 2 0 00-2 2v4a2 2 0 002 2zm8-12V5a2 2 0 00-2-2H9a2 2 0 00-2 2v4h10z" />
        </svg>
        Print checklist
      </button>

      {/* Hidden Printable Checklist Component */}
      <div id="print-checklist" className="hidden print:block font-serif text-black bg-white" style={{ fontFamily: '"Times New Roman", Times, serif' }}>
        
        {/* Header */}
        <div className="text-center mb-6">
          <h1 className="text-[14pt] font-bold uppercase tracking-wide">
            IN THE HIGH COURT OF KARNATAKA
          </h1>
          <h2 className="text-[14pt] font-bold mb-2">
            Pre-Filing Scrutiny Checklist
          </h2>
          <hr className="border-black border-t-2 mb-2" />
          <div className="text-left text-[11pt] space-y-1 mb-2">
            <p><strong>Document:</strong> {filename}</p>
            <p><strong>Checked by ScrutinyAI on:</strong> {formatDateForPrint(result.checked_at)}</p>
            <p><strong>Checklist Version:</strong> v{result.checklist_version}</p>
          </div>
          <hr className="border-black border-t-2 mb-4" />
        </div>

        {/* Summary Box */}
        <div className="border border-black p-4 mb-6 text-[11pt]">
          <p className="mb-1 font-bold">Total objections: {total}</p>
          <p className="mb-2">
            Critical: {result.critical_count} &nbsp;|&nbsp; Major: {result.major_count} &nbsp;|&nbsp; Minor: {result.minor_count}
          </p>
          <p className="font-bold underline">
            {hasStoppingObjections 
              ? 'Status: OBJECTIONS FOUND — Do not file until rectified'
              : 'Status: CLEAR — May proceed to file'}
          </p>
        </div>

        {/* Objections Table */}
        <table className="w-full text-left text-[10pt] border-collapse mb-10 print:break-inside-auto">
          <thead>
            <tr>
              <th className="border-b-2 border-black pb-2 font-bold w-[5%] bg-white">#</th>
              <th className="border-b-2 border-black pb-2 font-bold w-[10%] bg-white">Section</th>
              <th className="border-b-2 border-black pb-2 font-bold w-[10%] bg-white">Severity</th>
              <th className="border-b-2 border-black pb-2 font-bold w-[35%] bg-white">Objection</th>
              <th className="border-b-2 border-black pb-2 font-bold w-[30%] bg-white">Suggested Fix</th>
              <th className="border-b-2 border-black pb-2 font-bold w-[10%] bg-white text-center">Rectified</th>
            </tr>
          </thead>
          <tbody>
            {sortedObjections.length === 0 ? (
              <tr>
                <td colSpan={6} className="py-4 text-center italic border-b border-gray-300">
                  No objections found in this document.
                </td>
              </tr>
            ) : (
              sortedObjections.map((o, index) => {
                let severityColor = '#000000';
                if (o.severity === 'CRITICAL') severityColor = '#a32d2d';
                else if (o.severity === 'MAJOR') severityColor = '#854f0b';
                else if (o.severity === 'MINOR') severityColor = '#5f5e5a';

                const bgColor = index % 2 === 0 ? '#ffffff' : '#f8fafc';

                return (
                  <tr key={o.id} style={{ backgroundColor: bgColor }} className="print:break-inside-avoid">
                    <td className="py-2.5 px-1 border-b border-gray-300 align-top">{index + 1}</td>
                    <td className="py-2.5 px-1 border-b border-gray-300 align-top">{o.category}</td>
                    <td className="py-2.5 px-1 border-b border-gray-300 align-top font-bold" style={{ color: severityColor }}>
                      {o.severity}
                    </td>
                    <td className="py-2.5 px-1 border-b border-gray-300 align-top pr-4">
                      <strong>[{o.checklist_point_id}]</strong> {o.description}
                    </td>
                    <td className="py-2.5 px-1 border-b border-gray-300 align-top pr-4">
                      {o.suggested_fix}
                    </td>
                    <td className="py-2.5 px-1 border-b border-gray-300 text-center align-middle">
                      <div className="w-5 h-5 border border-black mx-auto bg-white" />
                    </td>
                  </tr>
                )
              })
            )}
          </tbody>
        </table>

        {/* Footer (CSS repeated via position fixed or native media print rules) */}
        <div className="w-full text-[9pt] text-gray-700 pt-2 border-t border-black print:block hidden mb-4" style={{ position: 'fixed', bottom: 0 }}>
          <div className="flex justify-between items-end">
            <div>
              <p>Generated by ScrutinyAI · Karnataka High Court Pre-Filing Checker · Not an official court document</p>
              <p className="italic">This checklist is for advocate reference only. The registry's objection list is the authoritative record.</p>
            </div>
            {/* The page counter logic should map via CSS @page counter if browser supports, otherwise browser native controls inject it */}
            <div className="text-right whitespace-nowrap hidden sm:block">
              <span className="page-number-counter"></span>
            </div>
          </div>
        </div>
        
      </div>
    </>
  )
}
