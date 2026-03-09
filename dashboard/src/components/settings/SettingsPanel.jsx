import { useState, useEffect } from 'react';
import { Eye, EyeOff, Check, X, ChevronDown, ChevronUp, RefreshCw } from 'lucide-react';
import { PROVIDERS, PROVIDER_LOGOS } from '../../lib/utils';

const s = {
  panel: { display: 'flex', flexDirection: 'column', flex: 1, overflow: 'hidden' },
  header: {
    display: 'flex', alignItems: 'center', gap: 8, padding: '12px 16px',
    borderBottom: '1px solid var(--border)', minHeight: 44, flexShrink: 0,
  },
  title: { fontSize: 13, fontWeight: 600 },
  body: { flex: 1, overflowY: 'auto', padding: 16 },
  section: { marginBottom: 24 },
  sectionTitle: { fontSize: 14, fontWeight: 700, marginBottom: 12, color: 'var(--text)' },
  grid: { display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(160px, 1fr))', gap: 8 },
  provCard: (active) => ({
    padding: '12px', borderRadius: 'var(--radius)', cursor: 'pointer',
    border: `1px solid ${active ? 'var(--accent)' : 'var(--border)'}`,
    background: active ? 'var(--accent-dim)' : 'var(--bg-tertiary)',
    transition: 'all .15s', display: 'flex', flexDirection: 'column', gap: 6,
  }),
  provName: { fontSize: 13, fontWeight: 600 },
  provStatus: (connected) => ({
    fontSize: 10, fontWeight: 600, padding: '2px 6px', borderRadius: 99,
    display: 'inline-flex', alignItems: 'center', gap: 4, width: 'fit-content',
    background: connected ? 'var(--green-dim)' : 'var(--bg-hover)',
    color: connected ? 'var(--green)' : 'var(--text-muted)',
  }),
  formGroup: { marginBottom: 12 },
  label: {
    fontSize: 11, fontWeight: 600, color: 'var(--text-secondary)', display: 'block',
    marginBottom: 4, textTransform: 'uppercase', letterSpacing: '.05em',
  },
  inputRow: { display: 'flex', gap: 6 },
  input: {
    flex: 1, padding: '8px 12px', borderRadius: 'var(--radius-sm)',
    border: '1px solid var(--border)', background: 'var(--bg-primary)',
    color: 'var(--text)', fontFamily: 'var(--mono)', fontSize: 12,
    outline: 'none',
  },
  iconBtn: {
    width: 36, height: 36, borderRadius: 'var(--radius-sm)', border: '1px solid var(--border)',
    background: 'var(--bg-tertiary)', color: 'var(--text-muted)', cursor: 'pointer',
    display: 'flex', alignItems: 'center', justifyContent: 'center',
  },
  btn: (variant) => ({
    padding: '8px 16px', borderRadius: 'var(--radius-sm)',
    border: variant === 'ghost' ? '1px solid var(--border)' : 'none',
    cursor: 'pointer', fontSize: 12, fontWeight: 600,
    display: 'flex', alignItems: 'center', gap: 6,
    background: variant === 'primary' ? 'var(--accent)' : variant === 'danger' ? 'var(--red)' : 'var(--bg-tertiary)',
    color: variant === 'primary' || variant === 'danger' ? '#fff' : 'var(--text)',
  }),
  select: {
    flex: 1, padding: '8px 12px', borderRadius: 'var(--radius-sm)',
    border: '1px solid var(--border)', background: 'var(--bg-primary)',
    color: 'var(--text)', fontSize: 12, outline: 'none',
    appearance: 'none', cursor: 'pointer',
  },
  envRow: {
    display: 'flex', alignItems: 'center', gap: 8, padding: '8px 12px',
    background: 'var(--bg-tertiary)', borderRadius: 'var(--radius-sm)',
    marginBottom: 6, fontFamily: 'var(--mono)', fontSize: 11,
  },
  envKey: { color: 'var(--teal)', fontWeight: 600 },
  envVal: { color: 'var(--text-muted)', flex: 1, overflow: 'hidden', textOverflow: 'ellipsis' },
};

// Load saved config from localStorage
function loadConfig() {
  try {
    return JSON.parse(localStorage.getItem('opensable_agent_config') || '{}');
  } catch { return {}; }
}
function saveConfig(cfg) {
  localStorage.setItem('opensable_agent_config', JSON.stringify(cfg));
}

export default function SettingsPanel({ modelGroups = [], requestModels, switchModel, importGGUF }) {
  const [config, setConfig] = useState(loadConfig);
  const [selectedProvider, setSelectedProvider] = useState(null);
  const [showKey, setShowKey] = useState(false);
  const [saved, setSaved] = useState(false);
  const [expandedSection, setExpandedSection] = useState('providers');
  const [ggufPath, setGgufPath] = useState('');
  const [ggufName, setGgufName] = useState('');

  // Refresh local models when settings panel opens or Ollama is selected
  useEffect(() => {
    if (requestModels) requestModels();
  }, [selectedProvider]);

  const activeProvider = config.activeProvider || '';
  const providerConfigs = config.providers || {};

  const updateProviderConfig = (id, key, value) => {
    const next = {
      ...config,
      providers: {
        ...providerConfigs,
        [id]: { ...providerConfigs[id], [key]: value },
      },
    };
    setConfig(next);
    saveConfig(next);
  };

  const setActiveProvider = (id) => {
    const next = { ...config, activeProvider: id };
    setConfig(next);
    saveConfig(next);
  };

  const handleSave = () => {
    saveConfig(config);
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  };

  const sel = PROVIDERS.find(p => p.id === selectedProvider);

  return (
    <div style={s.panel}>
      <div style={s.header}>
        <span style={{ fontSize: 16 }}>⚙️</span>
        <span style={s.title}>Agent Configuration</span>
      </div>
      <div style={s.body}>
        {/* AI Providers */}
        <div style={s.section}>
          <div
            style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer', marginBottom: 12 }}
            onClick={() => setExpandedSection(expandedSection === 'providers' ? '' : 'providers')}
          >
            <span style={s.sectionTitle}>🔑 AI Providers</span>
            {expandedSection === 'providers' ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
          </div>

          {expandedSection === 'providers' && (
            <>
              <div style={s.grid}>
                {PROVIDERS.map(p => {
                  const cfg = providerConfigs[p.id] || {};
                  const isActive = activeProvider === p.id;
                  const hasKey = !!cfg.apiKey;
                  return (
                    <div
                      key={p.id}
                      style={s.provCard(selectedProvider === p.id)}
                      onClick={() => setSelectedProvider(p.id)}
                    >
                      <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                        <span style={{ fontSize: 18 }}>{PROVIDER_LOGOS[p.id]}</span>
                        <span style={s.provName}>{p.name}</span>
                      </div>
                      <div style={{ display: 'flex', gap: 4 }}>
                        <span style={s.provStatus(hasKey)}>
                          {hasKey ? <><Check size={10} /> Ready</> : 'Not configured'}
                        </span>
                        {isActive && (
                          <span style={{ ...s.provStatus(true), background: 'var(--accent-dim)', color: 'var(--accent-light)' }}>
                            Active
                          </span>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>

              {/* Provider detail form */}
              {sel && (
                <div style={{
                  marginTop: 16, padding: 16, background: 'var(--bg-tertiary)',
                  border: '1px solid var(--border)', borderRadius: 'var(--radius)',
                }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 16 }}>
                    <span style={{ fontSize: 22 }}>{PROVIDER_LOGOS[sel.id]}</span>
                    <span style={{ fontSize: 16, fontWeight: 700 }}>{sel.name}</span>
                    <button
                      style={{ marginLeft: 'auto', ...s.iconBtn }}
                      onClick={() => setSelectedProvider(null)}
                    >
                      <X size={14} />
                    </button>
                  </div>

                  {!sel.local && (
                    <div style={s.formGroup}>
                      <label style={s.label}>API Key</label>
                      <div style={s.inputRow}>
                        <input
                          style={s.input}
                          type={showKey ? 'text' : 'password'}
                          value={providerConfigs[sel.id]?.apiKey || ''}
                          onChange={(e) => updateProviderConfig(sel.id, 'apiKey', e.target.value)}
                          placeholder={`Enter ${sel.name} API key…`}
                        />
                        <button style={s.iconBtn} onClick={() => setShowKey(v => !v)}>
                          {showKey ? <EyeOff size={14} /> : <Eye size={14} />}
                        </button>
                      </div>
                    </div>
                  )}

                  {sel.local && (
                    <div style={s.formGroup}>
                      <label style={s.label}>Base URL</label>
                      <input
                        style={s.input}
                        value={providerConfigs[sel.id]?.baseUrl || (sel.id === 'ollama' ? 'http://localhost:11434' : 'http://localhost:1234')}
                        onChange={(e) => updateProviderConfig(sel.id, 'baseUrl', e.target.value)}
                        placeholder="http://localhost:11434"
                      />
                    </div>
                  )}

                  <div style={s.formGroup}>
                    <label style={s.label}>
                      Model
                      {sel.local && (() => {
                        const grp = modelGroups.find(g => g.provider === sel.id || (sel.id === 'ollama' && g.provider === 'ollama'));
                        const count = grp?.models?.length || 0;
                        return count > 0 ? (
                          <span style={{ fontWeight: 400, textTransform: 'none', letterSpacing: 0, marginLeft: 6, color: 'var(--green)' }}>
                            ({count} installed)
                          </span>
                        ) : null;
                      })()}
                      {sel.local && requestModels && (
                        <button
                          onClick={(e) => { e.preventDefault(); requestModels(); }}
                          style={{
                            background: 'none', border: 'none', cursor: 'pointer',
                            color: 'var(--text-muted)', marginLeft: 6, padding: 0, verticalAlign: 'middle',
                          }}
                          title="Refresh local models"
                        >
                          <RefreshCw size={11} />
                        </button>
                      )}
                    </label>
                    <div style={{ position: 'relative' }}>
                      {(() => {
                        // For local providers (Ollama/LM Studio), prefer dynamically fetched models from gateway groups
                        let dynamicNames = [];
                        if (sel.local) {
                          const grp = modelGroups.find(g => g.provider === sel.id || (sel.id === 'ollama' && g.provider === 'ollama'));
                          if (grp && grp.models) dynamicNames = grp.models.map(m => m.name || m);
                        }
                        const modelList = dynamicNames.length > 0 ? dynamicNames : sel.models;
                        const currentVal = providerConfigs[sel.id]?.model || modelList[0];
                        return (
                          <select
                            style={s.select}
                            value={currentVal}
                            onChange={(e) => updateProviderConfig(sel.id, 'model', e.target.value)}
                          >
                            {modelList.map(m => <option key={m} value={m}>{m}</option>)}
                            <option value="custom">Custom…</option>
                          </select>
                        );
                      })()}
                    </div>
                  </div>

                  {providerConfigs[sel.id]?.model === 'custom' && (
                    <div style={s.formGroup}>
                      <label style={s.label}>Custom Model Name</label>
                      <input
                        style={s.input}
                        value={providerConfigs[sel.id]?.customModel || ''}
                        onChange={(e) => updateProviderConfig(sel.id, 'customModel', e.target.value)}
                        placeholder="e.g. my-finetuned-model"
                      />
                    </div>
                  )}

                  <div style={{ display: 'flex', gap: 8, marginTop: 16 }}>
                    <button style={s.btn('primary')} onClick={() => { setActiveProvider(sel.id); handleSave(); }}>
                      <Check size={14} /> Set as Active
                    </button>
                    <button style={s.btn('ghost')} onClick={handleSave}>
                      {saved ? '✓ Saved' : 'Save'}
                    </button>
                  </div>
                </div>
              )}
            </>
          )}
        </div>

        {/* Environment Variables */}
        <div style={s.section}>
          <div
            style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer', marginBottom: 12 }}
            onClick={() => setExpandedSection(expandedSection === 'env' ? '' : 'env')}
          >
            <span style={s.sectionTitle}>🔐 Environment Variables</span>
            {expandedSection === 'env' ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
          </div>

          {expandedSection === 'env' && (
            <div>
              <p style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 12 }}>
                These environment variables are read from .env at startup. Edit .env file to change.
              </p>
              {[
                ['OPENAI_API_KEY', 'OpenAI API key'],
                ['ANTHROPIC_API_KEY', 'Anthropic API key'],
                ['GOOGLE_AI_API_KEY', 'Google AI API key'],
                ['XAI_API_KEY', 'xAI API key'],
                ['DEEPSEEK_API_KEY', 'DeepSeek API key'],
                ['SABLE_STORE_API_KEY', 'Skills Marketplace key'],
                ['SABLE_GATEWAY_URL', 'SAGP Gateway URL'],
                ['LLM_MODEL', 'Active LLM model'],
                ['LLM_PROVIDER', 'Active LLM provider'],
              ].map(([k, desc]) => (
                <div key={k} style={s.envRow}>
                  <span style={s.envKey}>{k}</span>
                  <span style={s.envVal}>{desc}</span>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Import GGUF Model */}
        <div style={s.section}>
          <div
            style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer', marginBottom: 12 }}
            onClick={() => setExpandedSection(expandedSection === 'gguf' ? '' : 'gguf')}
          >
            <span style={s.sectionTitle}>📥 Import Local Model (GGUF)</span>
            {expandedSection === 'gguf' ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
          </div>

          {expandedSection === 'gguf' && (
            <div>
              <p style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 12 }}>
                Import a .gguf model file (from HuggingFace, TheBloke, etc.) into Ollama.
                The file stays on disk — Ollama creates a reference to it.
              </p>
              <div style={s.formGroup}>
                <label style={s.label}>GGUF File Path</label>
                <input
                  style={s.input}
                  value={ggufPath}
                  onChange={(e) => setGgufPath(e.target.value)}
                  placeholder="/path/to/model.gguf  (e.g. ~/Downloads/Qwen3.5-9B-Q4_K_M.gguf)"
                />
              </div>
              <div style={s.formGroup}>
                <label style={s.label}>Model Name (optional)</label>
                <div style={s.inputRow}>
                  <input
                    style={s.input}
                    value={ggufName}
                    onChange={(e) => setGgufName(e.target.value)}
                    placeholder="Auto-derived from filename if empty"
                  />
                  <button
                    style={s.btn(ggufPath.trim() ? 'primary' : 'ghost')}
                    disabled={!ggufPath.trim()}
                    onClick={() => {
                      if (importGGUF && ggufPath.trim()) {
                        importGGUF(ggufPath.trim(), ggufName.trim());
                        setGgufPath('');
                        setGgufName('');
                      }
                    }}
                  >
                    📥 Import
                  </button>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Agent Behavior */}
        <div style={s.section}>
          <div
            style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer', marginBottom: 12 }}
            onClick={() => setExpandedSection(expandedSection === 'behavior' ? '' : 'behavior')}
          >
            <span style={s.sectionTitle}>🧠 Agent Behavior</span>
            {expandedSection === 'behavior' ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
          </div>

          {expandedSection === 'behavior' && (
            <div>
              {[
                { key: 'maxRounds', label: 'Max Think Rounds', type: 'number', default: 25, hint: 'Maximum reasoning rounds per query' },
                { key: 'temperature', label: 'Temperature', type: 'number', default: 0.7, step: 0.1, hint: 'Creativity (0=deterministic, 1=creative)' },
                { key: 'maxTokens', label: 'Max Tokens', type: 'number', default: 8192, hint: 'Maximum response length' },
                { key: 'systemPrompt', label: 'System Prompt Override', type: 'textarea', default: '', hint: 'Custom system prompt (leave empty for default)' },
              ].map(field => (
                <div key={field.key} style={s.formGroup}>
                  <label style={s.label}>{field.label}</label>
                  {field.type === 'textarea' ? (
                    <textarea
                      style={{ ...s.input, minHeight: 80, resize: 'vertical', fontFamily: 'var(--sans)' }}
                      value={config[field.key] ?? field.default}
                      onChange={(e) => {
                        const next = { ...config, [field.key]: e.target.value };
                        setConfig(next);
                        saveConfig(next);
                      }}
                      placeholder={field.hint}
                    />
                  ) : (
                    <input
                      style={s.input}
                      type={field.type}
                      step={field.step}
                      value={config[field.key] ?? field.default}
                      onChange={(e) => {
                        const next = { ...config, [field.key]: field.type === 'number' ? Number(e.target.value) : e.target.value };
                        setConfig(next);
                        saveConfig(next);
                      }}
                      placeholder={field.hint}
                    />
                  )}
                  <div style={{ fontSize: 10, color: 'var(--text-muted)', marginTop: 2 }}>{field.hint}</div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Permissions / Allowed Folders */}
        <div style={s.section}>
          <div
            style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer', marginBottom: 12 }}
            onClick={() => setExpandedSection(expandedSection === 'permissions' ? '' : 'permissions')}
          >
            <span style={s.sectionTitle}>🛡️ Permissions</span>
            {expandedSection === 'permissions' ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
          </div>

          {expandedSection === 'permissions' && (
            <div>
              <p style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 12 }}>
                Control which capabilities the agent can use. Changes require restart.
              </p>
              {[
                { key: 'fileAccess', label: 'File System Access', desc: 'Read/write files on disk' },
                { key: 'codeExecution', label: 'Code Execution', desc: 'Run Python/shell commands' },
                { key: 'webAccess', label: 'Web Access', desc: 'Browse and scrape websites' },
                { key: 'trading', label: 'Trading', desc: 'Execute trades (requires exchange keys)' },
                { key: 'selfModify', label: 'Self Modification', desc: 'Modify own code and behavior' },
              ].map(perm => (
                <div key={perm.key} style={{
                  display: 'flex', alignItems: 'center', gap: 12, padding: '10px 12px',
                  background: 'var(--bg-tertiary)', borderRadius: 'var(--radius-sm)',
                  marginBottom: 6, border: '1px solid var(--border)',
                }}>
                  <label style={{
                    position: 'relative', width: 40, height: 22, flexShrink: 0, cursor: 'pointer',
                  }}>
                    <input
                      type="checkbox"
                      checked={config.permissions?.[perm.key] !== false}
                      onChange={(e) => {
                        const next = {
                          ...config,
                          permissions: { ...config.permissions, [perm.key]: e.target.checked },
                        };
                        setConfig(next);
                        saveConfig(next);
                      }}
                      style={{ display: 'none' }}
                    />
                    <span style={{
                      display: 'block', width: 40, height: 22, borderRadius: 11,
                      background: config.permissions?.[perm.key] !== false ? 'var(--accent)' : 'var(--border)',
                      transition: 'background .2s', position: 'relative',
                    }}>
                      <span style={{
                        position: 'absolute', top: 2, left: config.permissions?.[perm.key] !== false ? 20 : 2,
                        width: 18, height: 18, borderRadius: '50%', background: '#fff',
                        transition: 'left .2s',
                      }} />
                    </span>
                  </label>
                  <div>
                    <div style={{ fontSize: 13, fontWeight: 600 }}>{perm.label}</div>
                    <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>{perm.desc}</div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
