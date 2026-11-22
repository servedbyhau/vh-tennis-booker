import { useTranslation } from "react-i18next";
import { machineAt, useMachines } from "../../machines";
import { AccountPicker } from "./AccountPicker";
import styles from "./SetupPanel.module.css";

/** The panel beside the ticket: the Setup of the machine shown. */
export function SetupPanel({ machine }: { machine: number }) {
  const { t } = useTranslation();
  const { mumuIndex } = machineAt(useMachines(), machine);
  return (
    <section aria-labelledby="setup-title" className={styles.panel}>
      <h2 id="setup-title" className={styles.title}>
        {t("pages.panel.setup")}
      </h2>
      <div className={styles.scroll}>
        {mumuIndex !== null && <AccountPicker key={mumuIndex} mumuIndex={mumuIndex} />}
      </div>
    </section>
  );
}
