/**
 * Animated TCG Digital careers loader mark (gear-shaped C with sparkles + a
 * traveling progress dot). Ported verbatim from the approved mockups
 * (tcgdigital-careers-loader / tcgdigital-career-portal). The `.lp-mark …`
 * animation rules live in the global stylesheet (index.css), parsed once so the
 * animation stays GPU-smooth; shared by the careers landing page and the
 * candidate dashboard loader.
 */
import { memo } from "react";

const LOADER_MARK = `
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 220 170" role="img" aria-labelledby="lp-mark-title lp-mark-desc">
  <title id="lp-mark-title">TCG Digital inspired animated loading mark</title>
  <desc id="lp-mark-desc">A minimal gear-shaped C with animated sparkles and a traveling progress dot.</desc>
  <defs>
    <linearGradient id="lpGearGradient" x1="30" y1="135" x2="145" y2="25" gradientUnits="userSpaceOnUse">
      <stop offset="0" stop-color="#00a68a"/>
      <stop offset=".48" stop-color="#11a9a2"/>
      <stop offset="1" stop-color="#e2d34d"/>
    </linearGradient>
    <linearGradient id="lpGoldGradient" x1="130" y1="44" x2="180" y2="98" gradientUnits="userSpaceOnUse">
      <stop offset="0" stop-color="#ffd96a"/>
      <stop offset=".55" stop-color="#f5be3e"/>
      <stop offset="1" stop-color="#e99a20"/>
    </linearGradient>
    <filter id="lpSoftGlow" x="-80%" y="-80%" width="260%" height="260%">
      <feGaussianBlur stdDeviation="4" result="blur"/>
      <feColorMatrix in="blur" type="matrix"
        values="0 0 0 0 0.12  0 0 0 0 0.63  0 0 0 0 0.58  0 0 0 .34 0"/>
      <feMerge><feMergeNode/><feMergeNode in="SourceGraphic"/></feMerge>
    </filter>
    <filter id="lpGoldGlow" x="-100%" y="-100%" width="300%" height="300%">
      <feGaussianBlur stdDeviation="4" result="blur"/>
      <feColorMatrix in="blur" type="matrix"
        values="0 0 0 0 1  0 0 0 0 .72  0 0 0 0 .16  0 0 0 .42 0"/>
      <feMerge><feMergeNode/><feMergeNode in="SourceGraphic"/></feMerge>
    </filter>
  </defs>

  <circle class="orbit" cx="95" cy="86" r="69"/>
  <g class="loader-mark">
    <path class="gear-arc" d="M96 31 A55 55 0 1 0 96 141" />
    <rect class="gear-tab tab-1" x="82" y="13" width="27" height="18" rx="3"/>
    <rect class="gear-tab tab-2" x="38" y="28" width="26" height="18" rx="3" transform="rotate(-43 51 37)"/>
    <rect class="gear-tab tab-3" x="17" y="74" width="27" height="18" rx="3"/>
    <rect class="gear-tab tab-4" x="36" y="124" width="26" height="18" rx="3" transform="rotate(43 49 133)"/>
    <rect class="gear-tab tab-5" x="82" y="140" width="27" height="18" rx="3"/>
    <path class="spark spark-main" d="M150 39 C154 51 163 60 176 64 C163 68 154 77 150 90 C146 77 137 68 124 64 C137 60 146 51 150 39Z"/>
    <path class="spark spark-small s2" d="M130 86 C132 92 137 97 143 99 C137 101 132 106 130 112 C128 106 123 101 117 99 C123 97 128 92 130 86Z"/>
    <path class="spark spark-small s3" d="M151 108 C154 116 160 122 168 125 C160 128 154 134 151 142 C148 134 142 128 134 125 C142 122 148 116 151 108Z"/>
    <circle class="runner" r="4.3"/>
  </g>
</svg>`;

/**
 * Memoized so the animated mark renders exactly once per mount. Its parents (the
 * careers Landing splash and the candidate Dashboard splash) re-render frequently
 * while data settles and the loader message rotates; without memo the mark's
 * subtree re-renders in step, which can visibly restart the CSS entrance
 * animation ("the gear keeps redrawing"). memo() gives it a stable identity so
 * the animation plays through once, uninterrupted.
 */
export const CareersLoaderMark = memo(function CareersLoaderMark() {
  return <div className="lp-mark" aria-hidden="true" dangerouslySetInnerHTML={{ __html: LOADER_MARK }} />;
});
