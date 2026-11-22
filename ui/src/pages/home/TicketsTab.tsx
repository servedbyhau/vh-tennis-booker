import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useTickets } from "../../api/queries";
import type { Ticket } from "../../api/types";
import { Icon } from "../../components/Icon";
import { QueryView } from "../../components/QueryView";
import { EmptyState } from "../../components/States";
import { localToday } from "../../format";
import { useMachines } from "../../machines";
import {
  type Period,
  pickTickets,
  ticketDays,
  ticketDevices,
  type TicketFilter,
} from "../../tickets";
import { useFormat } from "../../useFormat";
import { TicketDialog } from "./TicketDialog";
import { TicketStamp } from "./TicketStamp";
import styles from "./TicketsTab.module.css";
import { machineName } from "./ticketText";

const PERIODS: readonly Period[] = ["upcoming", "past"];

interface FilterBarProps {
  filter: TicketFilter;
  /** The machines with tickets; one alone has nothing to choose. */
  devices: readonly number[];
  onFilter: (filter: TicketFilter) => void;
}

/** What to list: the tickets still to play or those past, of which machine, cancelled or not. */
function FilterBar({ filter, devices, onFilter }: FilterBarProps) {
  const { t } = useTranslation();
  const machines = useMachines();
  return (
    <div className={styles.toolbar}>
      <div role="group" aria-label={t("pages.tickets.period")} className={styles.chips}>
        {PERIODS.map((period) => (
          <button
            key={period}
            type="button"
            aria-pressed={filter.period === period}
            className={styles.chip}
            onClick={() => onFilter({ ...filter, period })}
          >
            {t(`pages.tickets.${period}`)}
          </button>
        ))}
      </div>
      {devices.length > 1 && (
        <div role="group" aria-label={t("pages.tickets.machine")} className={styles.chips}>
          {[null, ...devices].map((device) => (
            <button
              key={device ?? "all"}
              type="button"
              aria-pressed={filter.device === device}
              className={styles.chip}
              onClick={() => onFilter({ ...filter, device })}
            >
              {device === null ? t("pages.tickets.all") : machineName(t, machines, device)}
            </button>
          ))}
        </div>
      )}
      <label className={styles.check}>
        <input
          type="checkbox"
          checked={filter.withCancelled}
          onChange={(event) => onFilter({ ...filter, withCancelled: event.target.checked })}
        />
        {t("pages.tickets.withCancelled")}
      </label>
    </div>
  );
}

/** One ticket in two lines: its slot, court and status, then its machine, code and picture. */
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
          <span>
            {t("pages.tickets.where", {
              machine: machineName(t, machines, ticket.device),
              code: ticket.code,
            })}
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
  tickets: Ticket[];
  filter: TicketFilter;
  onFilter: (filter: TicketFilter) => void;
}

/** The tickets the filter keeps, day by day, and the one opened over them. */
function TicketList({ tickets, filter, onFilter }: TicketListProps) {
  const { t } = useTranslation();
  const f = useFormat();
  const [openCode, setOpenCode] = useState<string | null>(null);
  const days = ticketDays(pickTickets(tickets, filter, localToday()), filter.period);
  const shown = days.flatMap((day) => day.tickets);
  const open = shown.findIndex((ticket) => ticket.code === openCode);
  return (
    <>
      <FilterBar filter={filter} devices={ticketDevices(tickets)} onFilter={onFilter} />
      <div className={styles.scroll}>
        {days.length === 0 && <EmptyState>{t(`pages.tickets.empty.${filter.period}`)}</EmptyState>}
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

interface TicketsTabProps {
  filter: TicketFilter;
  onFilter: (filter: TicketFilter) => void;
}

/**
 * The tickets of every machine's account, as the runs read them in the Vinhomes app: by day
 * of play, each opening its picture. Nothing here asks the app again or changes a ticket.
 */
export function TicketsTab({ filter, onFilter }: TicketsTabProps) {
  const { t } = useTranslation();
  const tickets = useTickets();
  return (
    <QueryView
      query={tickets}
      isEmpty={(list) => list.length === 0}
      empty={<span className={styles.none}>{t("pages.tickets.empty.none")}</span>}
    >
      {(list) => <TicketList tickets={list} filter={filter} onFilter={onFilter} />}
    </QueryView>
  );
}
