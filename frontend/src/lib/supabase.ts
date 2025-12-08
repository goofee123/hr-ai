/**
 * Supabase Client - AUTHENTICATION ONLY
 *
 * SECURITY NOTE: This client is ONLY used for authentication (login/logout/session).
 * ALL data access (candidates, compensation, etc.) MUST go through the FastAPI backend.
 *
 * This is critical for HR/PII data protection:
 * - Backend validates all permissions
 * - Backend logs all data access for audit
 * - No direct database queries from browser
 */

import { createClient } from "@supabase/supabase-js";

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL!;
const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!;

// This client is configured for AUTH ONLY
// Do NOT use supabase.from() to query tables directly
export const supabase = createClient(supabaseUrl, supabaseAnonKey, {
  auth: {
    autoRefreshToken: true,
    persistSession: true,
    detectSessionInUrl: true,
  },
  // Disable realtime and other features - we only need auth
  realtime: {
    params: {
      eventsPerSecond: 0,
    },
  },
});

// Helper to get current session token for API calls
export async function getAccessToken(): Promise<string | null> {
  const { data: { session } } = await supabase.auth.getSession();
  return session?.access_token || null;
}

// Auth-related types
export type AuthUser = {
  id: string;
  email: string;
  user_metadata: {
    full_name?: string;
    avatar_url?: string;
  };
};
