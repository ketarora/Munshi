export default function Waveform({ active = false, bars = 7 }: { active?: boolean; bars?: number }) {
  return (
    <span className={`wave ${active ? "on" : ""}`} aria-hidden="true">
      {Array.from({ length: bars }, (_, index) => (
        <i key={index} style={{ animationDelay: `${index * 90}ms` }} />
      ))}
    </span>
  );
}
