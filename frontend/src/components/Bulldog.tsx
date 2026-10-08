// "Dan", the chat assistant's bulldog: a nod to Handsome Dan, Yale's bulldog mascot.
// Drawn entirely in SVG (no image files, per AGENTS.md). It blinks while idle and tilts its head while thinking.

interface Props {
  size?: number
  mood?: 'idle' | 'thinking'
  className?: string
}

export default function Bulldog({ size = 40, mood = 'idle', className = '' }: Props) {
  return (
    <svg
      className={`bulldog bulldog-${mood} ${className}`}
      width={size}
      height={size}
      viewBox="0 0 100 100"
      role="img"
      aria-label="Dan the bulldog"
    >
      <g className="bulldog-head">
        {/* folded ears */}
        <path d="M20 36 Q8 14 33 19 Q27 27 28 37 Z" fill="#a9805b" stroke="#3a2c25" strokeWidth="2.5" strokeLinejoin="round" />
        <path d="M80 36 Q92 14 67 19 Q73 27 72 37 Z" fill="#a9805b" stroke="#3a2c25" strokeWidth="2.5" strokeLinejoin="round" />

        {/* head */}
        <path
          d="M50 17 C74 17 89 33 89 53 C89 74 72 86 50 86 C28 86 11 74 11 53 C11 33 26 17 50 17 Z"
          fill="#f3ece2"
          stroke="#3a2c25"
          strokeWidth="2.5"
        />
        {/* tan patch over one eye */}
        <ellipse cx="34" cy="45" rx="13" ry="11" fill="#dcb98f" />

        {/* forehead wrinkles */}
        <path d="M38 29 Q50 25 62 29" fill="none" stroke="#7a5c47" strokeWidth="2" strokeLinecap="round" />
        <path d="M41 34 Q50 31 59 34" fill="none" stroke="#7a5c47" strokeWidth="2" strokeLinecap="round" />

        {/* eyes + blinking lids */}
        <circle cx="35" cy="46" r="5" fill="#1d1717" />
        <circle cx="65" cy="46" r="5" fill="#1d1717" />
        <circle cx="36.6" cy="44.4" r="1.6" fill="#fff" />
        <circle cx="66.6" cy="44.4" r="1.6" fill="#fff" />
        <g className="bulldog-lids">
          <ellipse cx="35" cy="46" rx="6" ry="6" fill="#dcb98f" />
          <ellipse cx="65" cy="46" rx="6" ry="6" fill="#f3ece2" />
        </g>
        {/* droopy brows */}
        <path d="M28 39 Q35 36 41 40" fill="none" stroke="#3a2c25" strokeWidth="2.2" strokeLinecap="round" />
        <path d="M72 39 Q65 36 59 40" fill="none" stroke="#3a2c25" strokeWidth="2.2" strokeLinecap="round" />

        {/* muzzle, nose, jowls */}
        <ellipse cx="50" cy="66" rx="26" ry="16" fill="#fbf8f3" stroke="#3a2c25" strokeWidth="2.2" />
        <path d="M41 56 Q50 50 59 56 Q59 62 50 63 Q41 62 41 56 Z" fill="#2b2220" />
        <ellipse cx="46.5" cy="55.5" rx="2.2" ry="1.2" fill="#6b5a55" />
        <path d="M50 63 L50 67" stroke="#3a2c25" strokeWidth="2.2" strokeLinecap="round" />
        <path d="M50 67 Q41 75 31 70" fill="none" stroke="#3a2c25" strokeWidth="2.2" strokeLinecap="round" />
        <path d="M50 67 Q59 75 69 70" fill="none" stroke="#3a2c25" strokeWidth="2.2" strokeLinecap="round" />

        {/* classic bulldog underbite */}
        <path d="M37 72 Q50 81 63 72" fill="#c9656f" stroke="#3a2c25" strokeWidth="2.2" strokeLinejoin="round" />
        <path d="M40.5 74.5 L42.5 69 L44.5 75.5 Z" fill="#fff" stroke="#3a2c25" strokeWidth="1.4" strokeLinejoin="round" />
        <path d="M55.5 75.5 L57.5 69 L59.5 74.5 Z" fill="#fff" stroke="#3a2c25" strokeWidth="1.4" strokeLinejoin="round" />
      </g>

      {/* Yale-blue collar with a "Y" tag */}
      <path d="M22 82 Q50 94 78 82 L80 89 Q50 101 20 89 Z" fill="#00356b" stroke="#0a1f3d" strokeWidth="1.5" />
      <circle cx="50" cy="93" r="6.5" fill="#ffffff" stroke="#00356b" strokeWidth="1.5" />
      <text x="50" y="96.4" textAnchor="middle" fontFamily="Georgia, serif" fontSize="9" fontWeight="700" fill="#00356b">
        Y
      </text>
    </svg>
  )
}
