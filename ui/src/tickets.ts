/**
 * What the tickets list shows: the tickets of one period, of one machine or all, in days.
 * The backend gives every machine's tickets in one list; picking among them sends no request.
 */
import type { Ticket } from "./api/types";

/** Which tickets to list: those still to play (today's too), or those before today. */
export type Period = "upcoming" | "past";

export interface TicketFilter {
  period: Period;
  /** The MuMu instance whose tickets to list, `null` for every machine's. */
  device: number | null;
  /** Whether cancelled tickets are listed too. */
  withCancelled: boolean;
}

/** The tickets of one day of play, by slot and then by machine. */
export interface TicketDay {
  day: string;
  tickets: Ticket[];
}

/** Return the machines that have tickets, by their MuMu index. */
export function ticketDevices(tickets: readonly Ticket[]): number[] {
  return [...new Set(tickets.map((ticket) => ticket.device))].sort((a, b) => a - b);
}

/** Return the tickets `filter` keeps on `today` ("2026-10-15"). */
export function pickTickets(
  tickets: readonly Ticket[],
  filter: TicketFilter,
  today: string,
): Ticket[] {
  return tickets.filter(
    (ticket) =>
      ticket.play_date >= today === (filter.period === "upcoming") &&
      (filter.device === null || ticket.device === filter.device) &&
      (filter.withCancelled || ticket.status !== "cancelled"),
  );
}

/** Group tickets by day of play: the next day first when upcoming, the last one when past. */
export function ticketDays(tickets: readonly Ticket[], period: Period): TicketDay[] {
  const days = new Map<string, Ticket[]>();
  for (const ticket of tickets) {
    days.set(ticket.play_date, [...(days.get(ticket.play_date) ?? []), ticket]);
  }
  const order = period === "upcoming" ? 1 : -1;
  return [...days]
    .sort(([a], [b]) => (a < b ? -order : order))
    .map(([day, list]) => ({
      day,
      tickets: list.sort(
        (a, b) =>
          a.slot.localeCompare(b.slot) ||
          a.device - b.device ||
          // A slot booked again after a cancel: the newer ticket first.
          b.code.localeCompare(a.code),
      ),
    }));
}

/** Return where a ticket's picture is; `seen_at` makes a picture taken again load again. */
export function photoUrl(ticket: Pick<Ticket, "code" | "seen_at">): string {
  return `/api/tickets/${ticket.code}/photo?seen=${encodeURIComponent(ticket.seen_at)}`;
}
