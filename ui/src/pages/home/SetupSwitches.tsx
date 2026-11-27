import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router";
import { errorMessage } from "../../api/errors";
import {
  useSaveNotifications,
  useSwitchInstance,
  useSwitchKeepOn,
  useSwitchSchedule,
} from "../../api/mutations";
import { useKeepOn, useMumuInstances, useNotifications } from "../../api/queries";
import type { ScheduleState } from "../../api/types";
import { Switch } from "../../components/Switch";
import { DEFAULT_LANGUAGE, LANGUAGES } from "../../i18n";
import type { Machine } from "../../machines";
import { paths } from "../../paths";
import { SetupRow } from "./SetupRow";

interface DailyProps {
  schedule: ScheduleState;
  /** A run goes on: the daily task stays as it is until it ends. */
  running: boolean;
}

/** The booking of every morning; a switch still off is set off. A dry run is not needed. */
export function DailyRow({ schedule, running }: DailyProps) {
  const { t } = useTranslation();
  const toggle = useSwitchSchedule();
  const title = t("pages.setup.daily.title");
  return (
    <SetupRow
      icon="alarm"
      title={title}
      hint={t("pages.setup.daily.times", { start: schedule.start_at, wake: schedule.wake_at })}
      problem={toggle.isError ? errorMessage(t, toggle.error) : null}
      remind={!schedule.enabled}
    >
      <Switch
        label={title}
        checked={schedule.enabled}
        disabled={running || toggle.isPending}
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
 * The PC kept on while plugged in (no sleep, no hibernation, nothing on closing the lid), read
 * from Windows; off gives back the values it had. It shows once Windows is read, not when
 * Windows could not be.
 */
export function KeepOnRow() {
  const { t } = useTranslation();
  const keepOn = useKeepOn();
  const toggle = useSwitchKeepOn();
  const state = keepOn.data;
  if (state === undefined) {
    return null;
  }
  const title = t("pages.setup.keepOn.title");
  const hint = state.on
    ? t(state.modern_standby ? "pages.setup.keepOn.standby" : "pages.setup.keepOn.on")
    : t("pages.setup.keepOn.off");
  return (
    <SetupRow
      icon="power"
      title={title}
      hint={hint}
      problem={toggle.isError ? errorMessage(t, toggle.error) : null}
    >
      <Switch
        label={title}
        checked={state.on}
        disabled={toggle.isPending}
        onChange={(on) => toggle.mutate(on)}
      />
    </SetupRow>
  );
}

/**
 * The machine shown and, beside the first, which always books, its switch:
 * on, the runs book with it too (it gets its `[[instances]]` table, taking the first machine's
 * choices until changed); off, they leave its MuMu alone and its choices are hidden. A machine
 * whose MuMu instance is not on the PC yet says so, and switching it on leads to the Setup
 * page's machines, where it is made.
 */
export function MachineRow({ machine, running }: { machine: Machine; running: boolean }) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const instances = useMumuInstances().data ?? [];
  const use = useSwitchInstance();
  const { mumuIndex } = machine;
  // A machine past the first whose instance MuMu does not list yet; none while MuMu is not read.
  const missing =
    machine.place > 0 &&
    mumuIndex !== null &&
    instances.length > 0 &&
    !instances.includes(mumuIndex);
  return (
    <SetupRow
      icon="machine"
      title={t("pages.ticket.instanceName", { number: machine.place + 1 })}
      hint={missing ? t("pages.setup.machine.missing") : undefined}
      problem={use.isError ? errorMessage(t, use.error) : null}
    >
      {machine.place > 0 && (
        <Switch
          label={t("pages.setup.useLabel", { number: machine.place + 1, index: mumuIndex })}
          checked={machine.enabled}
          disabled={mumuIndex === null || running || use.isPending}
          onChange={(enabled) => {
            if (enabled && missing) {
              void navigate(`${paths.setup}?step=machines`);
            } else if (mumuIndex !== null) {
              use.mutate({ mumuIndex, enabled });
            }
          }}
        />
      )}
    </SetupRow>
  );
}
