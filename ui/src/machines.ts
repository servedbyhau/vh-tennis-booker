/**
 * The machines the home screen shows, one at a time: the top of the settings first, then
 * the other MuMu instances by their index, each with its own account. Every MuMu instance on
 * the PC shows, and three at least: the instances the settings lack show switched off (each
 * books only once switched on, which adds its instance), the ones MuMu does not list yet on
 * the lowest indexes free.
 */
import { useMemo } from "react";
import { useMumuInstances, useSettings } from "./api/queries";
import type { Customer, Settings } from "./api/types";

/** The machines shown at least: the first, and two beside it. */
const MIN_MACHINES = 3;

export interface Machine {
  /** 0 for the top of the settings, then each other machine by its MuMu index. */
  place: number;
  /** Its MuMu instance, `null` until the settings have loaded. */
  mumuIndex: number | null;
  /** Where its ticks are kept: "" for the first, else its MuMu index. */
  key: string;
  /** Whether the runs book with it; the first always does. */
  enabled: boolean;
  /**
   * Where its choices are in the settings: 0 for the top, then one more than its instance's
   * place in `instances`; `null` while it is switched off.
   */
  entry: number | null;
}

/** The one machine known before the settings load. */
const FIRST: Machine = { place: 0, mumuIndex: null, key: "", enabled: true, entry: 0 };

/** A machine's MuMu instance and where its choices are in the settings. */
type Placed = Pick<Machine, "entry"> & { mumuIndex: number };

/** Return the `count` lowest MuMu instances not in `used`. */
function spareIndexes(used: ReadonlySet<number>, count: number): number[] {
  const spare: number[] = [];
  for (let index = 0; spare.length < count; index += 1) {
    if (!used.has(index)) {
      spare.push(index);
    }
  }
  return spare;
}

/**
 * Return the machines of `settings` and of the MuMu instances on the PC (`mumu`, empty while
 * not known), the first alone until the settings have loaded.
 */
export function machinesOf(
  settings: Settings | undefined,
  mumu: readonly number[] = [],
): Machine[] {
  if (settings === undefined) {
    return [FIRST];
  }
  const booked: Placed[] = settings.instances.map((instance, place) => ({
    mumuIndex: instance.mumu_index,
    entry: place + 1,
  }));
  const used = new Set([settings.mumu_index, ...booked.map((item) => item.mumuIndex)]);
  const listed = [...new Set(mumu)].filter((index) => !used.has(index));
  const taken = new Set([...used, ...listed]);
  const spare: Placed[] = [
    ...listed,
    ...spareIndexes(taken, MIN_MACHINES - 1 - booked.length - listed.length),
  ].map((mumuIndex) => ({ mumuIndex, entry: null }));
  // By MuMu index, so a machine keeps its name whichever of the others is on.
  const others = [...booked, ...spare].sort((a, b) => a.mumuIndex - b.mumuIndex);
  return [{ mumuIndex: settings.mumu_index, entry: 0 }, ...others].map(
    ({ mumuIndex, entry }, place) => ({
      place,
      mumuIndex,
      key: place === 0 ? "" : String(mumuIndex),
      enabled: entry !== null,
      entry,
    }),
  );
}

/** Return machine `place`, the last if it is gone. */
export function machineAt(machines: readonly Machine[], place: number): Machine {
  return machines[Math.min(place, machines.length - 1)] ?? FIRST;
}

/** Return the machines the runs book with. */
export function enabledMachines(machines: readonly Machine[]): Machine[] {
  return machines.filter((machine) => machine.enabled);
}

/** Read the machines from the settings. */
export function useMachines(): Machine[] {
  const settings = useSettings();
  const mumu = useMumuInstances();
  return useMemo(() => machinesOf(settings.data, mumu.data), [settings.data, mumu.data]);
}

/** Return the account MuMu instance `mumuIndex` books with and its customer, or `null`. */
export function accountOn(customers: readonly Customer[], mumuIndex: number) {
  for (const customer of customers) {
    const account = customer.accounts.find((item) => item.device === mumuIndex);
    if (account !== undefined) {
      return { customer, account };
    }
  }
  return null;
}
