import { describe, expect, it } from "vitest";
import { runSummary } from "../../test/runs";
import { averageOf, rateOf, statsOf } from "./stats";

const lost = (slot: string, reason: string) => ({
  slot,
  ok: false,
  reason,
  finished_at: "2026-10-15T06:00:05.000",
  seconds: 2,
  commands: 10,
});

describe("statsOf", () => {
  it("sums the 06:00 runs since a day by machine, by slot and by reason", () => {
    const runs = [
      runSummary(1, { device: 0, started_at: "2026-10-15T05:45:00.000" }),
      runSummary(2, {
        device: 1,
        started_at: "2026-10-15T05:45:00.000",
        slots: [lost("15:00 - 16:00", "fully booked"), lost("16:00 - 17:00", "fully booked")],
      }),
      runSummary(3, { device: 1, trigger: "manual" }), // started by hand: left out
      runSummary(4, { device: 1, dry_run: true, trigger: "scheduled" }), // a dry run: left out
      runSummary(5, { device: 0, started_at: "2026-09-01T05:45:00.000" }), // too old
    ];

    const stats = statsOf(runs, "2026-09-20", 0);

    expect(stats.runs).toBe(2);
    expect([stats.all.tried, stats.all.booked]).toEqual([4, 2]);
    expect(stats.byMachine.map((item) => [item.key, item.tried, item.booked])).toEqual([
      ["0", 2, 2],
      ["1", 2, 0],
    ]);
    expect(stats.bySlot.map((item) => [item.key, rateOf(item)])).toEqual([
      ["15:00 - 16:00", 50],
      ["16:00 - 17:00", 50],
    ]);
    expect(stats.reasons).toEqual([{ reason: "fully booked", count: 2 }]);
    expect(averageOf(stats.all)).toBeCloseTo(5.15);
  });

  it("tells nothing of nothing tried", () => {
    const stats = statsOf([], "2026-09-20", 0);

    expect(rateOf(stats.all)).toBeNull();
    expect(averageOf(stats.all)).toBeNull();
  });
});
