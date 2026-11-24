/** What the 06:00 runs of the last days tell, summed by machine, by slot and by reason. */
import type { RunSummary } from "../../api/types";

/** The days the statistics look back on. */
export const STATS_DAYS = 30;

/** Slots tried and booked, with the seconds the booked ones took. */
export interface Tally {
  key: string;
  tried: number;
  booked: number;
  /** Seconds of the booked slots, for their average. */
  seconds: number[];
}

function tally(found: Map<string, Tally>, key: string, ok: boolean, seconds: number | null) {
  const item = found.get(key) ?? { key, tried: 0, booked: 0, seconds: [] };
  item.tried += 1;
  if (ok) {
    item.booked += 1;
    if (seconds !== null) {
      item.seconds.push(seconds);
    }
  }
  found.set(key, item);
}

/** Return the share booked, in whole percent, `null` with nothing tried. */
export function rateOf(item: Pick<Tally, "tried" | "booked">): number | null {
  return item.tried === 0 ? null : Math.round((item.booked / item.tried) * 100);
}

/** Return the average seconds of the booked slots, `null` without one. */
export function averageOf(item: Pick<Tally, "seconds">): number | null {
  return item.seconds.length === 0
    ? null
    : item.seconds.reduce((sum, value) => sum + value, 0) / item.seconds.length;
}

/** The statistics of `runs`: in all, by MuMu instance, by slot, and the reasons of the slots lost. */
export interface Stats {
  all: Tally;
  byMachine: Tally[];
  bySlot: Tally[];
  /** Each reason a slot was lost for, as the engine wrote it, with how often. */
  reasons: { reason: string | null; count: number }[];
  runs: number;
}

/**
 * Sum the 06:00 runs among `runs` that started on or after `since` (a day, "2026-10-26"): dry
 * runs and runs started by hand are left out. A run of no recorded instance is `first`'s.
 */
export function statsOf(runs: readonly RunSummary[], since: string, first: number): Stats {
  const kept = runs.filter(
    (run) => run.trigger === "scheduled" && !run.dry_run && run.started_at.slice(0, 10) >= since,
  );
  const all = new Map<string, Tally>();
  const machines = new Map<string, Tally>();
  const slots = new Map<string, Tally>();
  const reasons = new Map<string | null, number>();
  for (const run of kept) {
    for (const slot of run.slots) {
      tally(all, "all", slot.ok, slot.seconds);
      tally(machines, String(run.device ?? first), slot.ok, slot.seconds);
      tally(slots, slot.slot, slot.ok, slot.seconds);
      if (!slot.ok) {
        reasons.set(slot.reason, (reasons.get(slot.reason) ?? 0) + 1);
      }
    }
  }
  return {
    all: all.get("all") ?? { key: "all", tried: 0, booked: 0, seconds: [] },
    byMachine: [...machines.values()].sort((a, b) => Number(a.key) - Number(b.key)),
    bySlot: [...slots.values()].sort((a, b) => a.key.localeCompare(b.key)),
    reasons: [...reasons.entries()]
      .map(([reason, count]) => ({ reason, count }))
      .sort((a, b) => b.count - a.count),
    runs: kept.length,
  };
}
