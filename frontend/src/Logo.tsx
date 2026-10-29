/** Tell the Tree: a speech bubble with a family inside, drawn with the app's own notation
 *  (two parents, the knot that joins them, a child). Takes the theme's colours. */
export function Logo({ size = 32 }: { size?: number }) {
  return (
    <svg className="logo" width={size} height={size} viewBox="0 0 64 64" aria-hidden="true">
      <path d="M11 7H53a5 5 0 0 1 5 5V41a5 5 0 0 1-5 5H27L15 57V46H11a5 5 0 0 1-5-5V12a5 5 0 0 1 5-5Z"
            fill="none" stroke="currentColor" strokeWidth="3.6" strokeLinejoin="round" />
      <rect x="14" y="14" width="14" height="9" rx="1.5" fill="currentColor" />
      <rect x="36" y="14" width="14" height="9" rx="1.5" fill="currentColor" />
      <path d="M21 23V28.5H43V23" fill="none" stroke="currentColor" strokeWidth="2.6" />
      <rect x="28.4" y="25" width="7.2" height="7.2" transform="rotate(45 32 28.6)" fill="var(--accent)" />
      <rect x="25" y="32.5" width="14" height="9" rx="1.5" fill="var(--accent)" />
    </svg>
  );
}
