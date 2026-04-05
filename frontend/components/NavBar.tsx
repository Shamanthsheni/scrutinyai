'use client'
// frontend/components/NavBar.tsx

import { useRouter } from 'next/navigation'
import { useEffect, useState } from 'react'
import { supabase } from '../lib/supabase'

export default function NavBar() {
  const router = useRouter()
  const [userEmail, setUserEmail] = useState<string | null>(null)
  const [signingOut, setSigningOut] = useState(false)

  useEffect(() => {
    supabase.auth.getSession().then(({ data }) => {
      setUserEmail(data.session?.user?.email ?? null)
    })
  }, [])

  const handleSignOut = async () => {
    setSigningOut(true)
    await supabase.auth.signOut()
    router.push('/login')
  }

  // Get first letter of email for avatar
  const avatarLetter = userEmail ? userEmail.charAt(0).toUpperCase() : 'U'

  return (
    <>
      {/* Top thin green progress bar line */}
      <div className="h-[3px] w-full bg-teal fixed top-0 left-0 z-[60]" />
      
      <nav className="sticky top-[3px] z-50 bg-white border-b border-gray-200 px-6 py-3.5
                      flex items-center justify-between shadow-sm">
        {/* Left: wordmark + separator + court name */}
        <div className="flex items-center gap-3">
          <span className="text-teal text-[17px] font-medium tracking-tight">
            ScrutinyAI
          </span>
          <span className="text-gray-200 text-lg select-none">|</span>
          <span className="text-gray-text text-xs hidden sm:block">
            Karnataka High Court
          </span>
        </div>

        {/* Right: user email + sign out */}
        <div className="flex items-center gap-4">
          {userEmail && (
            <div className="flex items-center gap-2">
              <div className="w-7 h-7 rounded-full bg-teal text-white flex items-center justify-center text-xs font-bold">
                {avatarLetter}
              </div>
              <span className="text-gray-text text-xs hidden sm:block truncate max-w-xs font-medium">
                {userEmail}
              </span>
            </div>
          )}
          <button
            onClick={handleSignOut}
            disabled={signingOut}
            className="text-xs font-medium text-gray-600 border border-gray-300 rounded-lg
                       px-3 py-1.5 hover:border-teal hover:text-teal transition-colors
                       disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {signingOut ? 'Signing out…' : 'Sign out'}
          </button>
        </div>
      </nav>
    </>
  )
}
