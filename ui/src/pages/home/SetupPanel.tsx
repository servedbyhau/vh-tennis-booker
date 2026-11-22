import { useTranslation } from "react-i18next";
import { useOverview } from "../../api/queries";
import { useMachines } from "../../machines";
import { useManualTicks } from "../../manualSteps";
import { setupLeft } from "../../setupState";
import styles from "./SetupPanel.module.css";
import { SetupTab } from "./SetupTab";

/** The panel beside the ticket: the Setup of the machine shown, the tasks left counted in red. */
export function SetupPanel({ machine }: { machine: number }) {
  const { t } = useTranslation();
  const overview = useOverview();
  const ticks = useManualTicks();
  const machines = useMachines();
  const left = overview.data === undefined ? 0 : setupLeft(ticks, machines);
  return (
    <section aria-labelledby="setup-title" className={styles.panel}>
      <h2 id="setup-title" className={styles.title}>
        {t("pages.panel.setup")}
        {left > 0 && (
          <>
            <span aria-hidden="true" className={styles.badge}>
              {left}
            </span>
            <span className="visually-hidden">{t("pages.panel.left", { count: left })}</span>
          </>
        )}
      </h2>
      <SetupTab machine={machine} />
    </section>
  );
}
