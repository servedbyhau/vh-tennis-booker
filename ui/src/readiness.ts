/**
 * What would cost a booking of the next start although everything is switched on: a machine
 * that books with no chosen account, machines that would book the same court and slot, and an
 * account with fewer bookings left in the month than its machine's slots.
 */
import { useMemo } from "react";
import { useCustomers, useSettings } from "./api/queries";
import type { Customer, Settings } from "./api/types";
import { accountOn, enabledMachines, type Machine, useMachines } from "./machines";
import { leftOf, useBookingMonth } from "./quota";

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

/** A machine whose account has fewer bookings left in the month than the slots it books. */
export interface Short {
  place: number;
  left: number;
  slots: number;
  /** The customer whose account it is. */
  customer: string;
}

/**
 * Return the machines whose account, by the last read of its quota for the sport they book in
 * `month`, has fewer bookings left than their slots: the app refuses the ones over.
 */
export function shortOfQuota(
  settings: Settings,
  machines: readonly Machine[],
  customers: readonly Customer[],
  month: string,
): Short[] {
  return enabledMachines(machines).flatMap(({ place, mumuIndex, entry }) => {
    const booking = entry === null ? undefined : [settings, ...settings.instances][entry];
    const attached = mumuIndex === null ? null : accountOn(customers, mumuIndex);
    const reading = attached?.account.quota.find(
      (read) => read.month === month && read.sport === booking?.sport,
    );
    if (booking === undefined || reading === undefined) {
      return [];
    }
    const left = leftOf(reading);
    const slots = booking.slots.length;
    return left < slots && attached !== null
      ? [{ place, left, slots, customer: attached.customer.id }]
      : [];
  });
}

/** Read what to look at before the next start; nothing until it is known. */
export function useReadiness(): { accountless: Machine[]; clashing: Clash[]; short: Short[] } {
  const machines = useMachines();
  const customers = useCustomers().data;
  const settings = useSettings().data;
  const month = useBookingMonth();
  return useMemo(
    () => ({
      accountless: withoutAccount(machines, customers ?? []),
      clashing: settings === undefined ? [] : clashes(settings, machines),
      short:
        settings === undefined || month === undefined
          ? []
          : shortOfQuota(settings, machines, customers ?? [], month),
    }),
    [machines, customers, settings, month],
  );
}
