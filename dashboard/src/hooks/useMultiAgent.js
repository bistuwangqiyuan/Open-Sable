import { useState, useEffect, useCallback, useRef } from 'react';

/**
 * Multi-agent manager hook.
 *
 * Sends `agents.list` via the existing WebSocket to discover all profiles,
 * then subscribes to running agents' events via `agents.subscribe`.
 * Each agent's state (stats, activity, sessions, thoughts, messages) is
 * stored independently, keyed by profile name.
 */
export function useMultiAgent(wsRef, connected) {
  const [agents, setAgents] = useState([]);           // [{ name, running, is_current }]
  const [currentAgent, setCurrentAgent] = useState(''); // which agent tab is selected
  const [agentStates, setAgentStates] = useState({});   // { [profile]: { stats, activity, sessions, thoughts } }
  const subscribedRef = useRef(new Set());
  const pollRef = useRef(null);
  const currentAgentRef = useRef(''); // stable ref for closures

  // Keep ref in sync with state
  const _setCurrentAgent = useCallback((name) => {
    currentAgentRef.current = name;
    setCurrentAgent(name);
  }, []);

  // ── Request agent list ─────────────────────────────────────────────────
  const refreshAgents = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: 'agents.list' }));
    }
  }, [wsRef]);

  // ── Subscribe to a remote agent's events ───────────────────────────────
  const subscribeAgent = useCallback((profile) => {
    if (subscribedRef.current.has(profile)) return;
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: 'agents.subscribe', profile }));
      subscribedRef.current.add(profile);
    }
  }, [wsRef]);

  // ── Unsubscribe from a remote agent ────────────────────────────────────
  const unsubscribeAgent = useCallback((profile) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: 'agents.unsubscribe', profile }));
    }
    subscribedRef.current.delete(profile);
  }, [wsRef]);

  // ── Process incoming multi-agent messages ──────────────────────────────
  const handleAgentMessage = useCallback((msg) => {
    switch (msg.type) {
      case 'agents.list.result': {
        setAgents(msg.agents || []);
        if (!currentAgentRef.current && msg.current) {
          _setCurrentAgent(msg.current);
        }

        // Auto-subscribe to all running non-current agents
        for (const agent of (msg.agents || [])) {
          if (agent.running && !agent.is_current && !subscribedRef.current.has(agent.name)) {
            subscribeAgent(agent.name);
          }
        }
        break;
      }

      case 'agents.status.result': {
        const profile = msg.profile;
        if (profile) {
          setAgentStates(prev => ({
            ...prev,
            [profile]: {
              ...(prev[profile] || {}),
              stats: { ...msg, type: undefined, _profile: undefined },
              connected: msg.running !== false,
            },
          }));
        }
        break;
      }

      case 'agents.subscribed': {
        const profile = msg.profile;
        if (msg.status === 'connected') {
          setAgentStates(prev => ({
            ...prev,
            [profile]: {
              ...(prev[profile] || {}),
              connected: true,
              activity: prev[profile]?.activity || [],
              messages: prev[profile]?.messages || [],
              terminal: prev[profile]?.terminal || [],
            },
          }));
        } else if (msg.status === 'offline') {
          subscribedRef.current.delete(profile);
          setAgentStates(prev => ({
            ...prev,
            [profile]: { ...(prev[profile] || {}), connected: false },
          }));
        }
        break;
      }

      case 'agents.disconnected': {
        const profile = msg.profile;
        subscribedRef.current.delete(profile);
        setAgentStates(prev => ({
          ...prev,
          [profile]: { ...(prev[profile] || {}), connected: false },
        }));
        break;
      }

      case 'agents.unsubscribed':
        break;

      default:
        return false; // not handled here
    }
    return true;
  }, [_setCurrentAgent, subscribeAgent]);

  // ── Process proxied messages from remote agents ────────────────────────
  const handleProxiedMessage = useCallback((msg) => {
    const profile = msg._profile;
    if (!profile) return false;

    const actId = { current: 0 };

    setAgentStates(prev => {
      const state = prev[profile] || {
        stats: {}, activity: [], messages: [], terminal: [],
        sessions: [], thoughts: null, connected: true,
        model: '', streaming: false,
      };

      const newState = { ...state };

      switch (msg.type) {
        case 'status':
          newState.stats = { ...msg, _profile: undefined };
          if (msg.model) newState.model = msg.model;
          break;

        case 'sessions.list.result':
          newState.sessions = msg.sessions || [];
          break;

        case 'thoughts.list.result':
          newState.thoughts = msg;
          break;

        case 'monitor.subscribed':
          break;

        case 'monitor.event': {
          const event = msg.event;
          const data = msg.data || {};
          let act = null;
          let term = null;

          switch (event) {
            case 'tool.start':
              act = { type: 'tool', icon: '🔧', title: `Tool: ${data.name}`, detail: data.args ? JSON.stringify(data.args).slice(0, 100) : '' };
              term = { text: `[tool.start] ${data.name}(${data.args ? JSON.stringify(data.args).slice(0, 80) : ''})`, cls: 'cmd' };
              break;
            case 'tool.done':
              act = data.success
                ? { type: 'success', icon: '✅', title: `Tool done: ${data.name}`, detail: `${data.duration_ms}ms` }
                : { type: 'error', icon: '❌', title: `Tool failed: ${data.name}`, detail: (data.result || '').slice(0, 80) };
              term = { text: `[tool.done] ${data.name} → ${data.success ? 'OK' : 'FAIL'} (${data.duration_ms}ms)`, cls: data.success ? '' : 'error' };
              break;
            case 'thinking':
              act = { type: 'think', icon: '🧠', title: 'Thinking', detail: (data.message || '').slice(0, 100) };
              term = { text: `[thinking] Round ${data.round || '?'}: ${(data.message || '').slice(0, 100)}`, cls: 'info' };
              break;
            case 'reasoning':
              act = { type: 'think', icon: '💭', title: 'Deep Reasoning', detail: `${data.length} chars` };
              term = { text: `[reasoning] (${data.length} chars)`, cls: 'info' };
              break;
            case 'thinking.done':
              act = { type: 'success', icon: '💡', title: 'Thinking complete', detail: '' };
              break;
            case 'message.received':
              act = { type: 'info', icon: '📥', title: 'Message received', detail: (data.text || '').slice(0, 80) };
              break;
            case 'response.sent':
              act = { type: 'success', icon: '📤', title: 'Response sent', detail: `${data.length} chars` };
              break;
            default:
              act = { type: 'info', icon: '📌', title: event, detail: JSON.stringify(data).slice(0, 80) };
              term = { text: `[${event}] ${JSON.stringify(data).slice(0, 120)}`, cls: 'info' };
              break;
          }

          if (act) {
            const id = ++actId.current;
            newState.activity = [{ id, ...act, ts: Date.now() / 1000 }, ...(state.activity || [])].slice(0, 200);
          }
          if (term) {
            newState.terminal = [...(state.terminal || []), term].slice(-500);
          }
          break;
        }

        case 'monitor.snapshot':
          if (msg.model) newState.model = msg.model;
          break;

        case 'message.start':
          newState.streaming = true;
          break;

        case 'message.done':
          newState.streaming = false;
          if (msg.text) {
            newState.messages = [...(state.messages || []),
              { role: 'assistant', content: msg.text, ts: Date.now() },
            ];
          }
          break;

        case 'progress': {
          const id = ++actId.current;
          newState.activity = [{ id, type: 'info', icon: '⚡', title: 'Progress', detail: msg.text || '', ts: Date.now() / 1000 },
            ...(state.activity || [])].slice(0, 200);
          newState.terminal = [...(state.terminal || []), { text: `[progress] ${msg.text}`, cls: 'info' }].slice(-500);
          break;
        }

        case 'error': {
          const id = ++actId.current;
          newState.activity = [{ id, type: 'error', icon: '❌', title: 'Error', detail: msg.text || '', ts: Date.now() / 1000 },
            ...(state.activity || [])].slice(0, 200);
          newState.terminal = [...(state.terminal || []), { text: `[error] ${msg.text}`, cls: 'error' }].slice(-500);
          break;
        }

        case 'connected':
          newState.connected = true;
          break;

        default:
          break;
      }

      return { ...prev, [profile]: newState };
    });

    return true;
  }, []);

  // ── On connect: request agent list and poll periodically ───────────────
  useEffect(() => {
    if (!connected) {
      subscribedRef.current.clear();
      return;
    }

    refreshAgents();

    // Poll every 10s for agent list updates (new agents starting/stopping)
    pollRef.current = setInterval(refreshAgents, 10000);

    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, [connected, refreshAgents]);

  // ── Send chat message to a specific agent ─────────────────────────────
  const sendToAgent = useCallback((profile, text) => {
    if (!text || !wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) return;
    wsRef.current.send(JSON.stringify({
      type: 'agents.chat',
      profile,
      text,
      session_id: 'webchat_default',
      user_id: 'dashboard_user',
    }));
    // Optimistically add user message to remote state
    setAgentStates(prev => {
      const state = prev[profile] || { messages: [], activity: [], terminal: [], streaming: false };
      return {
        ...prev,
        [profile]: {
          ...state,
          messages: [...(state.messages || []), { role: 'user', content: text, ts: Date.now() }],
          streaming: true,
        },
      };
    });
  }, [wsRef]);

  return {
    agents,
    currentAgent,
    setCurrentAgent: _setCurrentAgent,
    agentStates,
    handleAgentMessage,
    handleProxiedMessage,
    refreshAgents,
    subscribeAgent,
    unsubscribeAgent,
    sendToAgent,
  };
}
