import { useMutation, useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { useOverview } from "../api/queries";
import { inDesktopWindow, installUpdate, newerVersion } from "../desktop";
import { inQuietTime, quietEnd } from "../quiet";
import { Button } from "./Button";
import styles from "./UpdateButton.module.css";

/** Asked once per opening of the window: a release comes about once a week. */
const UPDATE_KEY = ["update"] as const;

/**
 * Offer the newer version, in the desktop window only. Locked while a run holds the lock and
 * in the quiet time around the booking, since the installer replaces the files a run uses.
 */
export function UpdateButton({ now = () => new Date() }: { now?: () => Date }) {
  const { t } = useTranslation();
  const overview = useOverview();
  const update = useQuery({
    queryKey: UPDATE_KEY,
    queryFn: newerVersion,
    enabled: inDesktopWindow(),
    staleTime: Infinity,
    retry: false,
  });
  const install = useMutation({ mutationFn: installUpdate });

  const version = update.data;
  if (!version || !overview.data) {
    return null;
  }
  const { running, schedule } = overview.data;
  const quiet = inQuietTime(now(), schedule.wake_at, schedule.start_at);
  const locked = running !== null || quiet;
  let note: string | null = null;
  if (install.isError) {
    note = t("update.failed");
  } else if (locked) {
    note = t("update.locked", { from: schedule.wake_at, to: quietEnd(schedule.start_at) });
  }
  return (
    <div className={styles.update}>
      <Button
        variant="primary"
        disabled={locked || install.isPending}
        onClick={() => install.mutate()}
      >
        {install.isPending ? t("update.installing") : t("update.button", { version })}
      </Button>
      {note && <span className={styles.note}>{note}</span>}
    </div>
  );
}
