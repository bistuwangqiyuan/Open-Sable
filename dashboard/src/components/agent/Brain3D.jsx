/**
 * Brain3D — Interactive 3D neural connectome visualisation
 *
 * Renders the Drosophila-derived neural colony as a rotating 3D brain
 * with glowing nodes, animated synaptic connections, and live activation.
 *
 * Uses React Three Fiber + Drei for WebGL rendering.
 */
import { useRef, useState, useMemo, useEffect } from 'react';
import { Canvas, useFrame } from '@react-three/fiber';
import { OrbitControls, Text, Billboard, Line } from '@react-three/drei';
import * as THREE from 'three';

// ── 3D positions for each brain region (mapped to approx brain anatomy) ──
const NODE_3D = {
  AL:  { x: -1.8, y:  1.4, z:  0.6 },   // Antennal Lobe — front-left
  OL:  { x:  1.8, y:  1.4, z:  0.6 },   // Optic Lobe — front-right
  MB:  { x: -0.8, y:  0.6, z: -0.2 },   // Mushroom Body — inner-left
  LH:  { x:  0.8, y:  0.6, z: -0.2 },   // Lateral Horn — inner-right
  CX:  { x:  0.0, y:  0.0, z:  0.0 },   // Central Complex — center
  PI:  { x: -1.2, y: -1.0, z:  0.3 },   // Pars Intercerebralis — lower-left
  LPC: { x:  1.2, y: -1.0, z:  0.3 },   // Lateral Protocerebrum — lower-right
  SEZ: { x:  0.0, y: -1.6, z:  0.8 },   // Subesophageal Zone — bottom-center
};

const REGION_LABELS = {
  AL: 'Antennal Lobe',      OL: 'Optic Lobe',
  MB: 'Mushroom Body',      LH: 'Lateral Horn',
  CX: 'Central Complex',    PI: 'Pars Intercerebralis',
  LPC: 'Lateral Proto.',    SEZ: 'Subesophageal',
};

const MODULE_LABELS = {
  AL: 'Sensory Input',      OL: 'Context/Vision',
  MB: 'Memory/Learning',    LH: 'Reflex/Instinct',
  CX: 'Decision Engine',    PI: 'Motivation/Drive',
  LPC: 'Emotion',           SEZ: 'Action/Output',
};

// Color palette for regions
const REGION_COLORS = {
  AL:  '#00cec9',  OL:  '#6c5ce7',
  MB:  '#fdcb6e',  LH:  '#e17055',
  CX:  '#7c3aed',  PI:  '#00b894',
  LPC: '#e84393',  SEZ: '#0984e3',
};


// ── Animated Brain Node ───────────────────────────────────────────────
function BrainNode({ id, position, activation, threshold, fireCount, module, isHovered, onHover }) {
  const meshRef = useRef();
  const glowRef = useRef();
  const baseColor = REGION_COLORS[id] || '#7c3aed';
  const color = new THREE.Color(baseColor);
  const baseRadius = 0.18;
  const radius = baseRadius + activation * 0.12;

  useFrame((state) => {
    if (meshRef.current) {
      // Gentle pulse based on activation
      const pulse = 1 + Math.sin(state.clock.elapsedTime * 2 + position[0] * 3) * 0.03 * (1 + activation * 2);
      meshRef.current.scale.setScalar(pulse);
    }
    if (glowRef.current) {
      const glowPulse = 0.3 + activation * 0.7 + Math.sin(state.clock.elapsedTime * 3) * 0.1 * activation;
      glowRef.current.material.opacity = Math.max(0, Math.min(1, glowPulse * 0.35));
      glowRef.current.scale.setScalar(1 + activation * 0.6 + Math.sin(state.clock.elapsedTime * 1.5) * 0.1);
    }
  });

  return (
    <group position={position}>
      {/* Outer glow */}
      <mesh ref={glowRef}>
        <sphereGeometry args={[radius * 2.5, 16, 16]} />
        <meshBasicMaterial color={color} transparent opacity={0.1} depthWrite={false} />
      </mesh>

      {/* Core sphere */}
      <mesh
        ref={meshRef}
        onPointerEnter={(e) => { e.stopPropagation(); onHover(id); }}
        onPointerLeave={(e) => { e.stopPropagation(); onHover(null); }}
      >
        <sphereGeometry args={[radius, 32, 32]} />
        <meshStandardMaterial
          color={color}
          emissive={color}
          emissiveIntensity={0.3 + activation * 1.5}
          roughness={0.3}
          metalness={0.2}
          transparent
          opacity={0.7 + activation * 0.3}
        />
      </mesh>

      {/* Region code label */}
      <Billboard follow lockX={false} lockY={false} lockZ={false}>
        <Text
          position={[0, radius + 0.12, 0]}
          fontSize={0.12}
          color={baseColor}
          fontWeight={700}
          anchorX="center"
          anchorY="bottom"
          outlineWidth={0.008}
          outlineColor="#000000"
        >
          {id}
        </Text>
        <Text
          position={[0, radius + 0.01, 0]}
          fontSize={0.065}
          color="#8e99a4"
          anchorX="center"
          anchorY="bottom"
        >
          {MODULE_LABELS[id] || module}
        </Text>
      </Billboard>

      {/* Activation ring (visible when > threshold) */}
      {activation > threshold && (
        <mesh rotation={[Math.PI / 2, 0, 0]}>
          <ringGeometry args={[radius + 0.05, radius + 0.09, 32]} />
          <meshBasicMaterial color={color} transparent opacity={0.6} side={THREE.DoubleSide} />
        </mesh>
      )}
    </group>
  );
}


// ── Synaptic Connection (animated line with particles) ───────────────
function SynapticEdge({ from, to, weight, drift, mutations, isHighlighted }) {
  const lineRef = useRef();
  const particleRef = useRef();

  const points = useMemo(() => {
    const start = new THREE.Vector3(...from);
    const end = new THREE.Vector3(...to);
    // Create a slight curve via midpoint offset
    const mid = start.clone().lerp(end, 0.5);
    const normal = new THREE.Vector3()
      .subVectors(end, start)
      .cross(new THREE.Vector3(0, 1, 0))
      .normalize()
      .multiplyScalar(0.15);
    mid.add(normal);

    const curve = new THREE.QuadraticBezierCurve3(start, mid, end);
    return curve.getPoints(20);
  }, [from, to]);

  const driftAbs = Math.abs(drift || 0);
  const baseColor = driftAbs > 0.2 ? '#e17055' : driftAbs > 0.05 ? '#f39c12' : '#4a5568';
  const opacity = isHighlighted ? 0.8 : 0.15 + weight * 0.3;
  const lineWidth = isHighlighted ? 1.5 + weight * 2 : 0.5 + weight * 1.5;

  // Animated particle along the edge
  useFrame((state) => {
    if (particleRef.current && weight > 0.3) {
      const t = (state.clock.elapsedTime * 0.3 * weight) % 1;
      const idx = Math.floor(t * (points.length - 1));
      const pt = points[Math.min(idx, points.length - 1)];
      particleRef.current.position.copy(pt);
      particleRef.current.material.opacity = isHighlighted ? 0.9 : 0.4;
    }
  });

  return (
    <group>
      <Line
        ref={lineRef}
        points={points}
        color={baseColor}
        lineWidth={lineWidth}
        transparent
        opacity={opacity}
        dashed={driftAbs > 0.1}
        dashSize={0.1}
        gapSize={0.05}
      />
      {/* Traveling particle */}
      {weight > 0.3 && (
        <mesh ref={particleRef}>
          <sphereGeometry args={[0.03, 8, 8]} />
          <meshBasicMaterial
            color={mutations > 0 ? '#f39c12' : '#00cec9'}
            transparent
            opacity={0.5}
          />
        </mesh>
      )}
    </group>
  );
}


// ── Ambient brain shell (transparent outer shape) ────────────────────
function BrainShell() {
  const meshRef = useRef();

  useFrame((state) => {
    if (meshRef.current) {
      meshRef.current.rotation.y = state.clock.elapsedTime * 0.05;
    }
  });

  return (
    <mesh ref={meshRef}>
      <icosahedronGeometry args={[2.8, 2]} />
      <meshStandardMaterial
        color="#7c3aed"
        transparent
        opacity={0.02}
        wireframe
        depthWrite={false}
      />
    </mesh>
  );
}


// ── Auto-rotation wrapper ────────────────────────────────────────────
function AutoRotate({ children }) {
  const ref = useRef();
  useFrame((state) => {
    if (ref.current) {
      ref.current.rotation.y = state.clock.elapsedTime * 0.08;
    }
  });
  return <group ref={ref}>{children}</group>;
}


// ── Main Brain3D Component ───────────────────────────────────────────
export default function Brain3D({ connectome }) {
  const [hovered, setHovered] = useState(null);

  if (!connectome) return null;

  const nodes = connectome.nodes || [];
  const edges = connectome.edges || [];
  const gen = connectome.generation ?? 0;
  const totalProp = connectome.total_propagations ?? 0;
  const totalFire = connectome.total_firings ?? 0;

  const nodesById = {};
  nodes.forEach(n => { nodesById[n.id] = n; });

  const mutated = edges.filter(e => (e.mutations ?? 0) > 0).length;
  const maxDrift = edges.reduce((m, e) => Math.max(m, Math.abs(e.drift ?? 0)), 0);

  // Hovered node info
  const hoveredNode = hovered && nodesById[hovered];

  return (
    <div style={{
      width: '100%',
      borderRadius: 12,
      overflow: 'hidden',
      border: '1px solid var(--border, #2d3436)',
      background: '#0a0a12',
      position: 'relative',
    }}>
      {/* Stats overlay */}
      <div style={{
        position: 'absolute', top: 10, left: 14, zIndex: 10,
        display: 'flex', gap: 14, flexWrap: 'wrap', alignItems: 'center',
        pointerEvents: 'none',
      }}>
        <StatBadge label="Gen" value={gen} color="#7c3aed" />
        <StatBadge label="Propagations" value={totalProp} color="#00cec9" />
        <StatBadge label="Fires" value={totalFire} color="#e17055" />
        <StatBadge label="Mutated" value={`${mutated}/${edges.length}`} color="#f39c12" />
        <StatBadge label="Max Drift" value={maxDrift.toFixed(3)} color={maxDrift > 0.3 ? '#e17055' : '#00b894'} />
      </div>

      {/* Title */}
      <div style={{
        position: 'absolute', top: 10, right: 14, zIndex: 10,
        fontSize: 9, color: '#6c7a89', fontStyle: 'italic', pointerEvents: 'none',
      }}>
        FlyWire FAFB v783 — Drosophila Connectome
      </div>

      {/* Hovered info panel */}
      {hoveredNode && (
        <div style={{
          position: 'absolute', bottom: 14, left: 14, zIndex: 10,
          background: 'rgba(10,10,18,0.9)', border: '1px solid #2d3436',
          borderRadius: 8, padding: '8px 14px', pointerEvents: 'none',
          backdropFilter: 'blur(8px)',
        }}>
          <div style={{ fontSize: 12, fontWeight: 700, color: REGION_COLORS[hovered] || '#fff' }}>
            {hovered} — {REGION_LABELS[hovered] || ''}
          </div>
          <div style={{ fontSize: 9, color: '#8e99a4', marginTop: 2 }}>
            {MODULE_LABELS[hovered]} • Module: {hoveredNode.module}
          </div>
          <div style={{ display: 'flex', gap: 16, marginTop: 6, fontSize: 10, fontFamily: 'monospace' }}>
            <span style={{ color: '#00cec9' }}>Act: {(hoveredNode.activation ?? 0).toFixed(3)}</span>
            <span style={{ color: '#f39c12' }}>Thr: {(hoveredNode.threshold ?? 0.5).toFixed(2)}</span>
            <span style={{ color: '#e17055' }}>Fires: {hoveredNode.fire_count ?? 0}</span>
            <span style={{ color: '#fdcb6e' }}>Recv: {(hoveredNode.total_received ?? 0).toFixed(1)}</span>
          </div>
        </div>
      )}

      {/* 3D Canvas */}
      <Canvas
        camera={{ position: [0, 0, 5.5], fov: 50 }}
        style={{ height: 500, cursor: 'grab' }}
        gl={{ antialias: true, alpha: true }}
        onCreated={({ gl }) => {
          gl.setClearColor('#0a0a12', 1);
          gl.toneMapping = THREE.ACESFilmicToneMapping;
          gl.toneMappingExposure = 1.2;
        }}
      >
        {/* Lighting */}
        <ambientLight intensity={0.3} />
        <pointLight position={[5, 5, 5]} intensity={0.8} color="#7c3aed" />
        <pointLight position={[-5, -3, 3]} intensity={0.4} color="#00cec9" />
        <pointLight position={[0, -5, -5]} intensity={0.3} color="#e17055" />

        <AutoRotate>
          {/* Brain shell wireframe */}
          <BrainShell />

          {/* Synaptic connections */}
          {edges.map((e, i) => {
            const sp = NODE_3D[e.src];
            const dp = NODE_3D[e.dst];
            if (!sp || !dp) return null;
            return (
              <SynapticEdge
                key={`${e.src}-${e.dst}`}
                from={[sp.x, sp.y, sp.z]}
                to={[dp.x, dp.y, dp.z]}
                weight={e.weight ?? 0}
                drift={e.drift ?? 0}
                mutations={e.mutations ?? 0}
                isHighlighted={hovered === e.src || hovered === e.dst}
              />
            );
          })}

          {/* Brain region nodes */}
          {nodes.map(n => {
            const pos = NODE_3D[n.id];
            if (!pos) return null;
            return (
              <BrainNode
                key={n.id}
                id={n.id}
                position={[pos.x, pos.y, pos.z]}
                activation={n.activation ?? 0}
                threshold={n.threshold ?? 0.5}
                fireCount={n.fire_count ?? 0}
                module={n.module || ''}
                isHovered={hovered === n.id}
                onHover={setHovered}
              />
            );
          })}
        </AutoRotate>

        {/* User orbit controls */}
        <OrbitControls
          enablePan={false}
          enableZoom={true}
          minDistance={3}
          maxDistance={10}
          autoRotate={false}
          dampingFactor={0.1}
          enableDamping
        />
      </Canvas>

      {/* Legend at bottom-right */}
      <div style={{
        position: 'absolute', bottom: 14, right: 14, zIndex: 10,
        display: 'flex', flexWrap: 'wrap', gap: 6, pointerEvents: 'none',
      }}>
        {Object.entries(REGION_COLORS).map(([id, col]) => (
          <span key={id} style={{
            fontSize: 8, color: col, fontFamily: 'monospace',
            background: 'rgba(10,10,18,0.7)', padding: '2px 6px',
            borderRadius: 4, border: `1px solid ${col}33`,
          }}>
            {id}
          </span>
        ))}
      </div>
    </div>
  );
}


// ── Stat badge subcomponent ──────────────────────────────────────────
function StatBadge({ label, value, color }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
      <span style={{ fontSize: 12, fontWeight: 700, color, fontFamily: 'monospace' }}>{value}</span>
      <span style={{ fontSize: 7, color: '#6c7a89', textTransform: 'uppercase', letterSpacing: 0.5 }}>{label}</span>
    </div>
  );
}
