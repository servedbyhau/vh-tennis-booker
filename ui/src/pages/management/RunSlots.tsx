import { useTranslation } from "react-i18next";
import type { RunSummary } from "../../api/types";
import { Icon } from "../../components/Icon";
import { failureReason } from "../../reasons";
import { useFormat } from "../../useFormat";
import styles from "./Board.module.css";

/** A run's slots as marks: booked, or not with why in the tooltip. */
export function RunSlots({ run }: { run: RunSummary }) {
  const { t } = useTranslation();
  const f = useFormat();
  if (run.slots.length === 0) {
    return <span className={styles.muted}>{t("pages.machines.noSlots")}</span>;
  }
  return (
    <span className={styles.chips}>
      {run.slots.map((slot) => (
        <span
          key={slot.slot}
          title={slot.ok ? undefined : failureReason(t, f, slot.reason)}
          className={`${styles.chip} ${slot.ok ? styles.good : styles.bad}`}
        >
          <Icon name={slot.ok ? "check" : "close"} />
          {f.slot(slot.slot)}
        </span>
      ))}
    </span>
  );
}
