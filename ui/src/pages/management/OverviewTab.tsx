import { useTranslation } from "react-i18next";
import { Link } from "react-router";
import { useRuns, useTickets } from "../../api/queries";
import type { Ticket } from "../../api/types";
import { Icon, type IconName } from "../../components/Icon";
import { PageTitle } from "../../components/PageTitle";
import { Loading } from "../../components/States";
import { localToday } from "../../format";
import { paths } from "../../paths";
import { ticketCustomer, ticketsToUse } from "../../tickets";
import { useFormat } from "../../useFormat";
import { type Alert, addDays, bookedOf, useAlerts } from "./board";
import styles from "./Board.module.css";
import { type MachineFacts, runWhen, useMachineFacts } from "./machineFacts";
import { RunSlots } from "./RunSlots";

/** How many days of tickets to play the board lists. */
const UPCOMING_DAYS = 3;
/** The numbers at the top: this month's slots booked, tickets to play, machines on. */
function Figures({ facts, tickets }: { facts: MachineFacts[]; tickets: Ticket[] }) {
  const { t } = useTranslation();
  const month = localToday().slice(0, 7);
  const runs = useRuns({ month, dry_run: false, limit: 500 });
  const { booked, tried } = bookedOf(runs.data ?? []);
  const rate = tried === 0 ? null : Math.round((booked / tried) * 100);
  const figures: [string, string][] = [
    [rate === null ? "–" : `${booked}/${tried}`, t("pages.board.booked", { rate: rate ?? 0 })],
    [String(tickets.length), t("pages.board.toPlay")],
    [
      `${facts.filter((item) => item.booking !== undefined).length}/${facts.length}`,
      t("pages.board.machinesOn"),
    ],
  ];
  return (
    <div className={styles.figures}>
      {figures.map(([value, label]) => (
        <div key={label} className={styles.figure}>
          <span className={styles.figureValue}>{value}</span>
          <span className={styles.figureLabel}>{label}</span>
        </div>
      ))}
    </div>
  );
}

const LEVEL_ICONS: Record<Alert["level"], IconName> = { bad: "close", warn: "alarm" };

/** What to look at, the most urgent first; a line that all is well when nothing is. */
function Alerts({ alerts }: { alerts: Alert[] }) {
  const { t } = useTranslation();
  const sorted = [...alerts].sort((a, b) => (a.level === b.level ? 0 : a.level === "bad" ? -1 : 1));
  return (
    <section aria-labelledby="board-alerts" className={styles.card}>
      <h2 id="board-alerts" className={styles.sectionTitle}>
        {t("pages.board.alertsTitle")}
      </h2>
      {sorted.length === 0 ? (
        <p className={`${styles.alert} ${styles.good}`}>
          <Icon name="check" />
          {t("pages.board.allWell")}
        </p>
      ) : (
        <ul className={styles.alerts}>
          {sorted.map((alert) => (
            <li
              key={alert.text}
              className={`${styles.alert} ${alert.level === "bad" ? styles.alertBad : styles.alertWarn}`}
            >
              <Icon name={LEVEL_ICONS[alert.level]} />
              <Link to={alert.to}>{alert.text}</Link>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

/** Each machine in a line: whose it is, what it books and how its last booking went. */
function Machines({ facts }: { facts: MachineFacts[] }) {
  const { t } = useTranslation();
  const f = useFormat();
  return (
    <section aria-labelledby="board-machines" className={styles.card}>
      <div className={styles.cardHead}>
        <h2 id="board-machines" className={`${styles.sectionTitle} ${styles.value}`}>
          {t("pages.board.machinesTitle")}
        </h2>
        <Link to={paths.machines} className={styles.muted}>
          {t("pages.board.seeAll")}
        </Link>
      </div>
      <table className={styles.table}>
        <thead>
          <tr>
            <th>{t("pages.board.machine")}</th>
            <th>{t("pages.board.customer")}</th>
            <th>{t("pages.board.books")}</th>
            <th>{t("pages.board.last")}</th>
          </tr>
        </thead>
        <tbody>
          {facts.map(({ machine, booking, attached, lastRun }) => (
            <tr key={machine.place}>
              <td>{t("pages.ticket.instanceName", { number: machine.place + 1 })}</td>
              <td>{attached?.customer.name ?? <span className={styles.muted}>–</span>}</td>
              <td>
                {booking === undefined ? (
                  <span className={styles.muted}>{t("pages.machines.off")}</span>
                ) : (
                  <>
                    {f.court(booking.court)}{" "}
                    <span className={styles.muted}>
                      {booking.slots.map((slot) => f.slot(slot)).join(", ")}
                    </span>
                  </>
                )}
              </td>
              <td>
                {lastRun === undefined ? (
                  <span className={styles.muted}>–</span>
                ) : (
                  <span title={runWhen(t, f, lastRun)}>
                    <RunSlots run={lastRun} />
                  </span>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}

/** The tickets of the next days, by day, each with whose it is. */
function Upcoming({ tickets }: { tickets: Ticket[] }) {
  const { t } = useTranslation();
  const f = useFormat();
  const today = localToday();
  const days = Array.from({ length: UPCOMING_DAYS }, (_, index) => addDays(today, index));
  return (
    <section aria-labelledby="board-upcoming" className={styles.card}>
      <div className={styles.cardHead}>
        <h2 id="board-upcoming" className={`${styles.sectionTitle} ${styles.value}`}>
          {t("pages.board.upcomingTitle")}
        </h2>
        <Link to={paths.tickets} className={styles.muted}>
          {t("pages.board.seeAll")}
        </Link>
      </div>
      {days.map((day) => {
        const list = tickets.filter((ticket) => ticket.play_date === day);
        return (
          <div key={day}>
            <p className={styles.muted}>
              {f.day(day)} · {t("pages.tickets.count", { count: list.length })}
            </p>
            <ul className={styles.lines}>
              {list.map((ticket) => (
                <li key={ticket.code} className={styles.line}>
                  <span className={styles.chip}>{f.slot(ticket.slot)}</span>
                  <span className={styles.value}>{f.court(ticket.court)}</span>
                  <span className={styles.muted}>
                    {ticketCustomer(ticket) || t("pages.tickets.unknown")}
                  </span>
                </li>
              ))}
            </ul>
          </div>
        );
      })}
    </section>
  );
}

/**
 * The management's first board: this month's figures, what to look at, every machine in a line
 * and the tickets of the next days. Each part leads to the section that holds more.
 */
export function OverviewTab() {
  const { t } = useTranslation();
  const facts = useMachineFacts();
  const tickets = useTickets();
  const alerts = useAlerts(facts, tickets.data ?? []);
  const toPlay = ticketsToUse(tickets.data ?? [], localToday());
  return (
    <>
      <PageTitle>{t("pages.board.title")}</PageTitle>
      <div className={styles.page}>
        {facts === undefined ? (
          <Loading />
        ) : (
          <>
            <Figures facts={facts} tickets={toPlay} />
            <div className={styles.wide}>
              <div className={styles.column}>
                <Machines facts={facts} />
                <Upcoming tickets={toPlay} />
              </div>
              <Alerts alerts={alerts} />
            </div>
          </>
        )}
      </div>
    </>
  );
}
