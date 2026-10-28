/** Three bats cross the night once when the Villa Diodati tree opens. Hidden with reduced motion. */
const BAT = "M32 18c-3-6-9-9-15-8 3 2 4 5 3 8-4-3-10-3-14 0 5 1 9 4 11 9 2-3 6-5 10-4l5 3 5-3c4-1 8 1 10 4 2-5 6-8 11-9-4-3-10-3-14 0-1-3 0-6 3-8-6-1-12 2-15 8z";

export function Bats() {
  return (
    <div className="bats" aria-hidden="true">
      {[0, 1, 2].map((i) => (
        <svg key={i} className={`bat bat-${i}`} viewBox="0 0 64 32" width="44" height="22">
          <path d={BAT} />
        </svg>
      ))}
    </div>
  );
}
