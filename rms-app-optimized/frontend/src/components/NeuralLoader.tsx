import { useEffect, useState } from "react";

/**
 * True only once `active` has stayed true continuously for `delay` ms. Lets a page defer
 * showing the loader so quick (<1s) loads never flash it — the region stays blank instead.
 */
export function useDelayedFlag(active: boolean, delay = 1000): boolean {
  const [shown, setShown] = useState(false);
  useEffect(() => {
    if (!active) { setShown(false); return; }
    const t = setTimeout(() => setShown(true), delay);
    return () => clearTimeout(t);
  }, [active, delay]);
  return shown;
}

/**
 * Neural-network page loader — layered nodes with flowing signal edges, styled to the
 * app's accent palette. Pure CSS animation (see `.nn-*` rules in index.css), no assets.
 * Use for full-page loading states where the shell can't render until data arrives.
 */
const X = [26, 100, 174, 234];               // layer x-positions (viewBox 260×170)
const LAYERS = [[48, 85, 122], [24, 67, 110, 153], [48, 85, 122], [67, 103]];

// fully-connected edges between consecutive layers
const EDGES: [number, number, number, number][] = [];
for (let l = 0; l < LAYERS.length - 1; l++) {
  for (const y1 of LAYERS[l]) {
    for (const y2 of LAYERS[l + 1]) EDGES.push([X[l], y1, X[l + 1], y2]);
  }
}

export function NeuralLoader({ label = "Loading" }: { label?: string }) {
  let n = 0;
  return (
    <div className="nn-loader" role="status" aria-live="polite">
      <svg className="nn-svg" viewBox="0 0 260 170" fill="none" aria-hidden="true">
        <g className="nn-edges">
          {EDGES.map(([x1, y1, x2, y2], i) => (
            <line key={i} className="nn-edge" x1={x1} y1={y1} x2={x2} y2={y2} style={{ animationDelay: `${(i % 7) * -0.2}s` }} />
          ))}
        </g>
        <g className="nn-nodes">
          {LAYERS.map((col, l) => col.map((y) => (
            <circle key={`${l}-${y}`} className="nn-node" cx={X[l]} cy={y} r={6} style={{ animationDelay: `${(n++ % 6) * 0.18}s` }} />
          )))}
        </g>
      </svg>
      <div className="nn-label">{label}</div>
    </div>
  );
}
