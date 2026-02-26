import { useState, useEffect, useCallback } from 'react';
import {
  Search, Download, ToggleLeft, ToggleRight, Trash2,
  Package, Star, Shield, Zap, RefreshCw,
} from 'lucide-react';

const s = {
  panel: { display: 'flex', flexDirection: 'column', flex: 1, overflow: 'hidden' },
  header: {
    display: 'flex', alignItems: 'center', gap: 8, padding: '12px 16px',
    borderBottom: '1px solid var(--border)', minHeight: 44, flexShrink: 0,
  },
  title: { fontSize: 13, fontWeight: 600 },
  body: { flex: 1, overflowY: 'auto', padding: 16 },
  tabs: {
    display: 'flex', gap: 4, marginBottom: 16, borderBottom: '1px solid var(--border)',
    paddingBottom: 8,
  },
  tab: (active) => ({
    padding: '6px 14px', borderRadius: 'var(--radius-sm)', border: 'none',
    background: active ? 'var(--accent-dim)' : 'transparent',
    color: active ? 'var(--accent-light)' : 'var(--text-muted)',
    cursor: 'pointer', fontSize: 12, fontWeight: 600,
  }),
  searchBox: {
    display: 'flex', gap: 8, marginBottom: 16,
  },
  searchInput: {
    flex: 1, padding: '8px 12px 8px 36px', borderRadius: 'var(--radius)',
    border: '1px solid var(--border)', background: 'var(--bg-primary)',
    color: 'var(--text)', fontSize: 12, outline: 'none',
  },
  skillCard: {
    padding: 14, borderRadius: 'var(--radius)', marginBottom: 8,
    border: '1px solid var(--border)', background: 'var(--bg-tertiary)',
    display: 'flex', gap: 12, alignItems: 'flex-start', transition: 'border-color .15s',
  },
  skillIcon: {
    width: 40, height: 40, borderRadius: 'var(--radius-sm)',
    display: 'flex', alignItems: 'center', justifyContent: 'center',
    fontSize: 20, flexShrink: 0,
  },
  skillName: { fontSize: 14, fontWeight: 700, marginBottom: 2 },
  skillDesc: { fontSize: 12, color: 'var(--text-muted)', lineHeight: 1.4 },
  skillMeta: { display: 'flex', gap: 8, marginTop: 6, fontSize: 10, color: 'var(--text-muted)' },
  badge: (color) => ({
    padding: '2px 6px', borderRadius: 99, fontSize: 10, fontWeight: 600,
    background: `var(--${color}-dim)`, color: `var(--${color})`,
  }),
  btn: (v) => ({
    padding: '6px 12px', borderRadius: 'var(--radius-sm)', border: 'none',
    cursor: 'pointer', fontSize: 11, fontWeight: 600, display: 'flex',
    alignItems: 'center', gap: 4,
    background: v === 'primary' ? 'var(--accent)' : v === 'danger' ? 'var(--red)' : 'var(--bg-hover)',
    color: v === 'primary' || v === 'danger' ? '#fff' : 'var(--text-secondary)',
  }),
  empty: {
    padding: 32, textAlign: 'center', color: 'var(--text-muted)', fontSize: 13,
  },
  section: { marginBottom: 24 },
  sectionTitle: { fontSize: 14, fontWeight: 700, marginBottom: 12 },
  automationCard: {
    padding: 14, borderRadius: 'var(--radius)', marginBottom: 8,
    border: '1px solid var(--border)', background: 'var(--bg-tertiary)',
  },
};

// Built-in skills
const BUILTIN_SKILLS = [
  { slug: 'web_search', name: 'Web Search', icon: '🔍', desc: 'Search the web using DuckDuckGo/Google', category: 'core', enabled: true },
  { slug: 'code_exec', name: 'Code Execution', icon: '💻', desc: 'Execute Python, JavaScript, and shell commands', category: 'core', enabled: true },
  { slug: 'file_manager', name: 'File Manager', icon: '📁', desc: 'Read, write, and organize files on disk', category: 'core', enabled: true },
  { slug: 'web_scraper', name: 'Web Scraper', icon: '🕷️', desc: 'Scrape and extract data from websites', category: 'web', enabled: true },
  { slug: 'image_gen', name: 'Image Generation', icon: '🎨', desc: 'Generate images with DALL-E or Stable Diffusion', category: 'creative', enabled: false },
  { slug: 'rag', name: 'RAG / Knowledge Base', icon: '📚', desc: 'Retrieval-augmented generation from documents', category: 'knowledge', enabled: true },
  { slug: 'trading', name: 'Trading Engine', icon: '📈', desc: 'Execute and manage cryptocurrency trades', category: 'trading', enabled: false },
  { slug: 'email', name: 'Email', icon: '📧', desc: 'Send and manage emails', category: 'communication', enabled: false },
  { slug: 'calendar', name: 'Calendar', icon: '📅', desc: 'Manage calendar events and reminders', category: 'productivity', enabled: true },
  { slug: 'doc_writer', name: 'Document Writer', icon: '✍️', desc: 'Create, summarize, and rewrite documents', category: 'creative', enabled: true },
];

export default function AgentPanel() {
  const [tab, setTab] = useState('skills');
  const [search, setSearch] = useState('');
  const [skills, setSkills] = useState(BUILTIN_SKILLS);
  const [marketSkills, setMarketSkills] = useState([]);
  const [loadingMarket, setLoadingMarket] = useState(false);

  const toggleSkill = (slug) => {
    setSkills(prev => prev.map(sk =>
      sk.slug === slug ? { ...sk, enabled: !sk.enabled } : sk
    ));
  };

  const searchMarketplace = useCallback(async (q) => {
    if (!q.trim()) return;
    setLoadingMarket(true);
    try {
      const res = await fetch(`/api/skills?q=${encodeURIComponent(q)}&limit=10`);
      if (res.ok) {
        const data = await res.json();
        setMarketSkills(data.skills || []);
      }
    } catch {}
    setLoadingMarket(false);
  }, []);

  const filteredSkills = skills.filter(sk => {
    if (!search.trim()) return true;
    const q = search.toLowerCase();
    return sk.name.toLowerCase().includes(q) || sk.desc.toLowerCase().includes(q);
  });

  return (
    <div style={s.panel}>
      <div style={s.header}>
        <span style={{ fontSize: 16 }}>🤖</span>
        <span style={s.title}>Agent Desktop</span>
      </div>
      <div style={s.body}>
        {/* Tabs */}
        <div style={s.tabs}>
          <button style={s.tab(tab === 'skills')} onClick={() => setTab('skills')}>Skills</button>
          <button style={s.tab(tab === 'marketplace')} onClick={() => setTab('marketplace')}>Marketplace</button>
          <button style={s.tab(tab === 'automations')} onClick={() => setTab('automations')}>Automations</button>
          <button style={s.tab(tab === 'files')} onClick={() => setTab('files')}>File Access</button>
        </div>

        {/* Skills Tab */}
        {tab === 'skills' && (
          <div>
            <div style={{ position: 'relative', marginBottom: 16 }}>
              <Search size={14} style={{ position: 'absolute', left: 12, top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)' }} />
              <input
                style={s.searchInput}
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Search skills…"
              />
            </div>

            <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 12 }}>
              {skills.filter(sk => sk.enabled).length} active / {skills.length} total
            </div>

            {filteredSkills.map(sk => (
              <div key={sk.slug} style={s.skillCard}>
                <div style={{ ...s.skillIcon, background: sk.enabled ? 'var(--accent-dim)' : 'var(--bg-hover)' }}>
                  {sk.icon}
                </div>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <span style={s.skillName}>{sk.name}</span>
                    <span style={s.badge(sk.enabled ? 'green' : 'yellow')}>
                      {sk.enabled ? 'Active' : 'Disabled'}
                    </span>
                    {sk.category === 'core' && <span style={s.badge('accent')}>Core</span>}
                  </div>
                  <div style={s.skillDesc}>{sk.desc}</div>
                  <div style={s.skillMeta}>
                    <span>🏷️ {sk.category}</span>
                  </div>
                </div>
                <button
                  style={{ background: 'none', border: 'none', cursor: 'pointer', color: sk.enabled ? 'var(--accent-light)' : 'var(--text-muted)' }}
                  onClick={() => toggleSkill(sk.slug)}
                  title={sk.enabled ? 'Disable' : 'Enable'}
                >
                  {sk.enabled ? <ToggleRight size={24} /> : <ToggleLeft size={24} />}
                </button>
              </div>
            ))}
          </div>
        )}

        {/* Marketplace Tab */}
        {tab === 'marketplace' && (
          <div>
            <div style={s.searchBox}>
              <div style={{ position: 'relative', flex: 1 }}>
                <Search size={14} style={{ position: 'absolute', left: 12, top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)' }} />
                <input
                  style={s.searchInput}
                  placeholder="Search marketplace…"
                  onKeyDown={(e) => { if (e.key === 'Enter') searchMarketplace(e.target.value); }}
                />
              </div>
            </div>

            {loadingMarket ? (
              <div style={s.empty}>
                <RefreshCw size={20} style={{ animation: 'spin 1s linear infinite', marginBottom: 8 }} />
                Searching…
              </div>
            ) : marketSkills.length === 0 ? (
              <div style={s.empty}>
                <Package size={32} style={{ opacity: .3, marginBottom: 8 }} />
                <div>Search the Skills Marketplace</div>
                <div style={{ fontSize: 11, marginTop: 4 }}>
                  Browse and install community skills from sk.opensable.com
                </div>
              </div>
            ) : (
              marketSkills.map(sk => (
                <div key={sk.slug} style={s.skillCard}>
                  <div style={{ ...s.skillIcon, background: 'var(--teal-dim)' }}>
                    {sk.icon || '📦'}
                  </div>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <span style={s.skillName}>{sk.name}</span>
                      {sk.verified && <Shield size={12} style={{ color: 'var(--green)' }} />}
                    </div>
                    <div style={s.skillDesc}>{sk.description}</div>
                    <div style={s.skillMeta}>
                      <span>⭐ {sk.avg_rating?.toFixed(1) || '–'}</span>
                      <span>📥 {sk.install_count || 0}</span>
                      <span>👤 {sk.author}</span>
                    </div>
                  </div>
                  <button style={s.btn('primary')}>
                    <Download size={12} /> Install
                  </button>
                </div>
              ))
            )}
          </div>
        )}

        {/* Automations Tab */}
        {tab === 'automations' && (
          <div>
            <p style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 16 }}>
              Define repeatable workflows the agent can execute automatically.
            </p>

            {[
              { name: 'Daily Folder Cleanup', trigger: 'Schedule: 09:00 daily', desc: 'Sort Downloads folder by file type', enabled: true },
              { name: 'Meeting Notes Summary', trigger: 'On file change: ~/Notes/', desc: 'Summarize new meeting notes into digest', enabled: true },
              { name: 'Code Review Assistant', trigger: 'Manual trigger', desc: 'Review staged git changes and provide feedback', enabled: false },
              { name: 'Backup Reports', trigger: 'Schedule: Fridays 17:00', desc: 'Generate weekly backup status report', enabled: false },
            ].map((auto, i) => (
              <div key={i} style={s.automationCard}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
                  <Zap size={16} style={{ color: auto.enabled ? 'var(--yellow)' : 'var(--text-muted)' }} />
                  <span style={{ fontSize: 14, fontWeight: 700 }}>{auto.name}</span>
                  <span style={s.badge(auto.enabled ? 'green' : 'yellow')}>
                    {auto.enabled ? 'Active' : 'Disabled'}
                  </span>
                </div>
                <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 4 }}>{auto.desc}</div>
                <div style={{ fontSize: 10, color: 'var(--text-muted)', fontFamily: 'var(--mono)' }}>
                  ⏰ {auto.trigger}
                </div>
              </div>
            ))}

            <button style={{
              width: '100%', padding: 12, borderRadius: 'var(--radius)',
              border: '1px dashed var(--border)', background: 'transparent',
              color: 'var(--text-muted)', cursor: 'pointer', fontSize: 13, marginTop: 8,
            }}>
              + Create New Automation
            </button>
          </div>
        )}

        {/* File Access Tab */}
        {tab === 'files' && (
          <div>
            <p style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 16 }}>
              Control which folders the agent can access. The agent cannot access any folder not listed here.
            </p>

            {[
              { path: '~/Documents', access: 'read-write', desc: 'Documents folder' },
              { path: '~/Downloads', access: 'read-only', desc: 'Downloads folder' },
              { path: '~/Projects', access: 'read-write', desc: 'Projects folder' },
            ].map((f, i) => (
              <div key={i} style={{
                display: 'flex', alignItems: 'center', gap: 12, padding: '10px 12px',
                background: 'var(--bg-tertiary)', borderRadius: 'var(--radius-sm)',
                marginBottom: 6, border: '1px solid var(--border)',
              }}>
                <span style={{ fontSize: 16 }}>📁</span>
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: 13, fontWeight: 600, fontFamily: 'var(--mono)' }}>{f.path}</div>
                  <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>{f.desc}</div>
                </div>
                <span style={s.badge(f.access === 'read-write' ? 'accent' : 'yellow')}>
                  {f.access}
                </span>
                <button style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer' }}>
                  <Trash2 size={14} />
                </button>
              </div>
            ))}

            <button style={{
              width: '100%', padding: 12, borderRadius: 'var(--radius)',
              border: '1px dashed var(--border)', background: 'transparent',
              color: 'var(--text-muted)', cursor: 'pointer', fontSize: 13, marginTop: 8,
            }}>
              + Add Folder
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
