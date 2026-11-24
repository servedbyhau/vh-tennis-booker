import { useTranslation } from "react-i18next";
import { Link } from "react-router";
import { errorMessage } from "../../api/errors";
import { useOpenMachine } from "../../api/mutations";
import { useOverview } from "../../api/queries";
import { Button } from "../../components/Button";
import { Icon } from "../../components/Icon";
import { PageTitle } from "../../components/PageTitle";
import { QuotaLine } from "../../components/QuotaLine";
import { Loading } from "../../components/States";
import { paths } from "../../paths";
import { useBookingMonth } from "../../quota";
import { useFormat } from "../../useFormat";
import styles from "./Board.module.css";
import { type MachineFacts, runWhen, useMachineFacts } from "./machineFacts";
import { useQuotaRefresh } from "./quotaRefresh";
import { RunSlots } from "./RunSlots";

/** One machine: what it books, with whose account, its quota, its last booking and what to do. */
function MachineCard({ facts, running }: { facts: MachineFacts; running: boolean }) {
  const { t } = useTranslation();
  const f = useFormat();
  const month = useBookingMonth();
  const open = useOpenMachine();
  const { machine, booking, attached, lastRun } = facts;
  const refresh = useQuotaRefresh(attached === null ? null : machine.mumuIndex);
  const name = t("pages.ticket.instanceName", { number: machine.place + 1 });
  return (
    <section aria-label={name} className={styles.card}>
      <div className={styles.cardHead}>
        <h2 className={styles.cardTitle}>{name}</h2>
        <span className={`${styles.chip} ${booking === undefined ? "" : styles.good}`}>
          {booking === undefined ? t("pages.machines.off") : t("pages.machines.on")}
        </span>
        {machine.mumuIndex !== null && (
          <span className={`${styles.muted} ${styles.mono}`}>MuMu {machine.mumuIndex}</span>
        )}
      </div>
      <ul className={styles.lines}>
        <li className={styles.line}>
          <span className={styles.label}>{t("pages.machines.account")}</span>
          <span className={styles.value}>
            {attached === null ? (
              <span className={styles.muted}>{t("pages.machines.noAccount")}</span>
            ) : (
              <>
                {attached.customer.name}{" "}
                <span className={`${styles.muted} ${styles.mono}`}>
                  {attached.account.phone ?? ""}
                </span>
              </>
            )}
          </span>
        </li>
        <li className={styles.line}>
          <span className={styles.label}>{t("pages.machines.books")}</span>
          <span className={styles.value}>
            {booking === undefined ? (
              <span className={styles.muted}>{t("pages.machines.booksNothing")}</span>
            ) : (
              <>
                {f.court(booking.court)}
                <span className={styles.chips}>
                  {booking.slots.map((slot) => (
                    <span key={slot} className={styles.chip}>
                      {f.slot(slot)}
                    </span>
                  ))}
                </span>
              </>
            )}
          </span>
        </li>
        {attached !== null && (
          <li className={styles.line}>
            <span className={styles.label}>{t("pages.machines.quota")}</span>
            <span className={styles.value}>
              <QuotaLine quota={attached.account.quota} month={month} />
              {attached.account.quota.length === 0 && (
                <span className={styles.muted}>{t("pages.machines.quotaUnknown")}</span>
              )}
              {refresh.text !== null && (
                <span role="status" className={styles.muted}>
                  {" "}
                  {refresh.text}
                </span>
              )}
            </span>
          </li>
        )}
        <li className={styles.line}>
          <span className={styles.label}>{t("pages.machines.last")}</span>
          <span className={styles.value}>
            {lastRun === undefined ? (
              <span className={styles.muted}>{t("pages.machines.never")}</span>
            ) : (
              <>
                <span className={styles.muted}>{runWhen(t, f, lastRun)}</span>
                <RunSlots run={lastRun} />
              </>
            )}
          </span>
        </li>
      </ul>
      {open.isError && (
        <p role="alert" className={styles.muted}>
          {errorMessage(t, open.error)}
        </p>
      )}
      <div className={styles.actions}>
        {machine.mumuIndex !== null && (
          <Button
            disabled={running || open.isPending}
            onClick={() => machine.mumuIndex !== null && open.mutate(machine.mumuIndex)}
          >
            <Icon name="window" /> {t("pages.machines.open")}
          </Button>
        )}
        {attached !== null && (
          <Button disabled={running || refresh.running} onClick={refresh.read}>
            <Icon name="refresh" /> {t("quota.refresh.button")}
          </Button>
        )}
        <Link to={paths.overview} className={styles.muted}>
          {t("pages.machines.change")}
        </Link>
      </div>
    </section>
  );
}

/**
 * Every machine side by side: what it books and with whose account, the quota left, how its last
 * booking went, and the buttons that open its MuMu and read its quota again. What it books is
 * chosen on the booking page.
 */
export function MachinesTab() {
  const { t } = useTranslation();
  const facts = useMachineFacts();
  const overview = useOverview();
  const running = overview.data?.running != null;
  return (
    <>
      <PageTitle>{t("pages.machines.title")}</PageTitle>
      <div className={styles.page}>
        {facts === undefined ? (
          <Loading />
        ) : (
          <div className={styles.grid}>
            {facts.map((item) => (
              <MachineCard key={item.machine.place} facts={item} running={running} />
            ))}
          </div>
        )}
      </div>
    </>
  );
}
