/**
 * What is left of the accounts' quota, as the runs read it on the Vinhomes app's history page
 * (quota.py): 8 bookings of a sport a month. Only the month the next booking is for counts.
 */
import { useOverview } from "./api/queries";
import type { QuotaReading } from "./api/types";

/** Return "2026-11", the month of a day such as "2026-11-26". */
export function monthOf(day: string): string {
  return day.slice(0, 7);
}

/** Return the reads of `month`; none while it is not known. */
export function readingsOf(
  quota: readonly QuotaReading[],
  month: string | undefined,
): QuotaReading[] {
  return month === undefined ? [] : quota.filter((reading) => reading.month === month);
}

/** Return the bookings a read leaves in its month. */
export function leftOf(reading: QuotaReading): number {
  return Math.max(0, reading.month_limit - reading.used);
}

/** Read the month the next booking is for, once the overview has loaded. */
export function useBookingMonth(): string | undefined {
  const day = useOverview().data?.schedule.next_play_date;
  return day === undefined ? undefined : monthOf(day);
}
