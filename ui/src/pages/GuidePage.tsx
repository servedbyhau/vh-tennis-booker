import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { useOverview } from "../api/queries";
import { Icon, type IconName } from "../components/Icon";
import { PageTitle } from "../components/PageTitle";
import { type Machine, useMachines } from "../machines";
import {
  doneOf,
  MANUAL_STEPS,
  type ManualStep,
  SHARED_STEPS,
  setManualDone,
  useManualTicks,
} from "../manualSteps";
import styles from "./GuidePage.module.css";

/** The times of the settings as they come, until the backend told its own: the guide shows anyway. */
const WAKE_AT = "05:45";
const START_AT = "06:00";

interface CardProps {
  id: string;
  icon: IconName;
  title: string;
  children: ReactNode;
}

function Card({ id, icon, title, children }: CardProps) {
  return (
    <section aria-labelledby={id} className={styles.card}>
      <h2 id={id} className={styles.title}>
        <Icon name={icon} />
        {title}
      </h2>
      {children}
    </section>
  );
}

/** The three steps of a first use. */
function Start({ start }: { start: string }) {
  const { t } = useTranslation();
  const names = { dryRun: t("pages.setup.dryRun.button"), daily: t("pages.setup.daily.title") };
  return (
    <section aria-labelledby="start-title" className={styles.start}>
      <h2 id="start-title" className={styles.startTitle}>
        {t("pages.guide.start.title", { start })}
      </h2>
      <ol className={styles.steps}>
        {(["1", "2", "3"] as const).map((step) => (
          <li key={step} className={styles.step}>
            <span aria-hidden="true" className={styles.number}>
              {step}
            </span>
            <span>{t(`pages.guide.start.steps.${step}`, names)}</span>
          </li>
        ))}
      </ol>
    </section>
  );
}

/** The tick of a step, of one machine or of all. */
function Tick({ step, machine, label }: { step: ManualStep; machine: Machine; label: string }) {
  const ticks = useManualTicks();
  return (
    <label className={styles.tick}>
      <input
        type="checkbox"
        aria-label={label}
        checked={doneOf(ticks, machine.key)[step]}
        onChange={(event) => setManualDone(step, event.target.checked, machine.key)}
      />
    </label>
  );
}

/**
 * The steps only the user can do, ticked by the user; the app does not check them. MuMu's is
 * ticked once, the others for each machine; those of a machine switched off are pale and not
 * counted as left.
 */
function Prepare() {
  const { t } = useTranslation();
  const machines = useMachines();
  const name = (machine: Machine) => t("pages.ticket.instanceName", { number: machine.place + 1 });
  const [first] = machines;
  return (
    <Card id="prepare-title" icon="tasks" title={t("pages.guide.prepare.title")}>
      <p className={styles.note}>{t("pages.guide.prepare.note")}</p>
      <table className={styles.table}>
        <thead>
          <tr>
            <th scope="col">
              <span className="visually-hidden">{t("pages.guide.prepare.step")}</span>
            </th>
            {machines.map((machine) => (
              <th key={machine.key} scope="col" className={machine.enabled ? "" : styles.off}>
                {name(machine)}
                {!machine.enabled && (
                  <span className={styles.state}>{t("pages.guide.prepare.off")}</span>
                )}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {MANUAL_STEPS.map((step) => {
            const title = t(`pages.guide.prepare.${step}.title`);
            return (
              <tr key={step}>
                <th scope="row">
                  <span className={styles.name}>{title}</span>
                  <span className={styles.hint}>{t(`pages.guide.prepare.${step}.hint`)}</span>
                </th>
                {SHARED_STEPS.includes(step) && first !== undefined ? (
                  <td colSpan={machines.length}>
                    <Tick step={step} machine={first} label={title} />
                  </td>
                ) : (
                  machines.map((machine) => (
                    <td key={machine.key} className={machine.enabled ? "" : styles.off}>
                      <Tick
                        step={step}
                        machine={machine}
                        label={t("pages.guide.prepare.box", { title, machine: name(machine) })}
                      />
                    </td>
                  ))
                )}
              </tr>
            );
          })}
        </tbody>
      </table>
    </Card>
  );
}

/** What happens by itself, and when. */
function Morning({ wake, start }: { wake: string; start: string }) {
  const { t } = useTranslation();
  const moments = [
    [wake, t("pages.guide.morning.wake")],
    [start, t("pages.guide.morning.start")],
    [t("pages.guide.morning.afterTime"), t("pages.guide.morning.after")],
  ] as const;
  return (
    <Card id="morning-title" icon="alarm" title={t("pages.guide.morning.title")}>
      <dl className={styles.moments}>
        {moments.map(([time, text]) => (
          <div key={time} className={styles.moment}>
            <dt>{time}</dt>
            <dd>{text}</dd>
          </div>
        ))}
      </dl>
      <p className={styles.note}>
        <strong>{t("pages.guide.morning.needs")}</strong> {t("pages.guide.morning.needsText")}
      </p>
    </Card>
  );
}

const TROUBLES = ["notRunning", "slotFull", "quota", "loggedOut"] as const;

function Trouble() {
  const { t } = useTranslation();
  const labels = { slotFull: t("reasons.slotFull") };
  return (
    <Card id="trouble-title" icon="help" title={t("pages.guide.trouble.title")}>
      <dl className={styles.answers}>
        {TROUBLES.map((trouble) => (
          <div key={trouble}>
            <dt>{t(`pages.guide.trouble.${trouble}.question`, labels)}</dt>
            <dd>{t(`pages.guide.trouble.${trouble}.answer`)}</dd>
          </div>
        ))}
      </dl>
    </Card>
  );
}

/**
 * How to use the app: the three steps, the ones only the user can do to tick for each machine,
 * what happens every morning and what to do when something goes wrong. MuMu's place and screen
 * and waking the PC need no step: the runs and the daily switch see to them.
 */
export function GuidePage() {
  const { t } = useTranslation();
  const schedule = useOverview().data?.schedule;
  const wake = schedule?.wake_at ?? WAKE_AT;
  const start = schedule?.start_at ?? START_AT;
  return (
    <>
      <PageTitle>{t("pages.guide.title")}</PageTitle>
      <h1 className="visually-hidden">{t("pages.guide.title")}</h1>
      <div className={styles.scroll}>
        <div className={styles.page}>
          <Start start={start} />
          <div className={styles.columns}>
            <div className={styles.column}>
              <Prepare />
              <Morning wake={wake} start={start} />
            </div>
            <Trouble />
          </div>
        </div>
      </div>
    </>
  );
}
