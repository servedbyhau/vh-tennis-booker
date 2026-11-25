import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useMarkSent } from "../../api/mutations";
import { useTickets } from "../../api/queries";
import { sportName } from "../../quota";
import type { Ticket } from "../../api/types";
import { Icon } from "../../components/Icon";
import { PageTitle } from "../../components/PageTitle";
import { QueryView } from "../../components/QueryView";
import { localToday } from "../../format";
import { useMachines } from "../../machines";
import { ticketCustomer, ticketCustomers, ticketDays, ticketsToUse, UNKNOWN } from "../../tickets";
import { useFormat } from "../../useFormat";
import { TicketDialog } from "./TicketDialog";
import { TicketStamp } from "./TicketStamp";
import { TicketWeek } from "./TicketWeek";
import styles from "./TicketsTab.module.css";
import { useManagement } from "./state";
import { holderText, machineName } from "../home/ticketText";

interface CustomerFilterProps {
  /** The customers with tickets. */
  customers: readonly string[];
  /** The customer whose tickets show, `null` for every customer's. */
  customer: string | null;
  onCustomer: (customer: string | null) => void;
}

/** Whose tickets to list. */
function CustomerFilter({ customers, customer, onCustomer }: CustomerFilterProps) {
  const { t } = useTranslation();
  return (
    <div role="group" aria-label={t("pages.tickets.customer")} className={styles.chips}>
      {[null, ...customers].map((choice) => (
        <button
          key={choice ?? "all"}
          type="button"
          aria-pressed={customer === choice}
          className={styles.chip}
          onClick={() => onCustomer(choice)}
        >
          {choice === null
            ? t("pages.tickets.all")
            : choice === UNKNOWN
              ? t("pages.tickets.unknown")
              : choice}
        </button>
      ))}
    </div>
  );
}

interface TicketRowProps {
  ticket: Ticket;
  /** Whether to name its customer too: several customers' tickets are listed. */
  withCustomer: boolean;
  onOpen: () => void;
}

/**
 * One ticket in two lines, a press opening its picture: its slot and court, a mark while it has
 * a picture, its status unless it is the usual one; then the account it was booked with (the
 * machine, while that is not known). Beside them, whether it was sent to its customer, which a
 * press changes.
 */
function TicketRow({ ticket, withCustomer, onOpen }: TicketRowProps) {
  const { t } = useTranslation();
  const f = useFormat();
  const machines = useMachines();
  const mark = useMarkSent();
  const row = t("pages.tickets.row", { slot: f.slot(ticket.slot), court: f.court(ticket.court) });
  const sent = ticket.sent_at !== null;
  const who = ticket.account ?? ticket.customer ?? machineName(t, machines, ticket.device);
  const customer = withCustomer && ticket.account !== null ? ticket.customer : null;
  return (
    <li className={styles.item}>
      <button
        type="button"
        className={styles.open}
        title={holderText(ticket) ?? undefined}
        onClick={onOpen}
      >
        <span className={styles.head}>
          <span className={styles.title}>{row}</span>
          {ticket.has_photo && (
            <span className={styles.photo}>
              <Icon name="picture" />
              <span className="visually-hidden">{t("pages.tickets.open")}</span>
            </span>
          )}
          {ticket.status !== "registered" && <TicketStamp ticket={ticket} />}
        </span>
        <span className={styles.who}>
          {who}
          {customer !== null && ` · ${customer}`}
        </span>
      </button>
      <button
        type="button"
        aria-pressed={sent}
        aria-label={t("pages.tickets.sentFor", { row })}
        className={sent ? `${styles.sent} ${styles.isSent}` : styles.sent}
        disabled={mark.isPending}
        onClick={() => mark.mutate({ code: ticket.code, sent: !sent })}
      >
        {sent && <Icon name="check" />}
        {t(sent ? "pages.tickets.sentButton" : "pages.tickets.unsentButton")}
      </button>
    </li>
  );
}

interface TicketListProps {
  /** The tickets still to use. */
  tickets: Ticket[];
  customer: string | null;
  onCustomer: (customer: string | null) => void;
}

/** Return how many of `tickets` were not sent to their customer yet. */
function unsentOf(tickets: readonly Ticket[]): number {
  return tickets.filter((ticket) => ticket.sent_at === null).length;
}

/** The sports of `tickets`, as their utilities name them, each once. */
function ticketSports(tickets: readonly Ticket[]): string[] {
  return [...new Set(tickets.map((ticket) => ticket.sport ?? ""))].filter(Boolean);
}

interface ViewBarProps {
  week: boolean;
  onWeek: (week: boolean) => void;
  sports: readonly string[];
  sport: string | null;
  onSport: (sport: string | null) => void;
  unsentOnly: boolean;
  onUnsentOnly: (unsent: boolean) => void;
}

/** How the tickets show: as a list or a week, of one sport or all, every one or those not sent. */
function ViewBar(props: ViewBarProps) {
  const { week, onWeek, sports, sport, onSport, unsentOnly, onUnsentOnly } = props;
  const { t } = useTranslation();
  return (
    <div className={styles.chips}>
      <div role="group" aria-label={t("pages.tickets.view.label")} className={styles.group}>
        {[false, true].map((choice) => (
          <button
            key={String(choice)}
            type="button"
            aria-pressed={week === choice}
            className={styles.chip}
            onClick={() => onWeek(choice)}
          >
            {t(choice ? "pages.tickets.view.week" : "pages.tickets.view.list")}
          </button>
        ))}
      </div>
      {sports.length > 1 && (
        <div role="group" aria-label={t("pages.tickets.sport")} className={styles.group}>
          {[null, ...sports].map((choice) => (
            <button
              key={choice ?? "all"}
              type="button"
              aria-pressed={sport === choice}
              className={styles.chip}
              onClick={() => onSport(choice)}
            >
              {choice === null ? t("pages.tickets.allSports") : sportName(t, choice, choice)}
            </button>
          ))}
        </div>
      )}
      <button
        type="button"
        aria-pressed={unsentOnly}
        className={styles.chip}
        onClick={() => onUnsentOnly(!unsentOnly)}
      >
        {t("pages.tickets.unsentOnly")}
      </button>
    </div>
  );
}

/** The tickets of one customer or all, day by day or in a week, and the one opened over them. */
function TicketList({ tickets, customer, onCustomer }: TicketListProps) {
  const { t } = useTranslation();
  const f = useFormat();
  const [openCode, setOpenCode] = useState<string | null>(null);
  const [week, setWeek] = useState(false);
  const [sport, setSport] = useState<string | null>(null);
  const [unsentOnly, setUnsentOnly] = useState(false);
  const customers = ticketCustomers(tickets);
  const sports = ticketSports(tickets);
  // A customer or sport chosen before their last ticket went: every one's.
  const chosen = customer !== null && customers.includes(customer) ? customer : null;
  const chosenSport = sport !== null && sports.includes(sport) ? sport : null;
  const kept = tickets.filter(
    (ticket) =>
      (chosen === null || ticketCustomer(ticket) === chosen) &&
      (chosenSport === null || ticket.sport === chosenSport) &&
      (!unsentOnly || ticket.sent_at === null),
  );
  const days = ticketDays(kept);
  const shown = days.flatMap((day) => day.tickets);
  const open = shown.findIndex((ticket) => ticket.code === openCode);
  return (
    <>
      {customers.length > 1 && (
        <CustomerFilter customers={customers} customer={chosen} onCustomer={onCustomer} />
      )}
      <ViewBar
        week={week}
        onWeek={setWeek}
        sports={sports}
        sport={chosenSport}
        onSport={setSport}
        unsentOnly={unsentOnly}
        onUnsentOnly={setUnsentOnly}
      />
      {week ? (
        <div className={styles.scroll}>
          <TicketWeek tickets={shown} onOpen={setOpenCode} />
        </div>
      ) : (
        <div className={styles.scroll}>
          {days.map(({ day, tickets: list }) => (
            <section key={day} aria-label={f.day(day)}>
              <h3 className={styles.day}>
                <span>{f.day(day)}</span>
                <span className={styles.count}>
                  {t("pages.tickets.count", { count: list.length })}
                  {unsentOf(list) > 0 &&
                    ` · ${t("pages.tickets.unsentCount", { count: unsentOf(list) })}`}
                </span>
              </h3>
              <ul className={styles.list}>
                {list.map((ticket) => (
                  <TicketRow
                    key={ticket.code}
                    ticket={ticket}
                    withCustomer={customers.length > 1 && chosen === null}
                    onOpen={() => setOpenCode(ticket.code)}
                  />
                ))}
              </ul>
            </section>
          ))}
          {days.length === 0 && <span className={styles.none}>{t("pages.tickets.noneKept")}</span>}
        </div>
      )}
      {open >= 0 && (
        <TicketDialog
          tickets={shown}
          place={open}
          onPlace={(place) => setOpenCode(shown[place]?.code ?? null)}
          onClose={() => setOpenCode(null)}
        />
      )}
    </>
  );
}

/**
 * The tickets booked and still to use, of every customer's accounts, as the runs read them in the
 * Vinhomes app: by day of play until that day is over, each opening its picture to send. Nothing
 * here asks the app again or changes a ticket.
 */
export function TicketsTab() {
  const { t } = useTranslation();
  const { customer, onCustomer } = useManagement();
  const tickets = useTickets();
  const today = localToday();
  return (
    <section aria-label={t("pages.tickets.title")} className={styles.paper}>
      <PageTitle>{t("pages.tickets.title")}</PageTitle>
      <QueryView
        query={tickets}
        isEmpty={(list) => ticketsToUse(list, today).length === 0}
        empty={<span className={styles.none}>{t("pages.tickets.empty")}</span>}
      >
        {(list) => (
          <TicketList
            tickets={ticketsToUse(list, today)}
            customer={customer}
            onCustomer={onCustomer}
          />
        )}
      </QueryView>
    </section>
  );
}
