/**
 * What the tickets list shows: the tickets still to use, in days. The backend gives every
 * machine's tickets in one list; picking among them sends no request.
 */
import type { Ticket } from "./api/types";

/** The tickets of one day of play, by slot and then by machine. */
export interface TicketDay {
  day: string;
  tickets: Ticket[];
}

/** Return the machines that have tickets, by their MuMu index. */
export function ticketDevices(tickets: readonly Ticket[]): number[] {
  return [...new Set(tickets.map((ticket) => ticket.device))].sort((a, b) => a - b);
}

/** Return the tickets still to use on `today` ("2026-10-15"): its own too, no cancelled one. */
export function ticketsToUse(tickets: readonly Ticket[], today: string): Ticket[] {
  return tickets.filter((ticket) => ticket.play_date >= today && ticket.status !== "cancelled");
}

/** Group tickets by day of play, the next day first. */
export function ticketDays(tickets: readonly Ticket[]): TicketDay[] {
  const days = new Map<string, Ticket[]>();
  for (const ticket of tickets) {
    days.set(ticket.play_date, [...(days.get(ticket.play_date) ?? []), ticket]);
  }
  return [...days]
    .sort(([a], [b]) => (a < b ? -1 : 1))
    .map(([day, list]) => ({
      day,
      tickets: list.sort(
        (a, b) =>
          a.slot.localeCompare(b.slot) ||
          a.device - b.device ||
          // A slot booked again: the newer ticket first.
          b.code.localeCompare(a.code),
      ),
    }));
}

/** Return where a ticket's picture is; `seen_at` makes a picture taken again load again. */
export function photoUrl(ticket: Pick<Ticket, "code" | "seen_at">): string {
  return `/api/tickets/${ticket.code}/photo?seen=${encodeURIComponent(ticket.seen_at)}`;
}

/** Characters Windows allows in no file name. */
const NOT_IN_FILE_NAMES = /[\\/:*?"<>|]/g;

/**
 * Name the file a ticket's picture is saved as, `court` as the list shows it: the day first, so
 * saved tickets sort by day ("2026-10-16 18h00-19h00 Tennis S6 1234567.png").
 */
export function photoFileName(
  ticket: Pick<Ticket, "code" | "play_date" | "slot">,
  court: string,
): string {
  const slot = ticket.slot.replaceAll(" ", "").replaceAll(":", "h");
  const name = [ticket.play_date, slot, court, ticket.code].join(" ");
  return `${name.replace(NOT_IN_FILE_NAMES, "")}.png`;
}
