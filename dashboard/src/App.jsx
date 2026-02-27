import { useState } from 'react';
import { useWebSocket } from './hooks/useWebSocket';
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
  const ws = useWebSocket();

  const panelProps = {
    chat:     { messages: ws.messages, streaming: ws.streaming, onSend: ws.sendMessage, onClear: ws.clearMessages },
    activity: { activity: ws.activity, onClear: ws.clearActivity },
    terminal: { terminal: ws.terminal, onClear: ws.clearTerminal },
    status:   { stats: ws.stats, sessions: ws.sessions, model: ws.model, activity: ws.activity },
    trading:  { stats: ws.stats, messages: ws.messages, streaming: ws.streaming, sendMessage: ws.sendMessage },
    tasks:    { streaming: ws.streaming, messages: ws.messages, activity: ws.activity, sendMessage: ws.sendMessage },
    history:  { messages: ws.messages, sessions: ws.sessions },
    thoughts: { ws: ws.wsRef, thoughts: ws.thoughts },
    qr:       {},
    agent:    {},
    devices:  {},
    settings: {},
  };

  const Panel = panels[tab];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <Topbar connected={ws.connected} model={ws.model} stats={ws.stats} />

      {ws.streaming && (
        <div style={{ height: 2, background: 'var(--accent-dim)', overflow: 'hidden' }}>
          <div style={{
            height: '100%', background: 'var(--accent)',
            animation: 'progress-slide 2s ease-in-out infinite',
          }} />
        </div>
      )}

      <div style={{ display: 'flex', flex: 1, minHeight: 0, overflow: 'hidden' }}>
        <Sidebar tab={tab} onTabChange={setTab} streaming={ws.streaming} />

        <div style={{ flex: 1, display: 'flex', overflow: 'hidden' }}>
          <Panel {...(panelProps[tab] || {})} />
        </div>
      </div>
    </div>
  );
}
