import React from 'react';
import {AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig, Easing} from 'remotion';
import {fitText} from '@remotion/layout-utils';
import {theme} from './theme';

export type Scene = {
  id: string;
  type: 'title' | 'pipeline' | 'readout' | 'race' | 'branch' | 'bars' | 'metrics' | 'outro';
  duration_s: number;
  narration: string[];
  data: any;
};

const clamp = {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'} as const;

// Fade + rise in, starting at `delay` seconds.
const useEnter = (delay = 0) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const s = spring({frame: frame - delay * fps, fps, config: {damping: 26, stiffness: 260, mass: 0.6}});
  return {opacity: s, transform: `translateY(${(1 - s) * 30}px)`};
};

const Caption: React.FC<{text: string}> = ({text}) => {
  const style = useEnter(0.2);
  return (
    <div style={{position: 'absolute', bottom: 70, width: '100%', textAlign: 'center', ...style}}>
      <span style={{background: 'rgba(0,0,0,0.55)', color: theme.fg, fontSize: 34, padding: '12px 28px', borderRadius: 10}}>
        {text}
      </span>
    </div>
  );
};

const Box: React.FC<{label: string; delay: number; highlight?: boolean; style?: React.CSSProperties}> = ({label, delay, highlight, style}) => {
  const enter = useEnter(delay);
  return (
    <div
      style={{
        position: 'absolute',
        width: 300,
        height: 100,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        background: theme.panel,
        border: `3px solid ${highlight ? theme.accent : theme.muted}`,
        borderRadius: 16,
        color: theme.fg,
        fontSize: 28,
        fontWeight: 600,
        ...style,
        ...enter,
      }}
    >
      {label}
    </div>
  );
};

const Title: React.FC<{d: any}> = ({d}) => (
  <AbsoluteFill style={{alignItems: 'center', justifyContent: 'center', flexDirection: 'column', gap: 24}}>
    <div style={{fontSize: 160, fontWeight: 800, color: theme.accent, ...useEnter(0)}}>{d.title}</div>
    <div style={{fontSize: 56, color: theme.fg, ...useEnter(0.25)}}>{d.subtitle}</div>
    <div style={{fontSize: 36, color: theme.muted, marginTop: 30, ...useEnter(0.7)}}>{d.kicker}</div>
  </AbsoluteFill>
);

const Pipeline: React.FC<{d: any}> = ({d}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const t = frame / fps;
  const col = [160, 810, 1460];
  const inY = [250, 430, 610];
  const midY = 430;
  // Arrows draw in after their source box appears.
  const draw = (start: number) => interpolate(t, [start, start + 0.5], [0, 1], clamp);
  const pulse = 1 + 0.04 * Math.sin(Math.max(0, t - 1.8) * 8) * interpolate(t, [1.8, 2.1, 2.7, 3], [0, 1, 1, 0], clamp);
  const Arrow = ({x1, y1, x2, y2, start}: {x1: number; y1: number; x2: number; y2: number; start: number}) => {
    const len = Math.hypot(x2 - x1, y2 - y1);
    return (
      <line x1={x1} y1={y1} x2={x2} y2={y2} stroke={theme.muted} strokeWidth={4}
        strokeDasharray={len} strokeDashoffset={len * (1 - draw(start))} markerEnd={draw(start) > 0.95 ? 'url(#head)' : undefined} />
    );
  };
  return (
    <AbsoluteFill>
      <svg width={1920} height={1080} style={{position: 'absolute'}}>
        <defs>
          <marker id="head" markerWidth="10" markerHeight="10" refX="8" refY="5" orient="auto">
            <path d="M0,0 L10,5 L0,10 z" fill={theme.muted} />
          </marker>
        </defs>
        {inY.map((y, i) => (
          <Arrow key={i} x1={col[0] + 300} y1={y + 50} x2={col[1] - 10} y2={midY + 50} start={1.2 + i * 0.1} />
        ))}
        <Arrow x1={col[1] + 300} y1={midY + 50} x2={col[2] - 10} y2={midY - 60} start={2.8} />
        <Arrow x1={col[2] + 150} y1={midY + 40} x2={col[2] + 150} y2={midY + 150} start={3.9} />
      </svg>
      {d.inputs.map((label: string, i: number) => (
        <Box key={label} label={label} delay={0.15 + i * 0.2} style={{left: col[0], top: inY[i]}} />
      ))}
      <Box label={d.model} delay={0.8} highlight style={{left: col[1], top: midY, transform: `scale(${pulse})`}} />
      <Box label={d.stages[0]} delay={3.2} style={{left: col[2], top: midY - 110}} />
      <Box label={d.stages[1]} delay={4.3} highlight style={{left: col[2], top: midY + 160}} />
      <div style={{position: 'absolute', top: 120, width: '100%', textAlign: 'center', fontSize: 48, color: theme.fg, fontWeight: 700, ...useEnter(0)}}>
        How it works
      </div>
    </AbsoluteFill>
  );
};

const Race: React.FC<{d: any; duration: number}> = ({d, duration}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const t = frame / fps;
  const scale = d.time_scale ?? 1; // video seconds per measured second
  const start = 0.5;
  const real = Math.max(0, (t - start) / scale); // measured seconds elapsed
  const leftDone = real >= d.left.seconds;
  const rightDone = real >= d.right.seconds;
  const n = d.right.decisions as number;
  const answers = Array.from({length: n}, (_, i) => (i * 7) % 5 < 3 ? 'yes' : 'no');
  const json = '[' + answers.map((a) => `"${a}"`).join(',') + ']';
  const frac = Math.min(1, real / d.left.seconds);
  const tokens = Math.round(frac * d.left.tokens);
  const chars = Math.round(frac * json.length);
  const reveal = interpolate(t, [start + d.left.seconds * scale + 0.1, start + d.left.seconds * scale + 0.5], [0, 1], clamp);
  const lane = (x: number): React.CSSProperties => ({position: 'absolute', left: x, top: 180, width: 820, height: 560, background: theme.panel, borderRadius: 20, padding: 36, boxSizing: 'border-box'});
  const clock = (sec: number, done: boolean) => (
    <div style={{fontFamily: theme.mono, fontSize: 64, color: done ? theme.accent : theme.fg, marginTop: 10}}>{sec.toFixed(3)} s</div>
  );
  return (
    <AbsoluteFill>
      <div style={lane(100)}>
        <div style={{fontSize: 38, color: theme.warn, fontWeight: 700}}>{d.left.label}</div>
        {clock(Math.min(real, d.left.seconds), leftDone)}
        <div style={{fontFamily: theme.mono, fontSize: 30, color: theme.fg, marginTop: 30, wordBreak: 'break-all', lineHeight: 1.5}}>
          {json.slice(0, chars)}<span style={{opacity: leftDone ? 0 : 1}}>▌</span>
        </div>
        <div style={{position: 'absolute', bottom: 30, fontSize: 30, color: theme.muted}}>{tokens} / {d.left.tokens} tokens</div>
      </div>
      <div style={lane(1000)}>
        <div style={{fontSize: 38, color: theme.accent, fontWeight: 700}}>{d.right.label}</div>
        {clock(Math.min(real, d.right.seconds), rightDone)}
        <div style={{display: 'grid', gridTemplateColumns: 'repeat(7, 1fr)', gap: 14, marginTop: 30}}>
          {answers.map((a, i) => (
            <div key={i} style={{height: 60, borderRadius: 10, background: rightDone ? (a === 'yes' ? theme.accent : theme.muted) : '#2a2e37', color: theme.bg, fontSize: 26, fontWeight: 700, display: 'flex', alignItems: 'center', justifyContent: 'center'}}>
              {rightDone ? a : ''}
            </div>
          ))}
        </div>
        <div style={{position: 'absolute', bottom: 30, fontSize: 30, color: theme.muted}}>{d.right.tokens} output tokens · {n} probability pairs</div>
      </div>
      <div style={{position: 'absolute', top: 60, width: '100%', textAlign: 'center', fontSize: 40, color: theme.muted}}>
        21 decisions, {d.note}
      </div>
      <div style={{position: 'absolute', top: 770, width: '100%', textAlign: 'center', fontSize: 90, fontWeight: 800, color: theme.accent, opacity: reveal, transform: `scale(${0.8 + 0.2 * reveal})`}}>
        {d.speedup} faster
      </div>
    </AbsoluteFill>
  );
};

const Bars: React.FC<{d: any}> = ({d}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const t = frame / fps;
  return (
    <AbsoluteFill style={{padding: '120px 200px', boxSizing: 'border-box'}}>
      <div style={{fontSize: 30, color: theme.muted, ...useEnter(0)}}>STATE</div>
      <div style={{fontSize: 40, color: theme.fg, marginBottom: 30, ...useEnter(0.1)}}>{d.state}</div>
      <div style={{fontSize: 30, color: theme.muted, ...useEnter(0.5)}}>QUESTION</div>
      <div style={{fontSize: 40, color: theme.fg, marginBottom: 50, ...useEnter(0.6)}}>{d.question}</div>
      {d.options.map((o: any, i: number) => {
        const grow = interpolate(t, [1.2 + i * 0.12, 2 + i * 0.12], [0, 1], {...clamp, easing: Easing.out(Easing.cubic)});
        return (
          <div key={o.id} style={{display: 'flex', alignItems: 'center', height: 80, gap: 30}}>
            <div style={{width: 320, fontFamily: theme.mono, fontSize: 32, color: theme.fg, textAlign: 'right'}}>{o.id}</div>
            <div style={{width: 900 * o.p * grow, minWidth: 4, height: 50, borderRadius: 8, background: i === 0 ? theme.accent : theme.muted}} />
            <div style={{fontFamily: theme.mono, fontSize: 32, color: theme.fg}}>{(o.p * grow).toFixed(2)}</div>
          </div>
        );
      })}
    </AbsoluteFill>
  );
};

const Readout: React.FC<{d: any}> = ({d}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const t = frame / fps;
  const dim = interpolate(t, [2, 2.6], [1, 0.15], clamp);
  const rowH = 70;
  return (
    <AbsoluteFill>
      <div style={{position: 'absolute', top: 70, width: '100%', textAlign: 'center', fontSize: 36, color: theme.muted, ...useEnter(0)}}>
        Q: {d.question}
      </div>
      <div style={{position: 'absolute', left: 160, top: 170, fontSize: 30, color: theme.fg, fontWeight: 700, ...useEnter(0.1)}}>
        Next-token scores (whole vocabulary)
      </div>
      {d.vocab.map((v: any, i: number) => {
        const enter = interpolate(t, [0.2 + i * 0.1, 0.6 + i * 0.1], [0, 1], clamp);
        return (
          <div key={v.tok} style={{position: 'absolute', left: 160, top: 240 + i * rowH, display: 'flex', alignItems: 'center', gap: 24, opacity: enter * (v.slot ? 1 : dim)}}>
            <div style={{width: 150, textAlign: 'right', fontFamily: theme.mono, fontSize: 34, color: v.slot && t > 2 ? theme.accent : theme.fg}}>{v.tok}</div>
            <div style={{width: (v.logit - 15) * 50 * enter, height: 40, borderRadius: 6, background: v.slot && t > 2 ? theme.accent : theme.muted}} />
            <div style={{fontFamily: theme.mono, fontSize: 28, color: theme.muted}}>{v.logit.toFixed(1)}</div>
          </div>
        );
      })}
      <div style={{position: 'absolute', left: 160, top: 240 + d.vocab.length * rowH, fontSize: 28, color: theme.muted, opacity: interpolate(t, [1, 1.4], [0, 1], clamp) * dim}}>
        … every other token in the vocabulary
      </div>
      <div style={{position: 'absolute', left: 1000, top: 400, fontSize: 64, color: theme.accent, opacity: interpolate(t, [2.8, 3.2], [0, 1], clamp)}}>→</div>
      <div style={{position: 'absolute', left: 1100, top: 300, fontSize: 30, color: theme.fg, fontWeight: 700, ...useEnter(3)}}>softmax over A, B, C</div>
      {d.slots.map((s: any, i: number) => {
        const grow = interpolate(t, [3.3 + i * 0.12, 4.1 + i * 0.12], [0, 1], {...clamp, easing: Easing.out(Easing.cubic)});
        return (
          <div key={s.letter} style={{position: 'absolute', left: 1100, top: 370 + i * 90, ...useEnter(3.1 + i * 0.1)}}>
            <div style={{fontFamily: theme.mono, fontSize: 28, color: theme.muted}}>{s.letter} → {s.option}</div>
            <div style={{display: 'flex', alignItems: 'center', gap: 16, marginTop: 6}}>
              <div style={{width: Math.max(4, 560 * s.p * grow), height: 36, borderRadius: 6, background: i === 0 ? theme.accent : theme.muted}} />
              <div style={{fontFamily: theme.mono, fontSize: 30, color: theme.fg}}>{(s.p * grow).toFixed(2)}</div>
            </div>
          </div>
        );
      })}
      <div style={{position: 'absolute', left: 1100, top: 680, fontSize: 30, color: theme.warn, ...useEnter(4.6)}}>{d.note}</div>
    </AbsoluteFill>
  );
};

const Branch: React.FC<{d: any}> = ({d}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const t = frame / fps;
  const n = d.branches as number;
  const fill = interpolate(t, [0.3, 1.6], [0, 1], {...clamp, easing: Easing.inOut(Easing.cubic)});
  const fan = interpolate(t, [2.2, 3.2], [0, 1], clamp);
  const lit = t > 3.5;
  const cache = {x: 860, y: 290, w: 240, h: 120};
  const strip = {x: 1300, y0: 150, h: 14, gap: 7, w: 460};
  const maxV = Math.max(...d.rates.map((r: any) => r.v));
  return (
    <AbsoluteFill>
      <div style={{position: 'absolute', left: 160, top: 260, fontSize: 30, color: theme.fg, fontWeight: 700, ...useEnter(0)}}>{d.prefix_label}</div>
      <div style={{position: 'absolute', left: 160, top: 310, width: 600, height: 80, borderRadius: 10, background: '#2a2e37', overflow: 'hidden'}}>
        <div style={{width: 600 * fill, height: '100%', background: theme.muted}} />
      </div>
      <div style={{position: 'absolute', left: 160, top: 400, fontSize: 26, color: theme.muted, opacity: fill}}>prefilled once</div>
      <svg width={1920} height={1080} style={{position: 'absolute'}}>
        <line x1={760} y1={350} x2={760 + (cache.x - 770) * interpolate(t, [1.6, 2], [0, 1], clamp)} y2={350} stroke={theme.muted} strokeWidth={4} />
        {Array.from({length: n}, (_, i) => {
          const y = strip.y0 + i * (strip.h + strip.gap) + strip.h / 2;
          const x1 = cache.x + cache.w, y1 = cache.y + cache.h / 2;
          return <line key={i} x1={x1} y1={y1} x2={x1 + (strip.x - x1) * fan} y2={y1 + (y - y1) * fan} stroke={lit ? theme.accent : theme.muted} strokeWidth={2} opacity={0.7} />;
        })}
      </svg>
      <div style={{position: 'absolute', left: cache.x, top: cache.y, width: cache.w, height: cache.h, display: 'flex', alignItems: 'center', justifyContent: 'center', background: theme.panel, border: `3px solid ${theme.accent}`, borderRadius: 16, color: theme.fg, fontSize: 32, fontWeight: 700, ...useEnter(1.8)}}>
        {d.cache_label}
      </div>
      <div style={{position: 'absolute', left: strip.x, top: 95, fontSize: 30, color: theme.fg, fontWeight: 700, ...useEnter(2.2)}}>{d.branch_label}</div>
      {Array.from({length: n}, (_, i) => (
        <div key={i} style={{position: 'absolute', left: strip.x, top: strip.y0 + i * (strip.h + strip.gap), width: strip.w, height: strip.h, borderRadius: 4, background: lit ? theme.accent : '#2a2e37', opacity: fan}} />
      ))}
      <div style={{position: 'absolute', left: 160, top: 640, fontSize: 30, color: theme.muted, ...useEnter(4.2)}}>{d.unit} · {d.workload}</div>
      {d.rates.map((r: any, i: number) => {
        const grow = interpolate(t, [4.4 + i * 0.25, 5.4 + i * 0.25], [0, 1], {...clamp, easing: Easing.out(Easing.cubic)});
        const best = r.v === maxV;
        return (
          <div key={r.label} style={{position: 'absolute', left: 160, top: 700 + i * 75, display: 'flex', alignItems: 'center', gap: 24, opacity: interpolate(t, [4.3 + i * 0.25, 4.5 + i * 0.25], [0, 1], clamp)}}>
            <div style={{width: 360, textAlign: 'right', fontSize: 32, color: theme.fg}}>{r.label}</div>
            <div style={{width: Math.max(4, 1000 * (r.v / maxV) * grow), height: 44, borderRadius: 6, background: best ? theme.accent : theme.muted}} />
            <div style={{fontFamily: theme.mono, fontSize: 32, color: best ? theme.accent : theme.fg}}>{(r.v * grow).toFixed(2)}</div>
          </div>
        );
      })}
    </AbsoluteFill>
  );
};

// Shrink text to one line inside its container (the browser would otherwise wrap it).
const fitSize = (text: string, width: number, max: number, fontWeight = '400') =>
  Math.min(max, fitText({text, withinWidth: width, fontFamily: theme.font, fontWeight}).fontSize);

const Metrics: React.FC<{d: any}> = ({d}) => {
  const inner = 500 - 2 * 36;
  return (
    <AbsoluteFill style={{alignItems: 'center', justifyContent: 'center', flexDirection: 'row', gap: 50}}>
      {d.cards.map((c: any, i: number) => (
        <div key={c.label} style={{width: 500, height: 380, background: theme.panel, borderRadius: 24, padding: '44px 36px', boxSizing: 'border-box', display: 'flex', flexDirection: 'column', justifyContent: 'space-between', alignItems: 'center', textAlign: 'center', whiteSpace: 'nowrap', ...useEnter(0.2 + i * 0.35)}}>
          <div style={{fontSize: fitSize(c.label, inner, 32), color: theme.muted}}>{c.label}</div>
          <div style={{fontSize: fitSize(c.value, inner, 96, '800'), fontWeight: 800, color: theme.accent, lineHeight: 1}}>{c.value}</div>
          <div style={{fontSize: fitSize(c.compare, inner, 32), color: theme.fg}}>{c.compare}</div>
        </div>
      ))}
    </AbsoluteFill>
  );
};

const Outro: React.FC<{d: any}> = ({d}) => (
  <AbsoluteFill style={{alignItems: 'center', justifyContent: 'center', flexDirection: 'column', gap: 40}}>
    <div style={{fontSize: 96, fontWeight: 800, color: theme.fg, ...useEnter(0)}}>{d.headline}</div>
    <div style={{fontFamily: theme.mono, fontSize: 44, color: theme.accent, ...useEnter(0.35)}}>{d.url}</div>
  </AbsoluteFill>
);

export const SceneView: React.FC<{scene: Scene}> = ({scene}) => {
  const {data: d} = scene;
  const body = {
    title: <Title d={d} />,
    pipeline: <Pipeline d={d} />,
    readout: <Readout d={d} />,
    race: <Race d={d} duration={scene.duration_s} />,
    branch: <Branch d={d} />,
    bars: <Bars d={d} />,
    metrics: <Metrics d={d} />,
    outro: <Outro d={d} />,
  }[scene.type];
  return (
    <AbsoluteFill style={{background: theme.bg, fontFamily: theme.font}}>
      {body}
      {/* Reference renderer: shows the first narration sentence; no audio or cue timing. */}
      <Caption text={scene.narration[0]} />
    </AbsoluteFill>
  );
};
