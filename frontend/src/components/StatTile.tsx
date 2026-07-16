/** A single absolute-value stat tile (e.g. "12.4 kg"), the neutral sibling of MetricTile — which is
 *  delta-oriented and forces a +/- prefix. Used by the home dashboard's stat row. */
export function StatTile({ value, unit, label }: { value: string; unit?: string; label: string }) {
  return (
    <div className="rounded-xl p-4 border bg-white border-gray-200 text-center">
      <p className="text-2xl font-black m-0 leading-none text-gray-900">
        {value}
        {unit && <span className="text-sm font-semibold ml-1 text-gray-500">{unit}</span>}
      </p>
      <p className="text-xs text-gray-500 m-0 mt-1.5 leading-snug">{label}</p>
    </div>
  );
}
