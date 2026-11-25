"use client";

import { NumberInput } from "@/components/NumberInput";

type ResourceStepProps = {
  numResources: number;
  manualMode: boolean;
  mirrored: boolean;
  eraseMode: boolean;
  disabled?: boolean;
  onNumResourcesChange: (value: number) => void;
  onManualModeChange: (manual: boolean) => void;
  onMirroredChange: (mirrored: boolean) => void;
  onEraseModeChange: (erasing: boolean) => void;
  onRandom: () => void;
  onUndo: () => void;
  onClear: () => void;
};

export function ResourceStep({
  numResources,
  manualMode,
  mirrored,
  eraseMode,
  disabled,
  onNumResourcesChange,
  onManualModeChange,
  onMirroredChange,
  onEraseModeChange,
  onRandom,
  onUndo,
  onClear,
}: ResourceStepProps) {
  return (
    <section className="panel-section">
      <h2>5. Resources</h2>
      <p>Place mirrored resource pools manually, switch to erase mode to remove individual pools, or generate them automatically.</p>
      <div className="control-grid">
        <label>
          Num Resource Pulls
          <NumberInput value={numResources} min={0} max={50} onChange={onNumResourcesChange} disabled={disabled} />
        </label>
        {manualMode && (
          <label className="checkbox-label" style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginTop: "1.5rem" }}>
            <input
              type="checkbox"
              checked={mirrored}
              onChange={(e) => onMirroredChange(e.target.checked)}
              disabled={disabled}
            />
            Mirrored Placement
          </label>
        )}
      </div>
      <div className="button-row">
        <button
          type="button"
          className={manualMode ? "active-btn" : "ghost-btn"}
          onClick={() => onManualModeChange(true)}
          disabled={disabled}
        >
          Manual
        </button>
        <button
          type="button"
          className={!manualMode ? "active-btn" : "ghost-btn"}
          onClick={() => onManualModeChange(false)}
          disabled={disabled}
        >
          Random
        </button>
        <button
          type="button"
          className={eraseMode ? "active-btn" : "ghost-btn"}
          onClick={() => onEraseModeChange(!eraseMode)}
          disabled={disabled || !manualMode}
        >
          Eraser
        </button>
      </div>
      <div className="button-row">
        <button type="button" className="primary-btn" onClick={onRandom} disabled={disabled || manualMode}>
          Place Random
        </button>
        <button type="button" className="ghost-btn" onClick={onUndo} disabled={disabled}>
          Undo
        </button>
        <button type="button" className="ghost-btn" onClick={onClear} disabled={disabled}>
          Clear
        </button>
      </div>
    </section>
  );
}
