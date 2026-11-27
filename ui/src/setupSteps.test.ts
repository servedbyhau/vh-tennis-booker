import { describe, expect, it } from "vitest";
import type { SetupReport } from "./api/types";
import { machinesOf } from "./machines";
import {
  appMissing,
  firstOpen,
  missingMachines,
  type SetupFacts,
  setupProblem,
  stepsDone,
} from "./setupSteps";
import { account, customer } from "./test/customers";
import { settings } from "./test/settings";

const READY: SetupReport = {
  mumu: "ok",
  wake_timers: "ok",
  machines: [
    { mumu_index: 0, screen: "ok", performance: "ok", app: "ok" },
    { mumu_index: 1, screen: "ok", performance: "fixable", app: "unknown" },
  ],
};

/** Machine 1 books with MuMu 0, machine 2 with MuMu 1 when `both`. */
function facts(fields: Partial<SetupFacts> = {}, both = false): SetupFacts {
  const chosen = settings({ instances: both ? [{ ...settings(), mumu_index: 1 }] : [] });
  return {
    keepOn: true,
    report: READY,
    machines: machinesOf(chosen, [0, 1]),
    customers: [customer("c1", { accounts: [account("a1", { device: 0 })] })],
    daily: true,
    ...fields,
  };
}

describe("stepsDone", () => {
  it("is done once every booking machine has what it needs", () => {
    expect(stepsDone(facts())).toEqual({
      power: true,
      mumu: true,
      machines: true,
      app: true,
      accounts: true,
      daily: true,
    });
  });

  it("asks only of the machines the runs book with", () => {
    const done = stepsDone(facts({}, true));
    expect([done.app, done.accounts]).toEqual([false, false]);
    expect(appMissing(facts({}, true))).toEqual([1]);
  });

  it("tells a booking machine whose MuMu instance is not made", () => {
    const report = { ...READY, machines: READY.machines.slice(0, 1) };
    expect(missingMachines(facts({ report }, true))).toEqual([1]);
    expect(stepsDone(facts({ report }, true)).machines).toBe(false);
  });

  it("counts nothing not read yet as done", () => {
    const done = stepsDone(
      facts({ keepOn: undefined, report: undefined, customers: undefined, daily: undefined }),
    );
    expect(Object.values(done).some(Boolean)).toBe(false);
  });

  it("counts MuMu found at another path as there", () => {
    expect(stepsDone(facts({ report: { ...READY, mumu: "fixable" } })).mumu).toBe(true);
    expect(stepsDone(facts({ report: { ...READY, mumu: "user" } })).mumu).toBe(false);
  });
});

describe("firstOpen", () => {
  it("is the first step not done, else the first", () => {
    expect(firstOpen(stepsDone(facts({ daily: false })))).toBe("daily");
    expect(firstOpen(stepsDone(facts()))).toBe("power");
  });
});

describe("setupProblem", () => {
  it("is what keeps a booking machine from booking, worst first", () => {
    expect(setupProblem(facts())).toBeNull(); // machine 2's app not known, and it does not book
    expect(setupProblem(facts({ report: { ...READY, mumu: "user" } }))).toEqual({ kind: "mumu" });
    const one = { ...READY, machines: READY.machines.slice(0, 1) };
    expect(setupProblem(facts({ report: one }, true))).toEqual({ kind: "machines", indexes: [1] });
    const noApp = {
      ...READY,
      machines: READY.machines.map((item) => ({ ...item, app: "user" as const })),
    };
    expect(setupProblem(facts({ report: noApp }, true))).toEqual({ kind: "app", indexes: [0, 1] });
  });

  it("says nothing of an app not known yet, or before the checks are read", () => {
    expect(setupProblem(facts({}, true))).toBeNull();
    expect(setupProblem(facts({ report: undefined }))).toBeNull();
  });
});
