// Geometric monogram generated deterministically from the slug.
// Avoids depending on external image files while still giving each client
// a distinctive mark.

type Palette = { bg: string; ink: string };

const PALETTES: Palette[] = [
  { bg: "#1F4D3C", ink: "#F2EEE5" },
  { bg: "#143228", ink: "#D7C68C" },
  { bg: "#B57A1F", ink: "#1A1916" },
  { bg: "#8C2A2A", ink: "#F2EEE5" },
  { bg: "#1A1916", ink: "#D7C68C" },
  { bg: "#3F4738", ink: "#F2EEE5" },
  { bg: "#5A3A1F", ink: "#ECE6D8" },
  { bg: "#2D4A6A", ink: "#F2EEE5" },
  { bg: "#704321", ink: "#F2EEE5" },
  { bg: "#0E2A20", ink: "#B57A1F" },
];

function hashString(s: string): number {
  let h = 0;
  for (let i = 0; i < s.length; i++) {
    h = (h << 5) - h + s.charCodeAt(i);
    h |= 0;
  }
  return Math.abs(h);
}

function initials(name: string): string {
  return name
    .split(/[-\s]+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((w) => w[0]?.toUpperCase() ?? "")
    .join("");
}

export function CaseMark({
  slug,
  size = 56,
  rounded = false,
}: {
  slug: string;
  size?: number;
  rounded?: boolean;
}) {
  const h = hashString(slug);
  const palette = PALETTES[h % PALETTES.length];
  const variant = h % 4;
  const letters = initials(slug);

  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 64 64"
      role="img"
      aria-label={`Marca ${slug}`}
      className="shrink-0"
    >
      <defs>
        <clipPath id={`clip-${slug}`}>
          <rect width="64" height="64" rx={rounded ? 32 : 0} />
        </clipPath>
      </defs>
      <g clipPath={`url(#clip-${slug})`}>
        <rect width="64" height="64" fill={palette.bg} />
        {variant === 0 && (
          <circle cx="64" cy="0" r="34" fill={palette.ink} opacity="0.18" />
        )}
        {variant === 1 && (
          <polygon points="0,64 64,64 64,16" fill={palette.ink} opacity="0.16" />
        )}
        {variant === 2 && (
          <>
            <rect x="0" y="48" width="64" height="2" fill={palette.ink} opacity="0.6" />
            <rect x="0" y="52" width="64" height="1" fill={palette.ink} opacity="0.4" />
          </>
        )}
        {variant === 3 && (
          <circle cx="48" cy="48" r="22" fill={palette.ink} opacity="0.14" />
        )}
        <text
          x="32"
          y="36"
          textAnchor="middle"
          dominantBaseline="middle"
          fontFamily="Fraunces, serif"
          fontWeight="600"
          fontSize="26"
          fill={palette.ink}
          letterSpacing="-1.2"
        >
          {letters}
        </text>
      </g>
    </svg>
  );
}
