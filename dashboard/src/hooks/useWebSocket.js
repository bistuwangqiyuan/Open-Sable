import { useState, useEffect, useRef, useCallback } from 'react';

function getWSUrl() {
  const proto = location.protocol === 'https:' ? 'wss' : 'ws';
  const params = new URLSearchParams(location.search);
  const token = params.get('token');
  return token
    ? `${proto}://${location.host}/?token=${encodeURIComponent(token)}`
    : `${proto}://${location.host}/`;
}

export function useWebSocket() {
  const [connected, setConnected] = useState(false);
  const [streaming, setStreaming] = useState(false);
  const [messages, setMessages] = useState([]);
  const [activity, setActivity] = useState([]);
  const [terminal, setTerminal] = useState([]);
  const [stats, setStats] = useState({});
  const [sessions, setSessions] = useState([]);
  const [model, setModel] = useState('');
  const [thoughts, setThoughts] = useState(null);

  const wsRef = useRef(null);
  const streamBuf = useRef('');
  const actIdRef = useRef(0);

  const addActivity = useCallback((type, icon, title, detail) => {
    const id = ++actIdRef.current;
    setActivity(prev => [{ id, type, icon, title, detail, ts: Date.now() / 1000 }, ...prev].slice(0, 200));
  }, []);

  const addTerminal = useCallback((text, cls = '') => {
    setTerminal(prev => [...prev, { text, cls }].slice(-500));
  }, []);

  const handleMonitorEvent = useCallback((event, data) => {
    switch (event) {
      case 'tool.start':
        addActivity('tool', '🔧', `Tool: ${data.name}`, data.args ? JSON.stringify(data.args).slice(0, 100) : '');
        addTerminal(`[tool.start] ${data.name}(${data.args ? JSON.stringify(data.args).slice(0, 80) : ''})`, 'cmd');
        break;
      case 'tool.done':
        if (data.success) {
          addActivity('success', '✅', `Tool done: ${data.name}`, `${data.duration_ms}ms`);
        } else {
          addActivity('error', '❌', `Tool failed: ${data.name}`, (data.result || '').slice(0, 80));
        }
        addTerminal(`[tool.done] ${data.name} → ${data.success ? 'OK' : 'FAIL'} (${data.duration_ms}ms)`, data.success ? '' : 'error');
        break;
      case 'thinking':
        addActivity('think', '🧠', 'Thinking', (data.message || '').slice(0, 100));
        addTerminal(`[thinking] Round ${data.round || '?'}: ${(data.message || '').slice(0, 100)}`, 'info');
        break;
      case 'reasoning':
        addActivity('think', '💭', 'Deep Reasoning', `${data.length} chars`);
        addTerminal(`[reasoning] (${data.length} chars)`, 'info');
        break;
      case 'thinking.done':
        addActivity('success', '💡', 'Thinking complete', '');
        break;
      case 'message.received':
        addActivity('info', '📥', 'Message received', (data.text || '').slice(0, 80));
        break;
      case 'response.sent':
        addActivity('success', '📤', 'Response sent', `${data.length} chars`);
        break;
      default:
        addActivity('info', '📌', event, JSON.stringify(data).slice(0, 80));
        addTerminal(`[${event}] ${JSON.stringify(data).slice(0, 120)}`, 'info');
        break;
    }
  }, [addActivity, addTerminal]);

  const handleMessage = useCallback((msg) => {
    switch (msg.type) {
      case 'connected':
        break;
      case 'message.start':
        streamBuf.current = '';
        setStreaming(true);
        addActivity('info', '💬', 'Processing', 'Agent is thinking…');
        break;
      case 'message.chunk':
        streamBuf.current += msg.text;
        setMessages(prev => {
          const copy = [...prev];
          if (copy.length && copy[copy.length - 1]._streaming) {
            copy[copy.length - 1] = { ...copy[copy.length - 1], content: streamBuf.current };
          } else {
            copy.push({ role: 'assistant', content: streamBuf.current, ts: Date.now(), _streaming: true });
          }
          return copy;
        });
        break;
      case 'message.done':
        setStreaming(false);
        setMessages(prev => {
          const copy = [...prev];
          if (copy.length && copy[copy.length - 1]._streaming) {
            copy[copy.length - 1] = { role: 'assistant', content: msg.text, ts: Date.now() };
          } else {
            copy.push({ role: 'assistant', content: msg.text, ts: Date.now() });
          }
          return copy;
        });
        addActivity('success', '✅', 'Response sent', (msg.text || '').slice(0, 80));
        break;
      case 'progress':
        addActivity('info', '⚡', 'Progress', msg.text || '');
        addTerminal(`[progress] ${msg.text}`, 'info');
        break;
      case 'error':
        setStreaming(false);
        setMessages(prev => [...prev, { role: 'assistant', content: '⚠️ ' + msg.text, ts: Date.now() }]);
        addActivity('error', '❌', 'Error', msg.text);
        addTerminal(`[error] ${msg.text}`, 'error');
        break;
      case 'status':
        setStats(msg);
        if (msg.model) setModel(msg.model);
        break;
      case 'sessions.list.result':
        setSessions(msg.sessions || []);
        break;
      case 'monitor.subscribed':
        addActivity('info', '📡', 'Monitor', 'Subscribed to real-time events');
        break;
      case 'monitor.event':
        handleMonitorEvent(msg.event, msg.data || {});
        break;
      case 'monitor.snapshot':
        if (msg.model) setModel(msg.model);
        break;
      case 'thoughts.list.result':
        setThoughts(msg);
        break;
      default:
        break;
    }
  }, [addActivity, addTerminal, handleMonitorEvent]);

  const connect = useCallback(() => {
    const ws = new WebSocket(getWSUrl());
    wsRef.current = ws;

    ws.onopen = () => {
      setConnected(true);
      addActivity('info', '🔗', 'Connected', 'WebSocket connection established');
      ws.send(JSON.stringify({ type: 'status' }));
      ws.send(JSON.stringify({ type: 'sessions.list' }));
      ws.send(JSON.stringify({ type: 'monitor.subscribe' }));
      ws.send(JSON.stringify({ type: 'thoughts.list', limit: 500 }));
    };

    ws.onclose = () => {
      setConnected(false);
      addActivity('error', '🔌', 'Disconnected', 'Reconnecting in 3s…');
      setTimeout(connect, 3000);
    };

    ws.onerror = () => {};
    ws.onmessage = (evt) => {
      try { handleMessage(JSON.parse(evt.data)); } catch {}
    };
  }, [addActivity, handleMessage]);

  useEffect(() => {
    connect();
    const iv = setInterval(() => {
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        wsRef.current.send(JSON.stringify({ type: 'status' }));
      }
    }, 5000);
    return () => clearInterval(iv);
  }, [connect]);

  const sendMessage = useCallback((text) => {
    if (!text || !wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) return;
    setMessages(prev => [...prev, { role: 'user', content: text, ts: Date.now() }]);
    if (text.startsWith('/')) {
      wsRef.current.send(JSON.stringify({ type: 'command', text, session_id: 'webchat_default' }));
    } else {
      wsRef.current.send(JSON.stringify({ type: 'message', text, session_id: 'webchat_default', user_id: 'dashboard_user' }));
    }
  }, []);

  const clearMessages = useCallback(() => setMessages([]), []);
  const clearActivity = useCallback(() => setActivity([]), []);
  const clearTerminal = useCallback(() => setTerminal([]), []);

  return {
    connected, streaming, messages, activity, terminal, stats, sessions, model, thoughts,
    sendMessage, clearMessages, clearActivity, clearTerminal, wsRef,
  };
}
