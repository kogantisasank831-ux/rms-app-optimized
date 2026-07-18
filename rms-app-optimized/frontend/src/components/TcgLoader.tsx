/**
 * TCG Digital animated loading mark — a gear-shaped "C" that draws in, sprouts tabs,
 * with drifting sparkles, a traveling runner dot and a faint orbit. Light-mode, decorative.
 * Pure CSS animation (no JS loops); see the `.tcg-*` rules in index.css.
 * Geometry from mockups/tcgdigital-careers-loader.html (viewBox 0 0 220 170).
 * Marked aria-hidden — the loader text carries the semantics.
 */
export function TcgLoader() {
  return (
    <div className="tcg-mark" aria-hidden="true">
      <svg viewBox="0 0 220 170" role="presentation" focusable="false" xmlns="http://www.w3.org/2000/svg">
        <defs>
          <linearGradient id="tcgGearGrad" x1="30" y1="135" x2="145" y2="25" gradientUnits="userSpaceOnUse">
            <stop offset="0" stopColor="#00a68a" />
            <stop offset=".48" stopColor="#11a9a2" />
            <stop offset="1" stopColor="#e2d34d" />
          </linearGradient>
          <linearGradient id="tcgGoldGrad" x1="130" y1="44" x2="180" y2="98" gradientUnits="userSpaceOnUse">
            <stop offset="0" stopColor="#ffd96a" />
            <stop offset=".55" stopColor="#f5be3e" />
            <stop offset="1" stopColor="#e99a20" />
          </linearGradient>
          <filter id="tcgSoftGlow" x="-80%" y="-80%" width="260%" height="260%">
            <feGaussianBlur stdDeviation="4" result="blur" />
            <feColorMatrix in="blur" type="matrix" values="0 0 0 0 0.12  0 0 0 0 0.63  0 0 0 0 0.58  0 0 0 .34 0" />
            <feMerge><feMergeNode /><feMergeNode in="SourceGraphic" /></feMerge>
          </filter>
          <filter id="tcgGoldGlow" x="-100%" y="-100%" width="300%" height="300%">
            <feGaussianBlur stdDeviation="4" result="blur" />
            <feColorMatrix in="blur" type="matrix" values="0 0 0 0 1  0 0 0 0 .72  0 0 0 0 .16  0 0 0 .42 0" />
            <feMerge><feMergeNode /><feMergeNode in="SourceGraphic" /></feMerge>
          </filter>
        </defs>

        <circle className="tcg-orbit" cx="95" cy="86" r="69" />

        <g className="tcg-body">
          <path className="tcg-arc" d="M96 31 A55 55 0 1 0 96 141" />

          <rect className="tcg-tab t1" x="82" y="13" width="27" height="18" rx="3" />
          <rect className="tcg-tab t2" x="38" y="28" width="26" height="18" rx="3" transform="rotate(-43 51 37)" />
          <rect className="tcg-tab t3" x="17" y="74" width="27" height="18" rx="3" />
          <rect className="tcg-tab t4" x="36" y="124" width="26" height="18" rx="3" transform="rotate(43 49 133)" />
          <rect className="tcg-tab t5" x="82" y="140" width="27" height="18" rx="3" />

          <path className="tcg-spark tcg-spark-main" d="M150 39 C154 51 163 60 176 64 C163 68 154 77 150 90 C146 77 137 68 124 64 C137 60 146 51 150 39Z" />
          <path className="tcg-spark tcg-spark-sm s2" d="M130 86 C132 92 137 97 143 99 C137 101 132 106 130 112 C128 106 123 101 117 99 C123 97 128 92 130 86Z" />
          <path className="tcg-spark tcg-spark-sm s3" d="M151 108 C154 116 160 122 168 125 C160 128 154 134 151 142 C148 134 142 128 134 125 C142 122 148 116 151 108Z" />

          <circle className="tcg-runner" r="4.3" />
        </g>
      </svg>
    </div>
  );
}
