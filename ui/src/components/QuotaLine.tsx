import { useTranslation } from "react-i18next";
import type { QuotaReading } from "../api/types";
import { useFormat } from "../useFormat";
import styles from "./QuotaLine.module.css";

/** Return "11/2026" from "2026-11". */
function monthText(month: string): string {
  const [year, number] = month.split("-");
  return `${number}/${year}`;
}

/**
 * What an account has left of each sport's quota in the month it books for, as a run last read
 * it on the app's history page: "Sân Tennis còn 1/8". When it was read is in the words a screen
 * reader says and in the tooltip; none left is marked.
 */
export function QuotaLine({ quota }: { quota: readonly QuotaReading[] }) {
  const { t } = useTranslation();
  const f = useFormat();
  if (quota.length === 0) {
    return null;
  }
  return (
    <span className={styles.line}>
      {quota.map((reading) => {
        const left = Math.max(0, reading.month_limit - reading.used);
        const read = t("quota.read", {
          used: reading.used,
          limit: reading.month_limit,
          month: monthText(reading.month),
          time: f.time(reading.read_at),
          day: f.shortDate(reading.read_at),
        });
        return (
          <span
            key={reading.utility}
            title={read}
            className={left === 0 ? `${styles.item} ${styles.none}` : styles.item}
          >
            {t("quota.left", { utility: reading.utility, left, limit: reading.month_limit })}
            <span className="visually-hidden"> ({read})</span>
          </span>
        );
      })}
    </span>
  );
}
