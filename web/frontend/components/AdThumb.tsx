"use client";

const GRAD_PAIRS = [
  ["#0a2e3d", "#06181f"],
  ["#2a1f4a", "#160f28"],
  ["#1a2f4a", "#0d1a28"],
  ["#3d2a1a", "#22160d"],
  ["#1a3d3d", "#0d2222"],
  ["#2a1a3d", "#160d22"],
  ["#3d1a2a", "#220d16"],
];

function nameHash(s: string): number {
  let h = 0;
  for (let i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) & 0xffff;
  return h;
}

type Props = {
  src: string | null;
  name: string;
  className?: string;
};

export default function AdThumb({ src, name, className = "h-10 w-10 rounded" }: Props) {
  const [from, to] = GRAD_PAIRS[nameHash(name) % GRAD_PAIRS.length];
  const initial = (name.trim()[0] ?? "?").toUpperCase();

  return (
    <div
      className={`relative overflow-hidden select-none ${className}`}
      style={{ background: `linear-gradient(135deg, ${from} 0%, ${to} 100%)` }}
    >
      <span className="absolute inset-0 flex items-center justify-center font-bold text-white/40" style={{ fontSize: "1.1rem" }}>
        {initial}
      </span>
      {src && (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={src}
          alt=""
          className="absolute inset-0 h-full w-full object-cover"
          onError={(e) => { (e.target as HTMLImageElement).style.display = "none"; }}
        />
      )}
    </div>
  );
}
