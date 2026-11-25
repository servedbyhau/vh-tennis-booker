/** What the management's first board puts together: what to look at. */
import { useTranslation } from "react-i18next";
import { useOverview } from "../../api/queries";
import type { Ticket } from "../../api/types";
import { localToday } from "../../format";
import { paths } from "../../paths";
import { useReadiness } from "../../readiness";
import type { MachineFacts } from "./machineFacts";

/** One thing to look at; `bad` keeps a machine from booking, and comes first. */
export interface Alert {
  level: "bad" | "warn";
  text: string;
  /** Where it is set right. */
  to: string;
}

/** Return `day` ("2026-11-25") moved by `days`. */
export function addDays(day: string, days: number): string {
  const [year = 0, month = 1, date = 1] = day.split("-").map(Number);
  const moved = new Date(year, month - 1, date + days);
  return localToday(moved);
}

/** Return the tickets of today and tomorrow not yet sent to their customer. */
export function unsentSoon(tickets: readonly Ticket[], today: string): Ticket[] {
  const tomorrow = addDays(today, 1);
  return tickets.filter(
    (ticket) =>
      ticket.sent_at === null &&
      ticket.status !== "cancelled" &&
      ticket.play_date >= today &&
      ticket.play_date <= tomorrow,
  );
}

/**
 * Return what to look at: what keeps a machine from booking, its last run's failure, and the
 * tickets of today and tomorrow not sent to their customer.
 */
export function useAlerts(facts: MachineFacts[] | undefined, tickets: readonly Ticket[]): Alert[] {
  const { t } = useTranslation();
  const overview = useOverview();
  const { accountless, clashing, short } = useReadiness();
  const alerts: Alert[] = [];
  const name = (place: number) => t("pages.ticket.instanceName", { number: place + 1 });
  if (overview.data !== undefined && !overview.data.schedule.enabled) {
    alerts.push({ level: "bad", text: t("pages.board.alerts.scheduleOff"), to: paths.overview });
  }
  for (const machine of accountless) {
    alerts.push({
      level: "bad",
      text: t("pages.board.alerts.noAccount", { machine: name(machine.place) }),
      to: paths.overview,
    });
  }
  for (const clash of clashing) {
    alerts.push({
      level: "warn",
      text: t("pages.board.alerts.clash", {
        machines: clash.places.map((place) => place + 1).join(", "),
      }),
      to: paths.overview,
    });
  }
  for (const item of short) {
    alerts.push({
      level: "warn",
      text: t("pages.board.alerts.short", {
        machine: name(item.place),
        left: item.left,
        slots: item.slots,
      }),
      to: `${paths.quota}?customer=${item.customer}`,
    });
  }
  for (const item of facts ?? []) {
    const run = item.lastRun;
    if (item.booking !== undefined && run !== undefined && run.error !== null) {
      alerts.push({
        level: "bad",
        text: t("pages.board.alerts.failed", { machine: name(item.machine.place) }),
        to: `${paths.history}?run=${run.id}`,
      });
    }
  }
  const unsent = unsentSoon(tickets, localToday());
  if (unsent.length > 0) {
    alerts.push({
      level: "warn",
      text: t("pages.board.alerts.unsent", { count: unsent.length }),
      to: paths.tickets,
    });
  }
  return alerts;
}
