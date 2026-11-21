import { describe, expect, it } from "vitest";
import type { Settings } from "./api/types";
import { machinesOf } from "./machines";
import { settings } from "./test/settings";

/** An `[[instances]]` entry of MuMu instance `index`. */
function instance(index: number): Settings["instances"][number] {
  return {
    mumu_index: index,
    slots: ["20:00 - 21:00"],
    subdivision: "",
    sport: "tennis",
    court: "S9 - Sân tennis",
    venue_keyword: "Origami",
  };
}

/** Each machine as its MuMu instance, whether it books, and where its choices are. */
function shape(fields: Parameters<typeof settings>[0]) {
  return machinesOf(settings(fields)).map(({ mumuIndex, enabled, entry }) => ({
    mumuIndex,
    enabled,
    entry,
  }));
}

describe("machinesOf", () => {
  it("shows three machines, the two beside the first off, without an instance", () => {
    expect(shape({})).toEqual([
      { mumuIndex: 0, enabled: true, entry: 0 },
      { mumuIndex: 1, enabled: false, entry: null },
      { mumuIndex: 2, enabled: false, entry: null },
    ]);
  });

  it("keeps each machine in its place whichever is on", () => {
    expect(shape({ instances: [instance(2)] })).toEqual([
      { mumuIndex: 0, enabled: true, entry: 0 },
      { mumuIndex: 1, enabled: false, entry: null },
      { mumuIndex: 2, enabled: true, entry: 1 },
    ]);
    // In the config's order, each still finds its own entry.
    expect(shape({ instances: [instance(2), instance(1)] })).toEqual([
      { mumuIndex: 0, enabled: true, entry: 0 },
      { mumuIndex: 1, enabled: true, entry: 2 },
      { mumuIndex: 2, enabled: true, entry: 1 },
    ]);
  });

  it("offers the lowest MuMu instances free beside a first that is not MuMu 0", () => {
    expect(shape({ mumu_index: 1 }).map((machine) => machine.mumuIndex)).toEqual([1, 0, 2]);
  });

  it("shows every instance of the config, more than three too", () => {
    const four = [instance(1), instance(2), instance(3)];
    expect(shape({ instances: four }).map((machine) => machine.mumuIndex)).toEqual([0, 1, 2, 3]);
  });

  it("names a machine's ticks by its MuMu index, the first's by none", () => {
    expect(machinesOf(settings({})).map((machine) => machine.key)).toEqual(["", "1", "2"]);
  });
});
