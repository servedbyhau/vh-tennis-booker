import { useTranslation } from "react-i18next";
import { useOverview } from "../../api/queries";
import { machineAt, useMachines } from "../../machines";
import { AccountPicker } from "./AccountPicker";
import { DryRun } from "./DryRun";
import styles from "./SetupPanel.module.css";
import { DailyRow, KeepOnRow, MachineRow, NotifyRow } from "./SetupSwitches";

/**
 * The panel beside the ticket: what holds for every machine (the daily booking and the result
 * notification), then the machine shown (whether the runs book with it, and the account it
 * books with), and the dry run at the foot.
 */
export function SetupPanel({ machine }: { machine: number }) {
  const { t } = useTranslation();
  const overview = useOverview();
  const machines = useMachines();
  const shown = machineAt(machines, machine);
  const running = overview.data?.running != null;
  return (
    <section aria-labelledby="setup-title" className={styles.panel}>
      <h2 id="setup-title" className={styles.title}>
        {t("pages.panel.setup")}
      </h2>
      <div className={styles.scroll}>
        {overview.data !== undefined && (
          <div className={styles.card}>
            <DailyRow schedule={overview.data.schedule} running={running} />
            <NotifyRow />
            <KeepOnRow />
          </div>
        )}
        {shown.mumuIndex !== null && (
          // Another machine starts with nothing open and no error of the last.
          <section
            key={shown.mumuIndex}
            aria-label={t("pages.ticket.instanceName", { number: shown.place + 1 })}
            className={styles.card}
          >
            <MachineRow machine={shown} running={running} />
            <AccountPicker mumuIndex={shown.mumuIndex} />
          </section>
        )}
      </div>
      {overview.data !== undefined && (
        <DryRun schedule={overview.data.schedule} running={running} />
      )}
    </section>
  );
}
