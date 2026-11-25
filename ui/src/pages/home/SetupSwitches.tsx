import { useTranslation } from "react-i18next";
import { errorMessage } from "../../api/errors";
import {
  useOpenMachine,
  useSaveNotifications,
  useSwitchInstance,
  useSwitchSchedule,
} from "../../api/mutations";
import { useMumuInstances, useNotifications } from "../../api/queries";
import type { ScheduleState } from "../../api/types";
import { IconButton } from "../../components/IconButton";
import { Switch } from "../../components/Switch";
import { DEFAULT_LANGUAGE, LANGUAGES } from "../../i18n";
import type { Machine } from "../../machines";
import { NewMachineRow } from "./NewMachine";
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
 * The machine shown and, beside the first, which always books, its switch: on, the runs book
 * with it too (it gets its `[[instances]]` table, taking the first machine's choices until
 * changed); off, they leave its MuMu alone and its choices are hidden.
 */
export function MachineRow({ machine, running }: { machine: Machine; running: boolean }) {
  const instances = useMumuInstances().data ?? [];
  // A machine past the first whose instance MuMu does not list yet; none while MuMu is not read.
  const missing =
    machine.place > 0 &&
    machine.mumuIndex !== null &&
    instances.length > 0 &&
    !instances.includes(machine.mumuIndex);
  return missing ? (
    <NewMachineRow machine={machine} running={running} />
  ) : (
    <MachineSwitch machine={machine} running={running} />
  );
}

/** A machine whose MuMu instance is on the PC: its window to open and, past the first, its switch. */
function MachineSwitch({ machine, running }: { machine: Machine; running: boolean }) {
  const { t } = useTranslation();
  const use = useSwitchInstance();
  const open = useOpenMachine();
  const { mumuIndex } = machine;
  const failed = use.isError ? use.error : open.isError ? open.error : null;
  return (
    <SetupRow
      icon="machine"
      title={t("pages.ticket.instanceName", { number: machine.place + 1 })}
      problem={failed === null ? null : errorMessage(t, failed)}
    >
      {mumuIndex !== null && (
        <IconButton
          icon="window"
          label={t("pages.setup.open", { index: mumuIndex })}
          disabled={running || open.isPending}
          onClick={() => open.mutate(mumuIndex)}
        />
      )}
      {machine.place > 0 && (
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
      )}
    </SetupRow>
  );
}
