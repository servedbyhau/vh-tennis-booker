import { useTranslation } from "react-i18next";
import type { Ticket } from "../../api/types";
import { localToday } from "../../format";
import { ticketCustomer } from "../../tickets";
import { useFormat } from "../../useFormat";
import { addDays } from "./board";
import styles from "./TicketsTab.module.css";

/** The days a week shows: today and the six after it. */
const WEEK_DAYS = 7;

interface TicketWeekProps {
  tickets: readonly Ticket[];
  onOpen: (code: string) => void;
}

/**
 * The tickets of this week in a grid: a column a day, a row a slot, each ticket a button that
 * opens its picture; a ticket not yet sent to its customer is marked.
 */
export function TicketWeek({ tickets, onOpen }: TicketWeekProps) {
  const { t } = useTranslation();
  const f = useFormat();
  const today = localToday();
  const days = Array.from({ length: WEEK_DAYS }, (_, index) => addDays(today, index));
  const slots = [...new Set(tickets.map((ticket) => ticket.slot))].sort();
  if (slots.length === 0) {
    return <span className={styles.none}>{t("pages.tickets.noneKept")}</span>;
  }
  return (
    <table className={styles.week}>
      <thead>
        <tr>
          <th scope="col" className={styles.weekSlot}>
            <span className="visually-hidden">{t("pages.tickets.slot")}</span>
          </th>
          {days.map((day) => (
            <th key={day} scope="col">
              {f.shortDay(day)}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {slots.map((slot) => (
          <tr key={slot}>
            <th scope="row" className={styles.weekSlot}>
              {f.slot(slot)}
            </th>
            {days.map((day) => (
              <td key={day}>
                {tickets
                  .filter((ticket) => ticket.play_date === day && ticket.slot === slot)
                  .map((ticket) => (
                    <button
                      key={ticket.code}
                      type="button"
                      className={
                        ticket.sent_at === null
                          ? `${styles.cell} ${styles.cellUnsent}`
                          : styles.cell
                      }
                      title={t(
                        ticket.sent_at === null ? "pages.tickets.unsent" : "pages.tickets.sentMark",
                      )}
                      onClick={() => onOpen(ticket.code)}
                    >
                      <span className={styles.cellCourt}>{f.court(ticket.court)}</span>
                      <span className={styles.cellWho}>
                        {ticketCustomer(ticket) || t("pages.tickets.unknown")}
                      </span>
                    </button>
                  ))}
              </td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  );
}
