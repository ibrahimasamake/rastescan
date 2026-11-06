/** Generic placeholder emblem: a road and a wheel in a ring. Deliberately not any government's seal. */
export function Emblem({ size = 52 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 64 64" role="img" aria-label="Placeholder emblem">
      <circle cx="32" cy="32" r="30" fill="#0b2545" />
      <circle cx="32" cy="32" r="25" fill="none" stroke="#f29a2e" strokeWidth="2.5" />
      <path d="M24 50 29 14h6l5 36z" fill="#ffffff" />
      <path d="M32 18v5m0 6v6m0 6v6" stroke="#0b2545" strokeWidth="2.4" strokeLinecap="round" />
      <circle cx="32" cy="32" r="18" fill="none" stroke="#ffffff" strokeWidth="1.2" strokeDasharray="2 4" opacity="0.6" />
    </svg>
  );
}
