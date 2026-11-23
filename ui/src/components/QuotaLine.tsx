import { useTranslation } from "react-i18next";
import type { QuotaReading } from "../api/types";
import { leftOf, readingsOf } from "../quota";
import { useFormat } from "../useFormat";
import styles from "./QuotaLine.module.css";

/** Return "11/2026" from "2026-11". */
function monthText(month: string): string {
  const [year, number] = month.split("-");
  return `${number}/${year}`;
}

interface QuotaLineProps {
  quota: readonly QuotaReading[];
  /** The month the next booking is for (`useBookingMonth`); nothing shows while unknown. */
  month: string | undefined;
}

/**
 * What an account has left of each sport's quota in the month the next booking is for, as a
 * run last read it on the app's history page: "Sân Tennis còn 1/8". When it was read is in the
 * words a screen reader says and in the tooltip; none left is marked.
 */
export function QuotaLine({ quota, month }: QuotaLineProps) {
  const { t } = useTranslation();
  const f = useFormat();
  const shown = readingsOf(quota, month);
  if (shown.length === 0) {
    return null;
  }
  return (
    <span className={styles.line}>
      {shown.map((reading) => {
        const left = leftOf(reading);
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
