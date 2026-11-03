import { addMinutes } from "./format";

/** No dry run or auto setup may start until this long after the start (lock.py SCHEDULE_AFTER). */
const AFTER_START_MINUTES = 5;

/** Return when the quiet time before and after a booking ends: the start time + 5 minutes. */
export function quietEnd(start: string): string {
  return addMinutes(start, AFTER_START_MINUTES);
}

/** Return "HH:MM" of `now`, on this PC's clock like the schedule's times. */
function clock(now: Date): string {
  return `${String(now.getHours()).padStart(2, "0")}:${String(now.getMinutes()).padStart(2, "0")}`;
}

/** Tell whether `now` falls in the quiet time, from the wake time to the start + 5 minutes. */
export function inQuietTime(now: Date, wake: string, start: string): boolean {
  const time = clock(now);
  return wake <= time && time < quietEnd(start);
}
