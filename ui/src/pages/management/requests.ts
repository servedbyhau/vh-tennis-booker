/** A request applied to a machine's settings, apart from how it shows (RequestsTab). */
import type { RequestFields, Settings } from "../../api/types";

/** Return `settings` with machine `mumuIndex` booking what `request` asks. */
export function appliedTo(settings: Settings, mumuIndex: number, request: RequestFields): Settings {
  const booking = {
    subdivision: request.subdivision,
    sport: request.sport,
    court: request.court,
    slots: [...request.slots],
    days: [...(request.days ?? [])],
  };
  if (mumuIndex === settings.mumu_index) {
    return { ...settings, ...booking };
  }
  return {
    ...settings,
    instances: settings.instances.map((instance) =>
      instance.mumu_index === mumuIndex ? { ...instance, ...booking } : instance,
    ),
  };
}

/** The words of each day of the week, Monday first, as the language files key them. */
const DAY_KEYS = ["days.0", "days.1", "days.2", "days.3", "days.4", "days.5", "days.6"] as const;

/** Return the key of the words of `day` (0 Monday to 6 Sunday). */
export function dayKey(day: number) {
  return DAY_KEYS[day] ?? "days.every";
}
