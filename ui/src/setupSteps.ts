/**
 * The steps of the Setup page, in the order a new PC takes them, and whether each is done. A
 * step is done once every machine the runs book with has what it needs; one not known yet (the
 * checks not read) is not done.
 */
import type { Customer, SetupReport } from "./api/types";
import { accountOn, enabledMachines, type Machine } from "./machines";

export const STEPS = ["power", "mumu", "machines", "app", "accounts", "daily"] as const;

export type StepId = (typeof STEPS)[number];

/** What the steps are told from. */
export interface SetupFacts {
  /** Whether the PC is kept on; `undefined` while Windows is not read. */
  keepOn: boolean | undefined;
  report: SetupReport | undefined;
  machines: readonly Machine[];
  customers: readonly Customer[] | undefined;
  /** Whether the daily booking is on; `undefined` while not read. */
  daily: boolean | undefined;
}

/** Return the MuMu instances of the machines the runs book with. */
function booked(machines: readonly Machine[]): number[] {
  return enabledMachines(machines).flatMap((machine) =>
    machine.mumuIndex === null ? [] : [machine.mumuIndex],
  );
}

/** Return the checks of each booked machine whose MuMu instance is on the PC. */
function present(facts: SetupFacts) {
  const indexes = booked(facts.machines);
  return (facts.report?.machines ?? []).filter((item) => indexes.includes(item.mumu_index));
}

/** Return the MuMu instances the runs book with that are not on the PC. */
export function missingMachines(facts: SetupFacts): number[] {
  if (facts.report === undefined) {
    return [];
  }
  const made = facts.report.machines.map((item) => item.mumu_index);
  return booked(facts.machines).filter((index) => !made.includes(index));
}

/** Return the MuMu instances of booked machines whose Vinhomes app is not there or not known. */
export function appMissing(facts: SetupFacts): number[] {
  return present(facts)
    .filter((item) => item.app !== "ok")
    .map((item) => item.mumu_index);
}

/** Return the MuMu instances of booked machines without an account chosen. */
export function accountMissing(facts: SetupFacts): number[] {
  const customers = facts.customers ?? [];
  return booked(facts.machines).filter((index) => accountOn(customers, index) === null);
}

/** Tell whether each step is done. */
export function stepsDone(facts: SetupFacts): Record<StepId, boolean> {
  const report = facts.report;
  return {
    power: facts.keepOn === true,
    mumu: report !== undefined && report.mumu !== "user",
    machines:
      report !== undefined && report.machines.length > 0 && missingMachines(facts).length === 0,
    app: report !== undefined && present(facts).length > 0 && appMissing(facts).length === 0,
    accounts: facts.customers !== undefined && accountMissing(facts).length === 0,
    daily: facts.daily === true,
  };
}

/** Return the first step not done, else the first. */
export function firstOpen(done: Record<StepId, boolean>): StepId {
  return STEPS.find((step) => !done[step]) ?? STEPS[0];
}
