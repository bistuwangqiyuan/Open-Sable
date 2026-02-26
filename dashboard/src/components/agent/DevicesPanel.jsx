import { useState, useEffect, useCallback } from 'react';
import { Smartphone, Trash2, RefreshCw, Monitor, Wifi, WifiOff } from 'lucide-react';

const s = {
  panel: { display: 'flex', flexDirection: 'column', flex: 1, overflow: 'hidden' },
  header: {
    display: 'flex', alignItems: 'center', gap: 8, padding: '12px 16px',
    borderBottom: '1px solid var(--border)', minHeight: 44, flexShrink: 0,
  },
  title: { fontSize: 13, fontWeight: 600 },
  body: { flex: 1, overflowY: 'auto', padding: 16 },
  device: {
    padding: 16, borderRadius: 'var(--radius)', marginBottom: 10,
    border: '1px solid var(--border)', background: 'var(--bg-tertiary)',
    display: 'flex', gap: 14, alignItems: 'flex-start',
  },
  deviceIcon: {
    width: 44, height: 44, borderRadius: 'var(--radius-sm)',
    display: 'flex', alignItems: 'center', justifyContent: 'center',
    flexShrink: 0,
  },
  name: { fontSize: 15, fontWeight: 700 },
  meta: { fontSize: 11, color: 'var(--text-muted)', marginTop: 2 },
  dot: (on) => ({
    width: 8, height: 8, borderRadius: '50%',
    background: on ? 'var(--green)' : 'var(--text-muted)',
    boxShadow: on ? '0 0 6px rgba(34,197,94,.5)' : 'none',
    flexShrink: 0,
  }),
  badge: (color) => ({
    padding: '2px 8px', borderRadius: 99, fontSize: 10, fontWeight: 600,
    background: `var(--${color}-dim)`, color: `var(--${color})`,
    display: 'inline-flex', alignItems: 'center', gap: 4,
  }),
  btn: {
    padding: '6px 12px', borderRadius: 'var(--radius-sm)',
    border: '1px solid var(--border)', background: 'transparent',
    color: 'var(--text-muted)', cursor: 'pointer', fontSize: 11,
    display: 'flex', alignItems: 'center', gap: 4,
  },
  empty: {
    padding: 48, textAlign: 'center', color: 'var(--text-muted)',
  },
  stats: {
    display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 8, marginBottom: 20,
  },
  stat: {
    background: 'var(--bg-tertiary)', border: '1px solid var(--border)',
    borderRadius: 'var(--radius-sm)', padding: '12px', textAlign: 'center',
  },
  statVal: { fontSize: 22, fontWeight: 700 },
  statLabel: { fontSize: 10, color: 'var(--text-muted)', textTransform: 'uppercase', marginTop: 2 },
};

export default function DevicesPanel() {
  const [devices, setDevices] = useState([]);
  const [loading, setLoading] = useState(true);
  const [status, setStatus] = useState(null);

  const fetchDevices = useCallback(async () => {
    try {
      const base = location.origin.replace(/:\d+$/, ':8081');
      const [devRes, statusRes] = await Promise.all([
        fetch(`${base}/mobile/devices`).catch(() => null),
        fetch(`${base}/mobile/status`).catch(() => null),
      ]);
      if (devRes?.ok) setDevices(await devRes.json());
      if (statusRes?.ok) setStatus(await statusRes.json());
    } catch {}
    setLoading(false);
  }, []);

  useEffect(() => {
    fetchDevices();
    const iv = setInterval(fetchDevices, 10000);
    return () => clearInterval(iv);
  }, [fetchDevices]);

  const unpair = async (deviceId) => {
    if (!confirm('Unpair this device?')) return;
    try {
      const base = location.origin.replace(/:\d+$/, ':8081');
      await fetch(`${base}/mobile/devices/${deviceId}`, { method: 'DELETE' });
      fetchDevices();
    } catch {}
  };

  const connectedCount = devices.filter(d => d.connected).length;

  return (
    <div style={s.panel}>
      <div style={s.header}>
        <span style={{ fontSize: 16 }}>📱</span>
        <span style={s.title}>Connected Devices</span>
        <span style={{ marginLeft: 'auto', fontSize: 11, color: 'var(--text-muted)' }}>
          {devices.length} paired
        </span>
        <button
          style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', padding: 4 }}
          onClick={fetchDevices}
          title="Refresh"
        >
          <RefreshCw size={14} />
        </button>
      </div>
      <div style={s.body}>
        {/* Stats */}
        <div style={s.stats}>
          <div style={s.stat}>
            <div style={{ ...s.statVal, color: 'var(--accent-light)' }}>{devices.length}</div>
            <div style={s.statLabel}>Paired</div>
          </div>
          <div style={s.stat}>
            <div style={{ ...s.statVal, color: 'var(--green)' }}>{connectedCount}</div>
            <div style={s.statLabel}>Online</div>
          </div>
          <div style={s.stat}>
            <div style={{ ...s.statVal, color: 'var(--teal)' }}>
              {status?.protocol || 'SETP/1.0'}
            </div>
            <div style={s.statLabel}>Protocol</div>
          </div>
        </div>

        {loading ? (
          <div style={s.empty}>
            <RefreshCw size={24} style={{ animation: 'spin 1s linear infinite', marginBottom: 8 }} />
            <div>Loading devices…</div>
          </div>
        ) : devices.length === 0 ? (
          <div style={s.empty}>
            <Smartphone size={40} style={{ opacity: .2, marginBottom: 12 }} />
            <div style={{ fontSize: 15, fontWeight: 600, marginBottom: 4 }}>No Devices Paired</div>
            <div style={{ fontSize: 12 }}>
              Go to QR Pair to connect your phone
            </div>
          </div>
        ) : (
          devices.map((d) => (
            <div key={d.device_id} style={s.device}>
              <div style={{
                ...s.deviceIcon,
                background: d.connected ? 'var(--green-dim)' : 'var(--bg-hover)',
                color: d.connected ? 'var(--green)' : 'var(--text-muted)',
              }}>
                <Smartphone size={22} />
              </div>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <span style={s.name}>{d.device_name || 'Unknown Device'}</span>
                  <span style={s.dot(d.connected)} />
                </div>
                <div style={s.meta}>
                  {d.device_os} · {d.msg_count} messages · ID: {d.device_id.slice(0, 8)}…
                </div>
                <div style={{ display: 'flex', gap: 6, marginTop: 6 }}>
                  <span style={s.badge(d.connected ? 'green' : 'yellow')}>
                    {d.connected ? <><Wifi size={10} /> Online</> : <><WifiOff size={10} /> Offline</>}
                  </span>
                </div>
                {d.last_seen && (
                  <div style={{ fontSize: 10, color: 'var(--text-muted)', marginTop: 4, fontFamily: 'var(--mono)' }}>
                    Last seen: {new Date(d.last_seen * 1000).toLocaleString()}
                  </div>
                )}
              </div>
              <button style={s.btn} onClick={() => unpair(d.device_id)}>
                <Trash2 size={12} /> Unpair
              </button>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
