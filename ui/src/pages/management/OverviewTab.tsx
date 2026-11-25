import { useTranslation } from "react-i18next";
import { Link } from "react-router";
import { useTickets } from "../../api/queries";
import { Icon } from "../../components/Icon";
import { PageTitle } from "../../components/PageTitle";
import { Loading } from "../../components/States";
import { useFormat } from "../../useFormat";
import { type Alert, useAlerts } from "./board";
import styles from "./Board.module.css";
import { type MachineFacts, runWhen, useMachineFacts } from "./machineFacts";
import { RunSlots } from "./RunSlots";

/** What to look at, what keeps a machine from booking first; nothing while all is well. */
function Alerts({ alerts }: { alerts: Alert[] }) {
  const { t } = useTranslation();
  const sorted = [...alerts].sort((a, b) => (a.level === b.level ? 0 : a.level === "bad" ? -1 : 1));
  return (
    <section aria-labelledby="board-alerts" className={styles.card}>
      <h2 id="board-alerts" className={styles.sectionTitle}>
        {t("pages.board.alertsTitle")}
      </h2>
      <ul className={styles.alerts}>
        {sorted.map((alert) => (
          <li key={alert.text} className={styles.alert}>
            <Icon name="alarm" />
            <Link to={alert.to}>{alert.text}</Link>
          </li>
        ))}
      </ul>
    </section>
  );
}

/** Each machine in a line: the account it books with, what it books, how its last run went. */
function Machines({ facts }: { facts: MachineFacts[] }) {
  const { t } = useTranslation();
  const f = useFormat();
  // The day of the newest 06:00 run of any machine.
  const latest = facts
    .map(({ lastRun }) => lastRun?.started_at)
    .filter((started) => started !== undefined)
    .sort()
    .at(-1);
  return (
    <section aria-labelledby="board-machines" className={styles.card}>
      <div className={styles.cardHead}>
        <h2 id="board-machines" className={`${styles.sectionTitle} ${styles.value}`}>
          {t("pages.board.machinesTitle")}
        </h2>
        {latest !== undefined && (
          <span className={styles.muted}>
            {t("pages.board.latestRun", { day: f.shortDay(latest.slice(0, 10)) })}
          </span>
        )}
      </div>
      <table className={styles.table}>
        <thead>
          <tr>
            <th>{t("pages.board.machine")}</th>
            <th>{t("pages.board.account")}</th>
            <th>{t("pages.board.books")}</th>
            <th>{t("pages.board.last")}</th>
          </tr>
        </thead>
        <tbody>
          {facts.map(({ machine, booking, attached, lastRun }) => (
            <tr key={machine.place}>
              <td>{t("pages.ticket.instanceName", { number: machine.place + 1 })}</td>
              <td>
                {attached === null ? (
                  <span className={styles.muted}>–</span>
                ) : (
                  <>
                    {attached.account.label || attached.customer.name}
                    <br />
                    <span className={`${styles.muted} ${styles.mono}`}>
                      {attached.account.phone ?? ""}
                    </span>
                  </>
                )}
              </td>
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

/**
 * The management's first board: what to look at, while there is something, then every machine in
 * a line with the account it books with and its last 06:00 run.
 */
export function OverviewTab() {
  const { t } = useTranslation();
  const facts = useMachineFacts();
  const tickets = useTickets();
  const alerts = useAlerts(facts, tickets.data ?? []);
  return (
    <>
      <PageTitle>{t("pages.board.title")}</PageTitle>
      <div className={styles.page}>
        {facts === undefined ? (
          <Loading />
        ) : (
          <>
            {alerts.length > 0 && <Alerts alerts={alerts} />}
            <Machines facts={facts} />
          </>
        )}
      </div>
    </>
  );
}
