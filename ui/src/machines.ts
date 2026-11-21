/**
 * The machines the home screen shows, one at a time: the top of the settings first, then
 * the other MuMu instances by their index, each with its own account. There are always
 * three at least: the instances the settings lack show switched off, on the lowest MuMu
 * instances free (each books only once switched on, which adds its instance).
 */
import { useMemo } from "react";
import { useSettings } from "./api/queries";
import type { Settings } from "./api/types";

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

/** Return the machines of `settings`, the first alone until they have loaded. */
export function machinesOf(settings: Settings | undefined): Machine[] {
  if (settings === undefined) {
    return [FIRST];
  }
  const booked: Placed[] = settings.instances.map((instance, place) => ({
    mumuIndex: instance.mumu_index,
    entry: place + 1,
  }));
  const used = new Set([settings.mumu_index, ...booked.map((item) => item.mumuIndex)]);
  const spare: Placed[] = spareIndexes(used, MIN_MACHINES - 1 - booked.length).map((mumuIndex) => ({
    mumuIndex,
    entry: null,
  }));
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
  return useMemo(() => machinesOf(settings.data), [settings.data]);
}
