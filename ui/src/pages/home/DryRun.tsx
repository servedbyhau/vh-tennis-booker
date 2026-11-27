import { useTranslation } from "react-i18next";
import { errorMessage } from "../../api/errors";
import { useStartDryRun } from "../../api/mutations";
import { useRuns } from "../../api/queries";
import type { RunSummary, ScheduleState } from "../../api/types";
import { Button } from "../../components/Button";
import { Icon } from "../../components/Icon";
import { localToday } from "../../format";
import { quietEnd } from "../../quiet";
import { failureReason } from "../../reasons";
import { useFormat } from "../../useFormat";
import { BookNow } from "./BookNow";
import styles from "./DryRun.module.css";

/** The newest dry run in a line: when, and whether it passed or why not. */
function LastDryRun({ run }: { run: RunSummary | undefined }) {
  const { t } = useTranslation();
  const f = useFormat();
  if (run === undefined) {
    return <p>{t("pages.setup.dryRun.none")}</p>;
  }
  if (run.status === "running") {
    return null;
  }
  const at = { when: f.when(run.started_at, localToday()), time: f.time(run.started_at) };
  let result: string;
  if (run.status === "ok") {
    result = t("pages.setup.dryRun.passed");
  } else if (run.status === "interrupted") {
    result = t("pages.setup.dryRun.stopped");
  } else {
    const reason = run.error ?? run.slots.find((slot) => !slot.ok)?.reason ?? null;
    result = t("pages.setup.dryRun.failed", { reason: failureReason(t, f, reason) });
  }
  return (
    <p>
      {t("pages.setup.dryRun.last", at)} ·{" "}
      <strong className={run.status === "ok" ? styles.passed : styles.failed}>{result}</strong>
    </p>
  );
}

/**
 * A dry run and how the last one went, and a booking now beside it. The dry run walks the whole
 * booking and stops before "Xác nhận"; the backend refuses one in the quiet time, which the
 * tooltip tells, and none starts while another run holds the emulator.
 */
export function DryRun({ schedule, running }: { schedule: ScheduleState; running: boolean }) {
  const { t } = useTranslation();
  const dryRun = useStartDryRun();
  const last = useRuns({ dry_run: true, limit: 1 });
  let line = last.data !== undefined && <LastDryRun run={last.data[0]} />;
  if (running) {
    line = <p>{t("pages.overview.live.locked")}</p>;
  } else if (dryRun.isError) {
    line = (
      <p role="alert" className={styles.failed}>
        {errorMessage(t, dryRun.error)}
      </p>
    );
  }
  return (
    <div className={styles.dryRun}>
      <div className={styles.line}>{line}</div>
      <div className={styles.buttons}>
        <Button
          className={styles.button}
          title={t("pages.setup.dryRun.quiet", {
            from: schedule.wake_at,
            to: quietEnd(schedule.start_at),
          })}
          disabled={running || dryRun.isPending}
          onClick={() => dryRun.mutate()}
        >
          <Icon name="play" />
          {t(dryRun.isPending ? "pages.setup.dryRun.starting" : "pages.setup.dryRun.button")}
        </Button>
        <BookNow schedule={schedule} running={running} />
      </div>
    </div>
  );
}
