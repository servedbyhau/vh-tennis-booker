import { useState } from "react";
import { useTranslation } from "react-i18next";
import { errorMessage } from "../../api/errors";
import { useStartBooking } from "../../api/mutations";
import type { ScheduleState } from "../../api/types";
import { Button } from "../../components/Button";
import { Icon } from "../../components/Icon";
import { BOOKING_CLOSES, inBookingHours } from "../../quiet";
import { useNow } from "../../useNow";
import styles from "./DryRun.module.css";

/**
 * A real booking now, after a question: before the start time it gets ready and books at it,
 * for a morning the PC did not wake; from it, at once. It may start from the wake time until the
 * app closes, while no run holds the emulator.
 */
export function BookNow({ schedule, running }: { schedule: ScheduleState; running: boolean }) {
  const { t } = useTranslation();
  const now = useNow();
  const book = useStartBooking();
  const [asked, setAsked] = useState(false);
  const open = inBookingHours(now, schedule.wake_at);
  const hours = t("pages.setup.bookNow.hours", { from: schedule.wake_at, to: BOOKING_CLOSES });
  if (asked) {
    return (
      <div className={styles.ask}>
        <p>{t("pages.setup.bookNow.ask", { start: schedule.start_at })}</p>
        <span className={styles.answers}>
          <Button
            variant="primary"
            onClick={() => {
              setAsked(false);
              book.mutate();
            }}
          >
            {t("pages.setup.bookNow.yes")}
          </Button>
          <Button onClick={() => setAsked(false)}>{t("pages.setup.bookNow.no")}</Button>
        </span>
      </div>
    );
  }
  return (
    <>
      {book.isError && (
        <p role="alert" className={styles.refused}>
          {errorMessage(t, book.error)}
        </p>
      )}
      <Button
        className={styles.button}
        title={open ? undefined : hours}
        disabled={running || book.isPending || !open}
        onClick={() => setAsked(true)}
      >
        <Icon name="go" />
        {t(book.isPending ? "pages.setup.dryRun.starting" : "pages.setup.bookNow.button")}
      </Button>
    </>
  );
}
