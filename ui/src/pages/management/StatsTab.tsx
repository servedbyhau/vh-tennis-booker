import { useTranslation } from "react-i18next";
import { useRuns, useSettings } from "../../api/queries";
import { PageTitle } from "../../components/PageTitle";
import { Loading } from "../../components/States";
import { localToday } from "../../format";
import { useMachines } from "../../machines";
import { failureReason } from "../../reasons";
import { useFormat } from "../../useFormat";
import { addDays } from "./board";
import styles from "./Board.module.css";
import { averageOf, rateOf, STATS_DAYS, statsOf, type Tally } from "./stats";

/** The most runs read: a month of three machines and more. */
const STATS_RUNS = 500;

/** The share booked as a bar and a number, marked when low. */
function Rate({ item }: { item: Tally }) {
  const rate = rateOf(item);
  if (rate === null) {
    return <span className={styles.muted}>–</span>;
  }
  const tone = rate >= 70 ? styles.good : rate >= 40 ? styles.warn : styles.bad;
  return <span className={`${styles.chip} ${tone}`}>{rate}%</span>;
}

interface TableProps {
  title: string;
  head: string;
  rows: Tally[];
  name: (key: string) => string;
}

/** Tallies in a table: what, tried, booked, the share, the average seconds. */
function TallyTable({ title, head, rows, name }: TableProps) {
  const { t } = useTranslation();
  const f = useFormat();
  return (
    <section aria-label={title} className={styles.card}>
      <h2 className={styles.sectionTitle}>{title}</h2>
      <table className={styles.table}>
        <thead>
          <tr>
            <th>{head}</th>
            <th className={styles.number}>{t("pages.stats.tried")}</th>
            <th className={styles.number}>{t("pages.stats.booked")}</th>
            <th>{t("pages.stats.rate")}</th>
            <th className={styles.number}>{t("pages.stats.average")}</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => {
            const average = averageOf(row);
            return (
              <tr key={row.key}>
                <td>{name(row.key)}</td>
                <td className={styles.number}>{row.tried}</td>
                <td className={styles.number}>{row.booked}</td>
                <td>
                  <Rate item={row} />
                </td>
                <td className={styles.number}>{average === null ? "–" : f.seconds(average)}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </section>
  );
}

/**
 * What the 06:00 runs of the last 30 days tell: the share of slots booked, by machine and by
 * slot, how long a booking took, and why the slots were lost.
 */
export function StatsTab() {
  const { t } = useTranslation();
  const f = useFormat();
  const machines = useMachines();
  const settings = useSettings();
  const runs = useRuns({ trigger: "scheduled", dry_run: false, limit: STATS_RUNS });
  const since = addDays(localToday(), -STATS_DAYS);
  const stats =
    runs.data === undefined || settings.data === undefined
      ? undefined
      : statsOf(runs.data, since, settings.data.mumu_index);
  const machineName = (key: string) => {
    const machine = machines.find((item) => String(item.mumuIndex) === key);
    return machine === undefined
      ? t("pages.ticket.mumuName", { index: key })
      : t("pages.ticket.instanceName", { number: machine.place + 1 });
  };
  const average = stats === undefined ? null : averageOf(stats.all);
  return (
    <>
      <PageTitle>{t("pages.stats.title")}</PageTitle>
      <div className={styles.page}>
        {stats === undefined ? (
          <Loading />
        ) : (
          <>
            <p className={styles.muted}>
              {t("pages.stats.since", { days: STATS_DAYS, runs: stats.runs })}
            </p>
            <div className={styles.figures}>
              {(
                [
                  [`${stats.all.booked}/${stats.all.tried}`, t("pages.stats.allBooked")],
                  [
                    rateOf(stats.all) === null ? "–" : `${rateOf(stats.all)}%`,
                    t("pages.stats.allRate"),
                  ],
                  [average === null ? "–" : f.seconds(average), t("pages.stats.allAverage")],
                ] as const
              ).map(([value, label]) => (
                <div key={label} className={styles.figure}>
                  <span className={styles.figureValue}>{value}</span>
                  <span className={styles.figureLabel}>{label}</span>
                </div>
              ))}
            </div>
            <div className={styles.wide}>
              <div className={styles.column}>
                <TallyTable
                  title={t("pages.stats.byMachine")}
                  head={t("pages.board.machine")}
                  rows={stats.byMachine}
                  name={machineName}
                />
                <TallyTable
                  title={t("pages.stats.bySlot")}
                  head={t("pages.stats.slot")}
                  rows={stats.bySlot}
                  name={(key) => f.slot(key)}
                />
              </div>
              <section aria-label={t("pages.stats.reasons")} className={styles.card}>
                <h2 className={styles.sectionTitle}>{t("pages.stats.reasons")}</h2>
                {stats.reasons.length === 0 ? (
                  <p className={styles.muted}>{t("pages.stats.noLoss")}</p>
                ) : (
                  <ul className={styles.lines}>
                    {stats.reasons.map(({ reason, count }) => (
                      <li key={reason ?? ""} className={styles.line}>
                        <span className={`${styles.chip} ${styles.bad}`}>{count}</span>
                        <span className={styles.value}>{failureReason(t, f, reason)}</span>
                      </li>
                    ))}
                  </ul>
                )}
              </section>
            </div>
          </>
        )}
      </div>
    </>
  );
}
