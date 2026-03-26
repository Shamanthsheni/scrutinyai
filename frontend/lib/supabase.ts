// frontend/lib/supabase.ts
import { createBrowserClient } from '@supabase/ssr'

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL!
const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!

// Singleton pattern — reuse the same client across the app
let client: ReturnType<typeof createBrowserClient> | null = null

export function getSupabase() {
  if (!client) {
    client = createBrowserClient(supabaseUrl, supabaseAnonKey)
  }
  return client
}

export const supabase = getSupabase()
