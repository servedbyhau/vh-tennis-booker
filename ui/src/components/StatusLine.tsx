import { useTranslation } from "react-i18next";
import { Link } from "react-router";
import type { Overview, Running } from "../api/types";
import { localToday } from "../format";
import { useMachines } from "../machines";
import { paths } from "../paths";
import { type Clash, useReadiness } from "../readiness";
import type { SetupProblem } from "../setupSteps";
import { useFormat } from "../useFormat";
import styles from "./StatusLine.module.css";

const TRIGGERS = [
  "scheduled",
  "dry_run",
  "manual",
  "setup",
  "cancel",
  "quota",
  "new_machine",
  "install_app",
] as const;

/**
 * The ink pill while a run holds the emulator: what runs. Screen readers hear it once,
 * when it appears.
 */
function RunningStatus({ running, startAt }: { running: Running; startAt: string }) {
  const { t } = useTranslation();
  const trigger = TRIGGERS.find((known) => known === running.trigger) ?? "other";
  return (
    <p role="status" className={styles.running}>
      <span aria-hidden="true" className={styles.light} />
      {t(`pages.overview.live.banner.${trigger}`, { start: startAt })}
    </p>
  );
}

/** Number machines as their tabs do: "1, 3". */
function machineNumbers(places: readonly number[]): string {
  return places.map((place) => place + 1).join(", ");
}

/**
 * One line in the header on whether the next booking can happen, in this order: the run
 * going on; the daily switch off; Windows keeping the PC from waking; what the Setup page lacks
 * (MuMu Player, a machine's MuMu instance or its Vinhomes app: a link to that step); machines
 * that would book the same; machines without an account; else ready for the next start. The
 * booking page holds what fixes the others (switching the schedule on allows waking).
 */
export function StatusLine({
  overview,
  setup = null,
}: {
  overview: Overview;
  setup?: SetupProblem | null;
}) {
  const { t } = useTranslation();
  const f = useFormat();
  const machines = useMachines();
  const { accountless, clashing } = useReadiness();
  const { running, schedule } = overview;
  if (running !== null) {
    return <RunningStatus running={running} startAt={schedule.start_at} />;
  }
  function clashWords({ court, slot, places }: Clash): string {
    return t("pages.overview.status.clash", {
      machines: machineNumbers(places),
      court: f.court(court),
      start: f.slotStart(slot),
    });
  }

  /** Number the machines of MuMu instances `indexes` as their tabs do. */
  function places(indexes: readonly number[]): string {
    return machineNumbers(
      machines.filter((item) => indexes.includes(item.mumuIndex ?? -1)).map(({ place }) => place),
    );
  }

  let words: string;
  let ready = false;
  if (!schedule.enabled) {
    words = t("pages.overview.status.scheduleOff");
  } else if (overview.wake_blocked) {
    words = t("pages.overview.status.wakeBlocked", { wake: schedule.wake_at });
  } else if (setup !== null) {
    const said =
      setup.kind === "mumu"
        ? t("pages.overview.status.noMumu")
        : t(`pages.overview.status.${setup.kind === "app" ? "noApp" : "noMachine"}`, {
            machines: places(setup.indexes),
          });
    return (
      <p className={styles.status}>
        <Link to={`${paths.setup}?step=${setup.kind}`} className={styles.todo}>
          <span aria-hidden="true">● </span>
          {said}
        </Link>
      </p>
    );
  } else if (clashing[0] !== undefined) {
    words = clashWords(clashing[0]);
  } else if (accountless.length > 0) {
    words = t("pages.overview.status.noAccount", {
      machines: machineNumbers(accountless.map(({ place }) => place)),
    });
  } else {
    ready = true;
    words = t("pages.overview.status.ready", {
      time: f.time(schedule.next_start),
      when: f.when(schedule.next_start, localToday()),
    });
  }
  return (
    <p className={styles.status}>
      <span className={ready ? styles.ready : styles.todo}>
        <span aria-hidden="true">● </span>
        {words}
      </span>
    </p>
  );
}
