import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useTickets } from "../../api/queries";
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

/**
 * One ticket in two lines: its slot, court and status, then whose it is (the machine, while that is
 * not known) and its picture.
 */
function TicketRow({ ticket, onOpen }: { ticket: Ticket; onOpen: () => void }) {
  const { t } = useTranslation();
  const f = useFormat();
  const machines = useMachines();
  return (
    <li className={styles.item}>
      <button type="button" className={styles.row} onClick={onOpen}>
        <span className={styles.head}>
          <span className={styles.title}>
            {t("pages.tickets.row", { slot: f.slot(ticket.slot), court: f.court(ticket.court) })}
          </span>
          <TicketStamp ticket={ticket} />
        </span>
        <span className={styles.line}>
          <span className={styles.holder} title={holderText(ticket) ?? undefined}>
            <span className={styles.customer}>
              {ticket.customer ?? machineName(t, machines, ticket.device)}
            </span>
            {ticket.account !== null && <span className={styles.account}>{ticket.account}</span>}
          </span>
          <span className={ticket.has_photo ? styles.photo : undefined}>
            {ticket.has_photo && <Icon name="picture" />}
            {t(ticket.has_photo ? "pages.tickets.view" : "pages.tickets.noPhoto")}
          </span>
        </span>
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

/** The tickets of one customer or all, day by day, and the one opened over them. */
function TicketList({ tickets, customer, onCustomer }: TicketListProps) {
  const { t } = useTranslation();
  const f = useFormat();
  const [openCode, setOpenCode] = useState<string | null>(null);
  const customers = ticketCustomers(tickets);
  // A customer chosen before their last ticket went: every customer's.
  const chosen = customer !== null && customers.includes(customer) ? customer : null;
  const days = ticketDays(
    tickets.filter((ticket) => chosen === null || ticketCustomer(ticket) === chosen),
  );
  const shown = days.flatMap((day) => day.tickets);
  const open = shown.findIndex((ticket) => ticket.code === openCode);
  return (
    <>
      {customers.length > 1 && (
        <CustomerFilter customers={customers} customer={chosen} onCustomer={onCustomer} />
      )}
      <div className={styles.scroll}>
        {days.map(({ day, tickets: list }) => (
          <section key={day} aria-label={f.day(day)}>
            <h3 className={styles.day}>
              <span>{f.day(day)}</span>
              <span className={styles.count}>
                {t("pages.tickets.count", { count: list.length })}
              </span>
            </h3>
            <ul className={styles.list}>
              {list.map((ticket) => (
                <TicketRow
                  key={ticket.code}
                  ticket={ticket}
                  onOpen={() => setOpenCode(ticket.code)}
                />
              ))}
            </ul>
          </section>
        ))}
      </div>
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
