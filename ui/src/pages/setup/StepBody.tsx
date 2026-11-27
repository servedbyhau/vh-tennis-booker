import type { TFunction } from "i18next";
import { useTranslation } from "react-i18next";
import { Link } from "react-router";
import { errorMessage } from "../../api/errors";
import { useOpenMachine } from "../../api/mutations";
import type { MachineSetup, ScheduleState } from "../../api/types";
import { IconButton } from "../../components/IconButton";
import { accountOn, type Machine } from "../../machines";
import { paths } from "../../paths";
import type { SetupFacts, StepId } from "../../setupSteps";
import { AppInstallRow } from "../home/AppInstall";
import { DryRun } from "../home/DryRun";
import { NewMachineRow } from "../home/NewMachine";
import { SetupRow } from "../home/SetupRow";
import { DailyRow, KeepOnRow } from "../home/SetupSwitches";
import styles from "./StepBody.module.css";

interface BodyProps {
  facts: SetupFacts;
  schedule: ScheduleState | undefined;
  /** A run goes on: what would use MuMu waits. */
  running: boolean;
}

function machineTitle(t: TFunction, machine: Machine) {
  return t("pages.ticket.instanceName", { number: machine.place + 1 });
}

/** The checks of `machine`'s MuMu instance, or `undefined` while it is not on the PC. */
function checksOf(facts: SetupFacts, machine: Machine): MachineSetup | undefined {
  return facts.report?.machines.find((item) => item.mumu_index === machine.mumuIndex);
}

/** The PC kept on, by its switch. */
function PowerBody() {
  return (
    <div className={styles.card}>
      <KeepOnRow />
    </div>
  );
}

/** Whether MuMu Player is installed, and how to install it when not. */
function MumuBody({ facts }: BodyProps) {
  const { t } = useTranslation();
  const status = facts.report?.mumu;
  if (status === undefined) {
    return null;
  }
  const found = status !== "user";
  return (
    <div className={styles.card}>
      <SetupRow
        icon={found ? "check" : "warn"}
        tone={found ? "ok" : "bad"}
        title={t(found ? "pages.setupPage.mumu.found" : "pages.setupPage.mumu.missing")}
        hint={found ? undefined : t("pages.setupPage.mumu.how")}
      />
    </div>
  );
}

/** A button that opens the machine of MuMu instance `index`, and why it did not. */
function useOpenButton(running: boolean) {
  const { t } = useTranslation();
  const open = useOpenMachine();
  return {
    problem: (index: number) =>
      open.isError && open.variables === index ? errorMessage(t, open.error) : null,
    button: (index: number) => (
      <IconButton
        icon="start"
        label={t("pages.setup.open", { index })}
        disabled={running || open.isPending}
        onClick={() => open.mutate(index)}
      />
    ),
  };
}

/** Each machine: its MuMu instance as checked, with a button that opens it, or one that makes it. */
function MachinesBody({ facts, running }: BodyProps) {
  const { t } = useTranslation();
  const open = useOpenButton(running);
  if (facts.report === undefined) {
    return null;
  }
  return (
    <div className={styles.card}>
      {facts.machines.map((machine) => {
        const checks = checksOf(facts, machine);
        if (checks === undefined) {
          return machine.place === 0 ? (
            <SetupRow
              key={machine.key}
              icon="warn"
              tone="bad"
              title={machineTitle(t, machine)}
              hint={t("pages.setupPage.machines.first")}
            />
          ) : (
            <NewMachineRow key={machine.key} machine={machine} running={running} />
          );
        }
        const later = checks.screen !== "ok" || checks.performance !== "ok";
        let hint = t(later ? "pages.setupPage.machines.later" : "pages.setupPage.machines.ready");
        if (!machine.enabled) {
          hint = `${hint} · ${t("pages.setupPage.machines.off")}`;
        }
        return (
          <SetupRow
            key={machine.key}
            icon="check"
            tone="ok"
            title={machineTitle(t, machine)}
            hint={hint}
            problem={open.problem(checks.mumu_index)}
          >
            {open.button(checks.mumu_index)}
          </SetupRow>
        );
      })}
    </div>
  );
}

/** The app installed from a file, then whether each machine has it. */
function AppBody({ facts, running }: BodyProps) {
  const { t } = useTranslation();
  const open = useOpenButton(running);
  const made = facts.machines.flatMap((machine) => {
    const checks = checksOf(facts, machine);
    return checks === undefined ? [] : [{ machine, checks }];
  });
  return (
    <div className={styles.card}>
      <AppInstallRow running={running} />
      {made.map(({ machine, checks }) => {
        const app = checks.app;
        const known = app === "ok" || app === "user";
        return (
          <SetupRow
            key={machine.key}
            icon={app === "ok" ? "check" : known ? "warn" : "unknown"}
            tone={app === "ok" ? "ok" : known ? "bad" : undefined}
            title={machineTitle(t, machine)}
            hint={t(
              app === "ok"
                ? "pages.setupPage.app.ok"
                : known
                  ? "pages.setupPage.app.missing"
                  : "pages.setupPage.app.unknown",
            )}
            problem={open.problem(checks.mumu_index)}
          >
            {!known && open.button(checks.mumu_index)}
          </SetupRow>
        );
      })}
    </div>
  );
}

/** The account each booking machine books with, chosen on the booking page. */
function AccountsBody({ facts }: BodyProps) {
  const { t } = useTranslation();
  const customers = facts.customers ?? [];
  return (
    <div className={styles.card}>
      {facts.machines
        .filter((machine) => machine.enabled && machine.mumuIndex !== null)
        .map((machine) => {
          const on = accountOn(customers, machine.mumuIndex ?? -1);
          return (
            <SetupRow
              key={machine.key}
              icon={on === null ? "warn" : "check"}
              tone={on === null ? "bad" : "ok"}
              title={machineTitle(t, machine)}
              hint={on === null ? t("pages.setupPage.accounts.none") : on.customer.name}
            >
              <Link to={paths.overview} className={styles.link}>
                {t("pages.setupPage.accounts.choose")}
              </Link>
            </SetupRow>
          );
        })}
    </div>
  );
}

/** A dry run, then the daily booking switched on. */
function DailyBody({ schedule, running }: BodyProps) {
  if (schedule === undefined) {
    return null;
  }
  return (
    <>
      <div className={styles.card}>
        <DailyRow schedule={schedule} running={running} />
      </div>
      <DryRun schedule={schedule} running={running} bookNow={false} />
    </>
  );
}

const BODIES: Record<StepId, (props: BodyProps) => React.JSX.Element | null> = {
  power: PowerBody,
  mumu: MumuBody,
  machines: MachinesBody,
  app: AppBody,
  accounts: AccountsBody,
  daily: DailyBody,
};

/** What a step shows and lets be done. */
export function StepBody({ step, ...props }: BodyProps & { step: StepId }) {
  const Body = BODIES[step];
  return <Body {...props} />;
}
