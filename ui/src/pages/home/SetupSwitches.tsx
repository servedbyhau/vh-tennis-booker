import { useTranslation } from "react-i18next";
import { errorMessage } from "../../api/errors";
import { useSaveNotifications, useSwitchInstance, useSwitchSchedule } from "../../api/mutations";
import { useNotifications } from "../../api/queries";
import type { ScheduleState } from "../../api/types";
import { Switch } from "../../components/Switch";
import { DEFAULT_LANGUAGE, LANGUAGES } from "../../i18n";
import type { Machine } from "../../machines";
import { SetupRow } from "./SetupRow";

interface DailyProps {
  schedule: ScheduleState;
  /** A run goes on: the daily task stays as it is until it ends. */
  running: boolean;
}

/**
 * The booking of every morning. It stays locked until a dry run has passed; once one has, a
 * switch still off is set off.
 */
export function DailyRow({ schedule, running }: DailyProps) {
  const { t } = useTranslation();
  const toggle = useSwitchSchedule();
  const locked = !schedule.enabled && !schedule.dry_run_passed;
  const title = t("pages.setup.daily.title");
  return (
    <SetupRow
      icon="alarm"
      title={title}
      hint={
        locked
          ? t("pages.setup.daily.locked")
          : t("pages.setup.daily.times", { start: schedule.start_at, wake: schedule.wake_at })
      }
      problem={toggle.isError ? errorMessage(t, toggle.error) : null}
      remind={!schedule.enabled && schedule.dry_run_passed}
    >
      <Switch
        label={title}
        checked={schedule.enabled}
        disabled={locked || running || toggle.isPending}
        onChange={(enabled) => toggle.mutate(enabled)}
      />
    </SetupRow>
  );
}

/** The Windows notification after every run, saved at once; it shows once the setting is read. */
export function NotifyRow() {
  const { t, i18n } = useTranslation();
  const notifications = useNotifications();
  const save = useSaveNotifications();
  // The notification speaks the UI's language; the switch saves it along.
  const language = LANGUAGES.find((known) => known === i18n.resolvedLanguage) ?? DEFAULT_LANGUAGE;
  if (notifications.data === undefined) {
    return null;
  }
  const title = t("pages.setup.notify");
  return (
    <SetupRow icon="bell" title={title} problem={save.isError ? errorMessage(t, save.error) : null}>
      <Switch
        label={title}
        checked={notifications.data.enabled}
        disabled={save.isPending}
        onChange={(enabled) => save.mutate({ enabled, language })}
      />
    </SetupRow>
  );
}

/**
 * The switch of a machine beside the first: on, the runs book with it too (it gets its
 * `[[instances]]` table, taking the first machine's choices until changed); off, they leave
 * its MuMu alone and its choices are hidden.
 */
export function MachineRow({ machine, running }: { machine: Machine; running: boolean }) {
  const { t } = useTranslation();
  const use = useSwitchInstance();
  const { mumuIndex } = machine;
  return (
    <SetupRow
      icon="machine"
      title={t("pages.setup.use")}
      problem={use.isError ? errorMessage(t, use.error) : null}
    >
      <Switch
        label={t("pages.setup.useLabel", { number: machine.place + 1, index: mumuIndex })}
        checked={machine.enabled}
        disabled={mumuIndex === null || running || use.isPending}
        onChange={(enabled) => {
          if (mumuIndex !== null) {
            use.mutate({ mumuIndex, enabled });
          }
        }}
      />
    </SetupRow>
  );
}
