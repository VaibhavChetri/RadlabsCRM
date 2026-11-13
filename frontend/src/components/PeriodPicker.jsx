// PeriodPicker.jsx
// ----------------
// This week / This month / Custom dates. Shared by the analytics strip and the
// Team stats page. `value` is { preset, from, to } (local "YYYY-MM-DD" dates,
// both included); picking a preset fills in its dates.

import { PERIOD_PRESETS, presetRange } from '../format';

export default function PeriodPicker({ value, onChange }) {
  const pickPreset = (preset) => {
    // Custom starts from the dates on screen, so the user only adjusts them.
    onChange(preset === 'custom' ? { ...value, preset } : { preset, ...presetRange(preset) });
  };

  return (
    <div className="period-picker">
      <div className="segmented" role="group" aria-label="Period">
        {PERIOD_PRESETS.map(([key, label]) => (
          <button key={key} type="button" aria-pressed={value.preset === key}
            className={value.preset === key ? 'active' : undefined}
            onClick={() => pickPreset(key)}>
            {label}
          </button>
        ))}
      </div>
      {value.preset === 'custom' && (
        <span className="period-dates">
          <input type="date" aria-label="From" value={value.from} max={value.to}
            onChange={(e) => e.target.value && onChange({ ...value, from: e.target.value })} />
          <span className="muted">to</span>
          <input type="date" aria-label="To" value={value.to} min={value.from}
            onChange={(e) => e.target.value && onChange({ ...value, to: e.target.value })} />
        </span>
      )}
    </div>
  );
}
