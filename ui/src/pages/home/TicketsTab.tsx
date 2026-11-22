import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useTickets } from "../../api/queries";
import type { Ticket } from "../../api/types";
import { Icon } from "../../components/Icon";
import { QueryView } from "../../components/QueryView";
import { localToday } from "../../format";
import { useMachines } from "../../machines";
import { ticketDays, ticketDevices, ticketsToUse } from "../../tickets";
import { useFormat } from "../../useFormat";
import { TicketDialog } from "./TicketDialog";
import { TicketStamp } from "./TicketStamp";
import styles from "./TicketsTab.module.css";
import { machineName } from "./ticketText";

interface MachineFilterProps {
  /** The machines with tickets. */
  devices: readonly number[];
  /** The MuMu instance whose tickets show, `null` for every machine's. */
  device: number | null;
  onDevice: (device: number | null) => void;
}

/** Whose tickets to list. */
function MachineFilter({ devices, device, onDevice }: MachineFilterProps) {
  const { t } = useTranslation();
  const machines = useMachines();
  return (
    <div role="group" aria-label={t("pages.tickets.machine")} className={styles.chips}>
      {[null, ...devices].map((choice) => (
        <button
          key={choice ?? "all"}
          type="button"
          aria-pressed={device === choice}
          className={styles.chip}
          onClick={() => onDevice(choice)}
        >
          {choice === null ? t("pages.tickets.all") : machineName(t, machines, choice)}
        </button>
      ))}
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
  /** The tickets still to use. */
  tickets: Ticket[];
  device: number | null;
  onDevice: (device: number | null) => void;
}

/** The tickets of one machine or all, day by day, and the one opened over them. */
function TicketList({ tickets, device, onDevice }: TicketListProps) {
  const { t } = useTranslation();
  const f = useFormat();
  const [openCode, setOpenCode] = useState<string | null>(null);
  const devices = ticketDevices(tickets);
  // A machine chosen before its last ticket went: every machine's.
  const chosen = device !== null && devices.includes(device) ? device : null;
  const days = ticketDays(tickets.filter((ticket) => chosen === null || ticket.device === chosen));
  const shown = days.flatMap((day) => day.tickets);
  const open = shown.findIndex((ticket) => ticket.code === openCode);
  return (
    <>
      {devices.length > 1 && (
        <MachineFilter devices={devices} device={chosen} onDevice={onDevice} />
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

interface TicketsTabProps {
  /** The MuMu instance whose tickets to list, `null` for every machine's. */
  device: number | null;
  onDevice: (device: number | null) => void;
}

/**
 * The tickets booked and still to use, of every machine's account, as the runs read them in the
 * Vinhomes app: by day of play until that day is over, each opening its picture to send. Nothing
 * here asks the app again or changes a ticket.
 */
export function TicketsTab({ device, onDevice }: TicketsTabProps) {
  const { t } = useTranslation();
  const tickets = useTickets();
  const today = localToday();
  return (
    <QueryView
      query={tickets}
      isEmpty={(list) => ticketsToUse(list, today).length === 0}
      empty={<span className={styles.none}>{t("pages.tickets.empty")}</span>}
    >
      {(list) => (
        <TicketList tickets={ticketsToUse(list, today)} device={device} onDevice={onDevice} />
      )}
    </QueryView>
  );
}
