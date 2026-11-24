import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { errorMessage } from "../../api/errors";
import { useCancelTicket } from "../../api/mutations";
import { queryKeys, useCancelState } from "../../api/queries";
import type { Ticket } from "../../api/types";
import { localToday, slotStart } from "../../format";

/** The exit codes of `court-booker cancel` that have words of their own. */
const FAILURES = ["1", "2", "3", "4", "5"] as const;

/**
 * Tell whether `ticket` may still be cancelled: booked or being booked, and its slot not begun
 * (`now` is this PC's time). Only the day of play is listed until it is over.
 */
export function cancellable(ticket: Ticket, now: Date = new Date()): boolean {
  if (ticket.status !== "registered" && ticket.status !== "processing") {
    return false;
  }
  const today = localToday(now);
  if (ticket.play_date !== today) {
    return ticket.play_date > today;
  }
  const time = `${String(now.getHours()).padStart(2, "0")}:${String(now.getMinutes()).padStart(2, "0")}`;
  return slotStart(ticket.slot) > time;
}

/** The cancel of `code`: asked, going on, or how it ended once started from here. */
export type CancelPhase =
  | { kind: "idle" }
  | { kind: "asking" }
  | { kind: "running" }
  | { kind: "done" }
  | { kind: "failed"; text: string };

/**
 * The cancel of the ticket shown (none while there is none) in the app: the question first, then
 * how it goes (about a minute, read every 2 s) and how it ended. Once over, the customers' quotas
 * are read again at once, the tickets when its words are put away or the dialog shuts: a cancelled
 * ticket leaves the list, and the dialog with it.
 */
export function useTicketCancel(ticket: Ticket | undefined) {
  const { t } = useTranslation();
  const cache = useQueryClient();
  const state = useCancelState();
  const start = useCancelTicket();
  const [asking, setAsking] = useState<string | null>(null);
  const code = ticket?.code;
  const mine = code !== undefined && state.data?.code === code ? state.data : undefined;
  const started = code !== undefined && start.data?.code === code;
  const ended = started && mine !== undefined && !mine.running;

  useEffect(() => {
    if (ended) {
      void cache.invalidateQueries({ queryKey: queryKeys.customers });
      void cache.invalidateQueries({ queryKey: queryKeys.overview });
      // Shut while its words show: the list is read again then.
      return () => void cache.invalidateQueries({ queryKey: queryKeys.tickets });
    }
    return undefined;
  }, [ended, cache]);

  let phase: CancelPhase = { kind: "idle" };
  if (start.isError && start.variables === code) {
    phase = { kind: "failed", text: errorMessage(t, start.error) };
  } else if (mine?.running === true || (start.isPending && start.variables === code)) {
    phase = { kind: "running" };
  } else if (ended) {
    const exit = String(mine.exit_code);
    phase =
      mine.exit_code === 0
        ? { kind: "done" }
        : {
            kind: "failed",
            text: t(
              `pages.tickets.cancel.failed.${FAILURES.find((known) => known === exit) ?? "other"}`,
            ),
          };
  } else if (asking !== null && asking === code) {
    phase = { kind: "asking" };
  }

  return {
    phase,
    ask: () => {
      start.reset();
      setAsking(code ?? null);
    },
    confirm: () => {
      setAsking(null);
      if (code !== undefined) {
        start.mutate(code);
      }
    },
    dismiss: () => {
      setAsking(null);
      start.reset();
    },
  };
}
