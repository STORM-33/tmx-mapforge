"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { CSSProperties } from "react";
import { NumberInput } from "@/components/NumberInput";

type GridEditorProps = {
  grid: number[][];
  mirroring: string;
  disabled?: boolean;
  onGridChange: (grid: number[][]) => void;
};

const cloneGrid = (grid: number[][]) => grid.map((row) => [...row]);

const gridsEqual = (a: number[][], b: number[][]) =>
  a.length === b.length && a.every((row, i) => row.length === b[i].length && row.every((value, j) => value === b[i][j]));

function mirroredCells(row: number, col: number, size: number, mode: string) {
  const cells = new Set<string>([`${row}:${col}`]);
  const add = (r: number, c: number) => {
    if (r >= 0 && c >= 0 && r < size && c < size) cells.add(`${r}:${c}`);
  };
  if (mode === "horizontal" || mode === "both") add(size - 1 - row, col);
  if (mode === "vertical" || mode === "both") add(row, size - 1 - col);
  if (mode === "diagonal1") add(col, row);
  if (mode === "diagonal2") add(size - 1 - col, size - 1 - row);
  if (mode === "both") add(size - 1 - row, size - 1 - col);
  return [...cells].map((cell) => cell.split(":").map(Number) as [number, number]);
}

// Every cell one brush dab at (row, col) touches, mirrored copies included.
// Painting and the hover preview both use this, so they cannot disagree.
function brushFootprint(row: number, col: number, brushSize: number, size: number, mode: string) {
  const cells = new Map<string, [number, number]>();
  const start = -Math.floor(brushSize / 2);
  for (let dr = start; dr < start + brushSize; dr++) {
    for (let dc = start; dc < start + brushSize; dc++) {
      const brushRow = row + dr;
      const brushCol = col + dc;
      if (brushRow < 0 || brushCol < 0 || brushRow >= size || brushCol >= size) continue;
      for (const [r, c] of mirroredCells(brushRow, brushCol, size, mode)) cells.set(`${r}:${c}`, [r, c]);
    }
  }
  return [...cells.values()];
}

export function GridEditor({ grid, mirroring, disabled, onGridChange }: GridEditorProps) {
  const [tool, setTool] = useState<"brush" | "erase">("brush");
  const [brushSize, setBrushSize] = useState(1);
  const [history, setHistory] = useState({ canUndo: false, canRedo: false });
  const [hoverCell, setHoverCell] = useState<[number, number] | null>(null);
  const activeBrushSize = Math.min(brushSize, grid.length, 10);
  const isPainting = useRef(false);
  const gridRef = useRef(grid);
  const past = useRef<number[][][]>([]);
  const future = useRef<number[][][]>([]);
  const strokeStart = useRef<number[][] | null>(null);

  useEffect(() => {
    gridRef.current = grid;
  }, [grid]);

  const refreshHistory = useCallback(() => {
    setHistory({ canUndo: past.current.length > 0, canRedo: future.current.length > 0 });
  }, []);

  const finishStroke = useCallback(() => {
    isPainting.current = false;
    const before = strokeStart.current;
    strokeStart.current = null;
    if (before && !gridsEqual(before, gridRef.current)) {
      past.current.push(before);
      future.current = [];
      refreshHistory();
    }
  }, [refreshHistory]);

  useEffect(() => {
    window.addEventListener("pointerup", finishStroke);
    window.addEventListener("pointercancel", finishStroke);
    return () => {
      window.removeEventListener("pointerup", finishStroke);
      window.removeEventListener("pointercancel", finishStroke);
    };
  }, [finishStroke]);

  const applyGrid = useCallback((next: number[][], saveUndo = true) => {
    const before = gridRef.current;
    if (gridsEqual(before, next)) return;
    finishStroke();
    if (saveUndo) past.current.push(cloneGrid(gridRef.current));
    future.current = [];
    gridRef.current = next;
    onGridChange(next);
    refreshHistory();
  }, [finishStroke, onGridChange, refreshHistory]);

  const paint = useCallback((row: number, col: number) => {
    const next = cloneGrid(gridRef.current);
    const value = tool === "brush" ? 1 : 0;
    for (const [r, c] of brushFootprint(row, col, activeBrushSize, next.length, mirroring)) next[r][c] = value;
    if (!gridsEqual(gridRef.current, next)) {
      gridRef.current = next;
      onGridChange(next);
    }
  }, [activeBrushSize, mirroring, onGridChange, tool]);

  // Cells the next click would paint, shown as an outline under the cursor.
  const previewCells = useMemo(() => {
    if (!hoverCell || disabled) return null;
    const [row, col] = hoverCell;
    if (row >= grid.length || col >= grid.length) return null;
    return new Set(
      brushFootprint(row, col, activeBrushSize, grid.length, mirroring).map(([r, c]) => `${r}:${c}`),
    );
  }, [activeBrushSize, disabled, grid.length, hoverCell, mirroring]);

  const resize = (size: number) => {
    const previous = gridRef.current;
    const oldSize = previous.length;
    // Sample from cell centres: a resize then drops or repeats a middle line.
    // Sampling from the leading edge dropped the last line when shrinking and
    // repeated the first when growing, so the shape drifted on every step.
    const sample = (index: number) => Math.min(oldSize - 1, Math.floor((index + 0.5) * oldSize / size));
    const next = Array.from({ length: size }, (_, row) =>
      Array.from({ length: size }, (_, col) => previous[sample(row)][sample(col)]),
    );
    applyGrid(next);
  };

  const undo = () => {
    finishStroke();
    const previous = past.current.pop();
    if (!previous) return;
    future.current.push(cloneGrid(gridRef.current));
    gridRef.current = previous;
    onGridChange(previous);
    refreshHistory();
  };

  const redo = () => {
    finishStroke();
    const next = future.current.pop();
    if (!next) return;
    past.current.push(cloneGrid(gridRef.current));
    gridRef.current = next;
    onGridChange(next);
    refreshHistory();
  };

  const clear = () => applyGrid(gridRef.current.map((row) => row.map(() => 0)));

  return (
    <>
      <div className="grid-editor-controls">
        <label>
          Grid size
          <NumberInput value={grid.length} min={5} max={30} step={1} onChange={resize} disabled={disabled} />
        </label>
        <div className="grid-tools" role="group" aria-label="Grid paint tool">
          <button type="button" className={tool === "brush" ? "active" : ""} aria-pressed={tool === "brush"} onClick={() => setTool("brush")} disabled={disabled}>Brush</button>
          <button type="button" className={tool === "erase" ? "active" : ""} aria-pressed={tool === "erase"} onClick={() => setTool("erase")} disabled={disabled}>Erase</button>
        </div>
        <div className="grid-history-tools">
          <button type="button" onClick={undo} disabled={disabled || !history.canUndo}>Undo</button>
          <button type="button" onClick={redo} disabled={disabled || !history.canRedo}>Redo</button>
          <button type="button" onClick={clear} disabled={disabled || grid.every((row) => row.every((value) => value === 0))}>Clear</button>
        </div>
      </div>
      <label className="grid-brush-size">
        Brush / Eraser size: {activeBrushSize}
        <input
          type="range"
          min={1}
          max={Math.min(10, grid.length)}
          step={1}
          value={activeBrushSize}
          onChange={(event) => setBrushSize(Number(event.target.value))}
          disabled={disabled}
        />
      </label>
      <p>Drag to paint cells. Mirroring applies to both tools.</p>
      <div
        className="coast-grid"
        style={{ "--grid-size": grid.length } as CSSProperties}
        onPointerLeave={() => setHoverCell(null)}
      >
        {grid.map((row, rowIndex) =>
          row.map((value, colIndex) => (
            <button
              key={`${rowIndex}-${colIndex}`}
              type="button"
              aria-label={`Row ${rowIndex + 1}, column ${colIndex + 1}: ${value ? "land" : "water"}`}
              className={`grid-cell ${value ? "on" : "off"}${
                previewCells?.has(`${rowIndex}:${colIndex}`) ? (tool === "erase" ? " preview-erase" : " preview") : ""
              }`}
              onPointerDown={(event) => {
                event.preventDefault();
                strokeStart.current = cloneGrid(gridRef.current);
                isPainting.current = true;
                paint(rowIndex, colIndex);
              }}
              onPointerEnter={(event) => {
                if (event.pointerType !== "touch") setHoverCell([rowIndex, colIndex]);
                if (isPainting.current) paint(rowIndex, colIndex);
              }}
              disabled={disabled}
            />
          )),
        )}
      </div>
    </>
  );
}
