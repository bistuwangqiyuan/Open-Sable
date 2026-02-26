import { useState, useEffect, useCallback } from 'react';
import { QRCodeSVG } from 'qrcode.react';
import { RefreshCw, Smartphone, Clock, Shield } from 'lucide-react';

const s = {
  panel: { display: 'flex', flexDirection: 'column', flex: 1, overflow: 'hidden' },
  header: {
    display: 'flex', alignItems: 'center', gap: 8, padding: '12px 16px',
    borderBottom: '1px solid var(--border)', minHeight: 44, flexShrink: 0,
  },
  title: { fontSize: 13, fontWeight: 600 },
  body: { flex: 1, overflowY: 'auto', padding: 24, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 24 },
  qrBox: {
    background: '#fff', borderRadius: 16, padding: 20,
    boxShadow: '0 8px 32px rgba(0,0,0,.4)',
  },
  info: {
    textAlign: 'center', maxWidth: 400,
  },
  step: {
    display: 'flex', alignItems: 'center', gap: 12, padding: '10px 16px',
    background: 'var(--bg-tertiary)', border: '1px solid var(--border)',
    borderRadius: 'var(--radius)', marginBottom: 8, fontSize: 13,
  },
  stepNum: {
    width: 28, height: 28, borderRadius: '50%', background: 'var(--accent-dim)',
    color: 'var(--accent-light)', display: 'flex', alignItems: 'center',
    justifyContent: 'center', fontSize: 12, fontWeight: 700, flexShrink: 0,
  },
  refreshBtn: {
    display: 'flex', alignItems: 'center', gap: 6, padding: '8px 16px',
    borderRadius: 'var(--radius)', border: '1px solid var(--border)',
    background: 'var(--bg-tertiary)', color: 'var(--text)', cursor: 'pointer',
    fontSize: 12, fontWeight: 600, transition: 'all .15s',
  },
  timer: {
    display: 'flex', alignItems: 'center', gap: 6, fontSize: 12,
    color: 'var(--text-muted)',
  },
  devices: {
    width: '100%', maxWidth: 400, borderTop: '1px solid var(--border)',
    paddingTop: 16,
  },
  device: {
    display: 'flex', alignItems: 'center', gap: 10, padding: '10px 12px',
    background: 'var(--bg-tertiary)', border: '1px solid var(--border)',
    borderRadius: 'var(--radius-sm)', marginBottom: 8,
  },
};

export default function QRPanel() {
  const [qrData, setQrData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [devices, setDevices] = useState([]);
  const [timeLeft, setTimeLeft] = useState(0);

  const fetchQR = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      // Try mobile relay endpoint
      const base = location.origin.replace(/:\d+$/, ':8081');
      const res = await fetch(`${base}/mobile/qr`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setQrData(data);
      setTimeLeft(Math.floor((data.expires_at - Date.now() / 1000)));
    } catch (e) {
      // Fallback: generate a local QR string
      const token = crypto.randomUUID();
      const wsProto = location.protocol === 'https:' ? 'wss' : 'ws';
      const fallback = `sablecore://pair?url=${wsProto}://${location.host}/&token=${token}&ts=${Math.floor(Date.now()/1000)}`;
      setQrData({ qr_string: fallback, token, expires_at: Date.now()/1000 + 300 });
      setTimeLeft(300);
      setError(null); // Don't show error if fallback works
    }
    setLoading(false);
  }, []);

  const fetchDevices = useCallback(async () => {
    try {
      const base = location.origin.replace(/:\d+$/, ':8081');
      const res = await fetch(`${base}/mobile/devices`);
      if (res.ok) setDevices(await res.json());
    } catch {}
  }, []);

  useEffect(() => {
    fetchQR();
    fetchDevices();
    const iv = setInterval(fetchDevices, 10000);
    return () => clearInterval(iv);
  }, [fetchQR, fetchDevices]);

  useEffect(() => {
    if (timeLeft <= 0) return;
    const iv = setInterval(() => {
      setTimeLeft(t => {
        if (t <= 1) { fetchQR(); return 0; }
        return t - 1;
      });
    }, 1000);
    return () => clearInterval(iv);
  }, [timeLeft, fetchQR]);

  const fmtTimer = (sec) => {
    const m = Math.floor(sec / 60);
    const s = sec % 60;
    return `${m}:${String(s).padStart(2, '0')}`;
  };

  return (
    <div style={s.panel}>
      <div style={s.header}>
        <span style={{ fontSize: 16 }}>📱</span>
        <span style={s.title}>Mobile Pairing</span>
      </div>
      <div style={s.body}>
        <div style={s.info}>
          <h2 style={{ fontSize: 20, fontWeight: 700, marginBottom: 8 }}>
            Pair Your Phone
          </h2>
          <p style={{ color: 'var(--text-secondary)', fontSize: 13, marginBottom: 16 }}>
            Scan this QR code with the OpenSable mobile app to connect your device securely.
          </p>
        </div>

        {qrData ? (
          <div style={s.qrBox}>
            <QRCodeSVG
              value={qrData.qr_string}
              size={220}
              level="M"
              bgColor="#ffffff"
              fgColor="#0a0b0f"
              imageSettings={{
                src: 'data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><text y="18" font-size="18">🤖</text></svg>',
                height: 32, width: 32, excavate: true,
              }}
            />
          </div>
        ) : loading ? (
          <div style={{ ...s.qrBox, width: 260, height: 260, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <RefreshCw size={24} style={{ animation: 'spin 1s linear infinite', color: '#666' }} />
          </div>
        ) : null}

        <div style={{ display: 'flex', gap: 16, alignItems: 'center' }}>
          <div style={s.timer}>
            <Clock size={14} />
            Expires in {fmtTimer(Math.max(0, timeLeft))}
          </div>
          <button style={s.refreshBtn} onClick={fetchQR} disabled={loading}>
            <RefreshCw size={14} />
            Refresh
          </button>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 11, color: 'var(--text-muted)' }}>
          <Shield size={12} />
          X25519 ECDH key exchange · End-to-end encrypted
        </div>

        <div style={{ width: '100%', maxWidth: 360 }}>
          <div style={s.step}>
            <div style={s.stepNum}>1</div>
            <span>Open OpenSable app on your phone</span>
          </div>
          <div style={s.step}>
            <div style={s.stepNum}>2</div>
            <span>Tap "Scan QR Code" on the home screen</span>
          </div>
          <div style={s.step}>
            <div style={s.stepNum}>3</div>
            <span>Point camera at this QR code</span>
          </div>
          <div style={s.step}>
            <div style={s.stepNum}>4</div>
            <span>Confirm pairing on both devices</span>
          </div>
        </div>

        {devices.length > 0 && (
          <div style={s.devices}>
            <h3 style={{ fontSize: 14, fontWeight: 600, marginBottom: 12 }}>
              Paired Devices ({devices.length})
            </h3>
            {devices.map((d, i) => (
              <div key={i} style={s.device}>
                <Smartphone size={18} style={{ color: d.connected ? 'var(--green)' : 'var(--text-muted)', flexShrink: 0 }} />
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text)' }}>
                    {d.device_name || 'Unknown Device'}
                  </div>
                  <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>
                    {d.device_os} · {d.msg_count} messages
                  </div>
                </div>
                <div style={{
                  width: 8, height: 8, borderRadius: '50%',
                  background: d.connected ? 'var(--green)' : 'var(--text-muted)',
                  boxShadow: d.connected ? '0 0 6px rgba(34,197,94,.5)' : 'none',
                }} />
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
