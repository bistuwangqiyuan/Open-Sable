import { useState, useCallback, useRef } from 'react';
import { useWebSocket } from './hooks/useWebSocket';
import { useMultiAgent } from './hooks/useMultiAgent';
import Sidebar from './components/layout/Sidebar';
import Topbar from './components/layout/Topbar';
import ChatPanel from './components/chat/ChatPanel';
import ActivityPanel from './components/chat/ActivityPanel';
import TerminalPanel from './components/chat/TerminalPanel';
import StatusPanel from './components/chat/StatusPanel';
import TradingPanel from './components/trading/TradingPanel';
import TaskPanel from './components/assistant/TaskPanel';
import HistoryPanel from './components/assistant/HistoryPanel';
import QRPanel from './components/agent/QRPanel';
import AgentPanel from './components/agent/AgentPanel';
import DevicesPanel from './components/agent/DevicesPanel';
import ThoughtsPanel from './components/agent/ThoughtsPanel';
import SettingsPanel from './components/settings/SettingsPanel';

const panels = {
  chat: ChatPanel,
  activity: ActivityPanel,
  terminal: TerminalPanel,
  status: StatusPanel,
  trading: TradingPanel,
  tasks: TaskPanel,
  history: HistoryPanel,
  thoughts: ThoughtsPanel,
  qr: QRPanel,
  agent: AgentPanel,
  devices: DevicesPanel,
  settings: SettingsPanel,
};

export default function App() {
  const [tab, setTab] = useState('chat');

  // Multi-agent: create external message handler first, pass to useWebSocket
  const multiAgentRef = useRef(null);
  const onExternalMessage = useCallback((msg) => {
    if (!multiAgentRef.current) return false;
    // Route agents.* messages
    if (msg.type?.startsWith('agents.')) {
      return multiAgentRef.current.handleAgentMessage(msg);
    }
    // Route proxied messages (have _profile field)
    if (msg._profile) {
      return multiAgentRef.current.handleProxiedMessage(msg);
    }
    return false;
  }, []);

  const ws = useWebSocket(onExternalMessage);
  const ma = useMultiAgent(ws.wsRef, ws.connected);
  multiAgentRef.current = ma;

  // Determine if we're viewing a remote agent or the current (local) agent
  const isLocal = !ma.currentAgent || ma.agents.some(a => a.is_current && a.name === ma.currentAgent);
  const remoteState = !isLocal ? (ma.agentStates[ma.currentAgent] || {}) : null;

  // Build panel props — for current agent use live ws data, for remote use proxied state
  // (no useMemo: ws is a new object every render so the memo never saves work)
  let panelProps;
  if (isLocal) {
    panelProps = {
      chat:     { messages: ws.messages, streaming: ws.streaming, onSend: ws.sendMessage, onClear: ws.clearMessages },
      activity: { activity: ws.activity, onClear: ws.clearActivity },
      terminal: { terminal: ws.terminal, onClear: ws.clearTerminal },
      status:   { stats: ws.stats, sessions: ws.sessions, model: ws.model, activity: ws.activity },
      trading:  { stats: ws.stats, messages: ws.messages, streaming: ws.streaming, sendMessage: ws.sendMessage },
      tasks:    { streaming: ws.streaming, messages: ws.messages, activity: ws.activity, sendMessage: ws.sendMessage },
      history:  { messages: ws.messages, sessions: ws.sessions },
      thoughts: { ws: ws.wsRef, thoughts: ws.thoughts, connected: ws.connected },
      qr:       {},
      agent:    {},
      devices:  {},
      settings: {},
    };
  } else {
    // Remote agent — interactive view via proxy
    const rs = remoteState || {};
    const sendToRemote = (text) => ma.sendToAgent(ma.currentAgent, text);
    const clearRemoteMsgs = () => {};
    panelProps = {
      chat:     { messages: rs.messages || [], streaming: rs.streaming || false, onSend: sendToRemote, onClear: clearRemoteMsgs },
      activity: { activity: rs.activity || [], onClear: () => {} },
      terminal: { terminal: rs.terminal || [], onClear: () => {} },
      status:   { stats: rs.stats || {}, sessions: rs.sessions || [], model: rs.model || '', activity: rs.activity || [] },
      trading:  { stats: rs.stats || {}, messages: rs.messages || [], streaming: rs.streaming || false, sendMessage: sendToRemote },
      tasks:    { streaming: rs.streaming || false, messages: rs.messages || [], activity: rs.activity || [], sendMessage: sendToRemote },
      history:  { messages: rs.messages || [], sessions: rs.sessions || [] },
      thoughts: { ws: { current: null }, thoughts: rs.thoughts, connected: rs.connected || false },
      qr:       {},
      agent:    {},
      devices:  {},
      settings: {},
    };
  }

  const Panel = panels[tab];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <Topbar
        connected={ws.connected}
        model={isLocal ? ws.model : (remoteState?.model || '')}
        stats={isLocal ? ws.stats : (remoteState?.stats || {})}
        agents={ma.agents}
        currentAgent={ma.currentAgent}
        onAgentSelect={ma.setCurrentAgent}
      />

      {(isLocal ? ws.streaming : remoteState?.streaming) && (
        <div style={{ height: 2, background: 'var(--accent-dim)', overflow: 'hidden' }}>
          <div style={{
            height: '100%', background: 'var(--accent)',
            animation: 'progress-slide 2s ease-in-out infinite',
          }} />
        </div>
      )}

      <div style={{ display: 'flex', flex: 1, minHeight: 0, overflow: 'hidden' }}>
        <Sidebar tab={tab} onTabChange={setTab} streaming={isLocal ? ws.streaming : (remoteState?.streaming || false)} />

        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
          {!isLocal && ma.currentAgent && (
            <div style={{
              padding: '4px 16px', fontSize: 11, fontWeight: 600,
              background: 'var(--accent-dim)', color: 'var(--accent-light)',
              borderBottom: '1px solid var(--border)', textTransform: 'uppercase',
              letterSpacing: '0.5px', display: 'flex', alignItems: 'center', gap: 6,
            }}>
              <span style={{ width: 6, height: 6, borderRadius: '50%', background: 'var(--green)' }} />
              Viewing: {ma.currentAgent}
            </div>
          )}
          <div style={{ flex: 1, display: 'flex', overflow: 'hidden' }}>
            <Panel key={ma.currentAgent || '_local'} {...(panelProps[tab] || {})} />
          </div>
        </div>
      </div>
    </div>
  );
}
