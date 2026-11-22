/**
 * What would cost a booking of the next start although everything is switched on: a machine
 * that books with no chosen account, and machines that would book the same court and slot.
 */
import { useMemo } from "react";
import { useCustomers, useSettings } from "./api/queries";
import type { Customer, Settings } from "./api/types";
import { accountOn, enabledMachines, type Machine, useMachines } from "./machines";

/** A court and slot that several machines would book: one gets it at most. */
export interface Clash {
  court: string;
  slot: string;
  /** The machines' places, the first one first. */
  places: number[];
}

/**
 * Return the machines that book with whichever account their app has logged in: logged out,
 * they book nothing. None while no customer has an account, as before there were customers.
 */
export function withoutAccount(
  machines: readonly Machine[],
  customers: readonly Customer[],
): Machine[] {
  if (customers.every((customer) => customer.accounts.length === 0)) {
    return [];
  }
  return enabledMachines(machines).filter(
    ({ mumuIndex }) => mumuIndex !== null && accountOn(customers, mumuIndex) === null,
  );
}

/** Return the courts and slots that more than one machine would book. */
export function clashes(settings: Settings, machines: readonly Machine[]): Clash[] {
  const found = new Map<string, Clash>();
  for (const { place, entry } of machines) {
    const booking = entry === null ? undefined : [settings, ...settings.instances][entry];
    for (const slot of booking?.slots ?? []) {
      const court = booking?.court ?? "";
      const key = `${court} ${slot}`;
      const places = [...(found.get(key)?.places ?? []), place];
      found.set(key, { court, slot, places });
    }
  }
  return [...found.values()].filter(({ places }) => places.length > 1);
}

/** Read what to look at before the next start; nothing until it is known. */
export function useReadiness(): { accountless: Machine[]; clashing: Clash[] } {
  const machines = useMachines();
  const customers = useCustomers().data;
  const settings = useSettings().data;
  return useMemo(
    () => ({
      accountless: withoutAccount(machines, customers ?? []),
      clashing: settings === undefined ? [] : clashes(settings, machines),
    }),
    [machines, customers, settings],
  );
}
