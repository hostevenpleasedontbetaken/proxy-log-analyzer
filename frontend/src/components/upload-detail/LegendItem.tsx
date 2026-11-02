/** One chart legend entry: a colour swatch and the series name. Renders an <li>. */
export function LegendItem({ color, label }: { color: string; label: string }) {
  return (
    <li className="flex items-center gap-1.5">
      <span className="size-2.5 rounded-sm" style={{ background: color }} aria-hidden />
      {label}
    </li>
  )
}
