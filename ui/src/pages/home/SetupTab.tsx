import { type FormEvent, useId, useState } from "react";
import { useTranslation } from "react-i18next";
import { useDeleteLogin, useSaveLogin } from "../../api/mutations";
import { useLogin, useOverview } from "../../api/queries";
import type { Overview } from "../../api/types";
import { Button } from "../../components/Button";
import { QueryView } from "../../components/QueryView";
import { type Machine, machineAt, useMachines } from "../../machines";
import {
  MANUAL_STEPS,
  SHARED_STEPS,
  setManualDone,
  useManualSteps,
  useManualTicks,
} from "../../manualSteps";
import { setupDone } from "../../setupState";
import styles from "./SetupTab.module.css";

/** The three steps of a first use; shown first until everything is set up. */
function HowTo() {
  const { t } = useTranslation();
  const names = { dryRun: t("pages.ticket.dryRun.button"), daily: t("pages.ticket.autoShort") };
  return (
    <ol className={styles.howto}>
      {(["1", "2", "3"] as const).map((step) => (
        <li key={step}>{t(`pages.setup.start.steps.${step}`, names)}</li>
      ))}
    </ol>
  );
}

/**
 * The steps only the user can do, ticked by the user; the app does not check them. With
 * several machines, the ticks are the shown machine's, MuMu's shared by all.
 */
function ManualSteps({ machine, several }: { machine: Machine; several: boolean }) {
  const { t } = useTranslation();
  const done = useManualSteps(machine.key);
  return (
    <section aria-labelledby="manual-title">
      <h3 id="manual-title" className={styles.heading}>
        {t("pages.setup.manual.title")}
      </h3>
      {several && machine.mumuIndex !== null && (
        <p className={styles.machine}>
          {t("pages.setup.manual.machine", {
            number: machine.place + 1,
            index: machine.mumuIndex,
          })}
          {!machine.enabled && ` · ${t("pages.setup.manual.off")}`}
        </p>
      )}
      <ul className={styles.list}>
        {MANUAL_STEPS.map((step) => (
          <li key={step} className={styles.item}>
            <label className={styles.check}>
              <input
                type="checkbox"
                checked={done[step]}
                onChange={(event) => setManualDone(step, event.target.checked, machine.key)}
              />
              <span className={styles.text}>
                <span className={styles.title}>
                  {t(`pages.setup.manual.${step}.title`)}
                  {several && SHARED_STEPS.includes(step) && ` (${t("pages.setup.manual.shared")})`}
                </span>
                <span className={styles.hint}>{t(`pages.setup.manual.${step}.hint`)}</span>
              </span>
            </label>
          </li>
        ))}
      </ul>
    </section>
  );
}

/** A phone number as the Vinhomes app takes it: 10 digits from 0. */
const PHONE_PATTERN = "0[0-9]{9}";

/**
 * The login a run types in when the Vinhomes app logged out (it does when the account logs
 * in on another device), one per machine. Saved in Windows' vault through the backend,
 * which never answers the password: once saved, only the masked phone number shows.
 */
function AutoLogin({ mumuIndex }: { mumuIndex: number }) {
  const { t } = useTranslation();
  const id = useId();
  const login = useLogin(mumuIndex);
  const save = useSaveLogin();
  const remove = useDeleteLogin();
  const [editing, setEditing] = useState(false);
  const [phone, setPhone] = useState("");
  const [password, setPassword] = useState("");
  const saved = login.data?.saved === true ? login.data : null;

  function submit(event: FormEvent) {
    event.preventDefault();
    save.mutate(
      { mumuIndex, login: { phone, password } },
      {
        onSuccess: () => {
          setPhone("");
          setPassword("");
          setEditing(false);
        },
      },
    );
  }

  return (
    <section aria-labelledby={`${id}-title`}>
      <h3 id={`${id}-title`} className={styles.heading}>
        {t("pages.setup.login.title")}
      </h3>
      <p className={styles.note}>{t("pages.setup.login.why")}</p>
      {saved !== null && !editing ? (
        <div className={styles.saved}>
          <span className={styles.savedText}>
            {t("pages.setup.login.saved", { phone: saved.phone ?? "" })}
          </span>
          <Button onClick={() => setEditing(true)}>{t("pages.setup.login.change")}</Button>
          <Button disabled={remove.isPending} onClick={() => remove.mutate(mumuIndex)}>
            {t("pages.setup.login.remove")}
          </Button>
        </div>
      ) : (
        <form className={styles.form} onSubmit={submit}>
          <label className={styles.field}>
            <span className={styles.label}>{t("pages.setup.login.phone")}</span>
            <input
              type="tel"
              inputMode="numeric"
              autoComplete="off"
              required
              pattern={PHONE_PATTERN}
              maxLength={10}
              value={phone}
              onChange={(event) => setPhone(event.target.value.trim())}
            />
          </label>
          <label className={styles.field}>
            <span className={styles.label}>{t("pages.setup.login.password")}</span>
            <input
              type="password"
              autoComplete="new-password"
              required
              maxLength={128}
              value={password}
              onChange={(event) => setPassword(event.target.value)}
            />
          </label>
          <div className={styles.actions}>
            <Button type="submit" variant="primary" disabled={save.isPending}>
              {t("pages.setup.login.save")}
            </Button>
            {editing && (
              <Button onClick={() => setEditing(false)}>{t("pages.setup.login.cancel")}</Button>
            )}
          </div>
          {save.isError && (
            <p role="alert" className={styles.error}>
              {t("pages.setup.login.failed")}
            </p>
          )}
        </form>
      )}
      {remove.isError && (
        <p role="alert" className={styles.error}>
          {t("pages.setup.login.failed")}
        </p>
      )}
    </section>
  );
}

const TROUBLES = ["notRunning", "slotFull", "quota", "loggedOut"] as const;

/** The guide in rows that open one at a time: how to use it, the mornings, the problems. */
function Guide({ overview, howto }: { overview: Overview; howto: boolean }) {
  const { t } = useTranslation();
  const { wake_at: wake, start_at: start } = overview.schedule;
  const labels = { slotFull: t("reasons.slotFull") };
  return (
    <section aria-labelledby="guide-title">
      <h3 id="guide-title" className={styles.heading}>
        {t("pages.setup.guide.title")}
      </h3>
      <div className={styles.list}>
        {howto && (
          <details className={styles.item}>
            <summary className={styles.summary}>{t("pages.setup.guide.howto")}</summary>
            <HowTo />
          </details>
        )}
        <details className={styles.item}>
          <summary className={styles.summary}>{t("pages.setup.guide.morning.title")}</summary>
          <div className={styles.answer}>
            <p>{t("pages.setup.guide.morning.text", { wake, start })}</p>
            <p>
              <strong>{t("pages.setup.guide.morning.needs")}</strong>{" "}
              {t("pages.setup.guide.morning.needsText")}
            </p>
          </div>
        </details>
        <details className={styles.item}>
          <summary className={styles.summary}>{t("pages.setup.guide.trouble.title")}</summary>
          <dl className={styles.answer}>
            {TROUBLES.map((trouble) => (
              <div key={trouble}>
                <dt>{t(`pages.setup.guide.trouble.${trouble}.question`, labels)}</dt>
                <dd>{t(`pages.setup.guide.trouble.${trouble}.answer`)}</dd>
              </div>
            ))}
          </dl>
        </details>
      </div>
    </section>
  );
}

/**
 * The Setup tab: how to start while anything is left, the steps the user ticks, the shown
 * machine's saved login and the guide; the notification switch is on the ticket. MuMu's place and screen and waking the
 * PC need no step: the runs and the daily switch see to them. It shows the machine chosen
 * on the ticket (`machine`, 0: the first).
 */
export function SetupTab({ machine }: { machine: number }) {
  const { t } = useTranslation();
  const overview = useOverview();
  const ticks = useManualTicks();
  const machines = useMachines();
  const shown = machineAt(machines, machine);
  return (
    <div className={styles.tab}>
      <QueryView query={overview}>
        {(data) => {
          const done = setupDone(data, ticks, machines);
          return (
            <>
              {!done && (
                <section aria-labelledby="start-title" className={styles.start}>
                  <h3 id="start-title" className={styles.startTitle}>
                    {t("pages.setup.start.title", { start: data.schedule.start_at })}
                  </h3>
                  <HowTo />
                </section>
              )}
              <ManualSteps machine={shown} several={machines.length > 1} />
              {shown.mumuIndex !== null && (
                <AutoLogin key={shown.mumuIndex} mumuIndex={shown.mumuIndex} />
              )}
              <Guide overview={data} howto={done} />
            </>
          );
        }}
      </QueryView>
    </div>
  );
}
