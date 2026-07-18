import { useEffect, useState } from "react";

/** First two word-initials of a name, uppercased (fallback when there's no photo). */
export function initials(name: string): string {
  return name.split(/\s+/).filter(Boolean).slice(0, 2).map((p) => p[0]).join("").toUpperCase() || "U";
}

interface AvatarProps {
  name: string;
  /** presigned photo url (icon for small sizes, profile for large); falsy => show initials */
  src?: string | null;
  /** pixel size; also drives the fallback font-size. Ignored if `className` sets its own box. */
  size?: number;
  /** corner radius in px (defaults to a soft ~29% of size) */
  radius?: number;
  className?: string;
}

/**
 * The person's photo everywhere in the app — falls back to their coloured initials when no
 * photo is set, or if the image fails to load (e.g. an expired presigned url).
 */
export function Avatar({ name, src, size = 34, radius, className }: AvatarProps) {
  const [failed, setFailed] = useState(false);
  // a new src (fresh presigned url) should get another chance to load
  useEffect(() => setFailed(false), [src]);

  const show = !!src && !failed;
  const style: React.CSSProperties = {
    width: size,
    height: size,
    borderRadius: radius ?? Math.round(size * 0.29),
    fontSize: Math.max(10, Math.round(size * 0.4)),
  };

  return (
    <div className={`avatar${className ? ` ${className}` : ""}`} style={style} title={name} aria-label={name}>
      {show
        ? <img src={src!} alt="" onError={() => setFailed(true)} />
        : initials(name)}
    </div>
  );
}
