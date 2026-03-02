import { NextResponse } from 'next/server';

declare global {
  var lastViteError: { error: string; file: string; timestamp: number } | null;
}

// Returns latest Vite compile error captured by the dev server process
export async function GET() {
  const err = global.lastViteError;

  // Only report errors from the last 30 seconds (stale errors are irrelevant)
  if (err && Date.now() - err.timestamp < 30_000) {
    return NextResponse.json({
      success: true,
      hasError: true,
      error: err.error,
      file: err.file,
      timestamp: err.timestamp
    });
  }

  return NextResponse.json({
    success: true,
    hasError: false,
    error: null
  });
}

// POST to clear the error (after successful fix)
export async function POST() {
  global.lastViteError = null;
  return NextResponse.json({ success: true, cleared: true });
}
}