/**
 * What the management shows of each machine, put together from what the app already reads: the
 * settings (what it books), the customers (whose account it books with) and the runs (how its
 * last booking went).
 */
import type { TFunction } from "i18next";
import { useMemo } from "react";
import { useCustomers, useRuns, useSettings } from "../../api/queries";
import type { Customer, CustomerAccount, RunSummary, Settings } from "../../api/types";
import { localToday } from "../../format";
import { accountOn, type Machine, useMachines } from "../../machines";
import type { Formatter } from "../../useFormat";

/** The runs read for the machines' last bookings: a few days of three machines and more. */
export const RECENT_RUNS = 60;

/** What a machine books: its sport, court and slots, as the settings hold them. */
export interface Booking {
  subdivision: string;
  sport: string;
  court: string;
  slots: string[];
}

export interface MachineFacts {
  machine: Machine;
  /** `undefined` while the machine is switched off: it books nothing. */
  booking: Booking | undefined;
  attached: { customer: Customer; account: CustomerAccount } | null;
  /** Its newest 06:00 booking (the daily task's), if one is in the runs read. */
  lastRun: RunSummary | undefined;
}

/** Return what machine `machine` books by `settings`, `undefined` while it is off. */
export function bookingOf(settings: Settings, machine: Machine): Booking | undefined {
  if (machine.entry === null) {
    return undefined;
  }
  const entry = machine.entry === 0 ? settings : settings.instances[machine.entry - 1];
  if (entry === undefined) {
    return undefined;
  }
  return {
    subdivision: entry.subdivision || settings.subdivision,
    sport: entry.sport,
    court: entry.court,
    slots: [...entry.slots],
  };
}

/**
 * Return the newest 06:00 booking of each MuMu instance in `runs` (newest first): the daily
 * task's, not a dry run or a booking started by hand. A run of no recorded instance, from before
 * there were several, is the first machine's.
 */
export function lastRuns(runs: readonly RunSummary[], first: number): Map<number, RunSummary> {
  const found = new Map<number, RunSummary>();
  for (const run of runs) {
    if (run.dry_run || run.trigger !== "scheduled") {
      continue;
    }
    const device = run.device ?? first;
    if (!found.has(device)) {
      found.set(device, run);
    }
  }
  return found;
}

/** Return each machine's facts, once the settings, customers and runs have loaded. */
export function machineFactsOf(
  machines: readonly Machine[],
  settings: Settings,
  customers: readonly Customer[],
  runs: readonly RunSummary[],
): MachineFacts[] {
  const last = lastRuns(runs, settings.mumu_index);
  return machines.map((machine) => ({
    machine,
    booking: bookingOf(settings, machine),
    attached: machine.mumuIndex === null ? null : accountOn(customers, machine.mumuIndex),
    lastRun: machine.mumuIndex === null ? undefined : last.get(machine.mumuIndex),
  }));
}

/** Read the machines' facts; `undefined` until all they are made of has loaded. */
export function useMachineFacts(): MachineFacts[] | undefined {
  const machines = useMachines();
  const settings = useSettings();
  const customers = useCustomers();
  const runs = useRuns({ limit: RECENT_RUNS });
  return useMemo(
    () =>
      settings.data === undefined || customers.data === undefined || runs.data === undefined
        ? undefined
        : machineFactsOf(machines, settings.data, customers.data, runs.data),
    [machines, settings.data, customers.data, runs.data],
  );
}

/** When a run was and what it booked for: "sáng nay · cho Thứ Sáu 27/11". */
export function runWhen(t: TFunction, f: Formatter, run: RunSummary): string {
  const when = f.when(run.started_at, localToday());
  return run.play_date === null
    ? when
    : t("pages.machines.runFor", { when, day: f.day(run.play_date) });
}
