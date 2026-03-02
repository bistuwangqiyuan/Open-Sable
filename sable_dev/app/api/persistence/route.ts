import { NextRequest, NextResponse } from 'next/server';
import { saveSession, loadSession, restoreSession, clearSession, saveChatHistory, loadChatHistory } from '@/lib/persistence';

/**
 * GET /api/persistence - Load persisted session or chat history
 */
export async function GET(request: NextRequest) {
  const type = request.nextUrl.searchParams.get('type') || 'session';
  
  try {
    if (type === 'chat-history') {
      const messages = loadChatHistory();
      return NextResponse.json({
        success: true,
        hasData: !!messages,
        messages: messages || [],
      });
    }
    
    const session = loadSession();
    return NextResponse.json({
      success: true,
      hasSession: !!session,
      session,
    });
  } catch (error) {
    return NextResponse.json({
      success: false,
      error: (error as Error).message,
    }, { status: 500 });
  }
}

/**
 * POST /api/persistence - Save session, restore session, save chat history, or clear
 */
export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const { action, messages } = body;
    
    switch (action) {
      case 'save': {
        const saved = saveSession();
        return NextResponse.json({ success: saved });
      }
      
      case 'restore': {
        const restored = restoreSession();
        return NextResponse.json({ success: restored });
      }
      
      case 'save-chat': {
        if (!messages || !Array.isArray(messages)) {
          return NextResponse.json({ success: false, error: 'messages array required' }, { status: 400 });
        }
        const saved = saveChatHistory(messages);
        return NextResponse.json({ success: saved });
      }
      
      case 'clear': {
        const cleared = clearSession();
        return NextResponse.json({ success: cleared });
      }
      
      default:
        return NextResponse.json({
          success: false,
          error: 'Invalid action. Use: save, restore, save-chat, clear',
        }, { status: 400 });
    }
  } catch (error) {
    return NextResponse.json({
      success: false,
      error: (error as Error).message,
    }, { status: 500 });
  }
}
