import { useEffect } from "react";
import { useTranslation } from "react-i18next";
import { Link, useSearchParams } from "react-router";
import { errorMessage } from "../api/errors";
import { Button } from "../components/Button";
import { Icon } from "../components/Icon";
import { PageTitle } from "../components/PageTitle";
import { paths } from "../paths";
import { firstOpen, STEPS, type StepId } from "../setupSteps";
import { useSetupSteps } from "../useSetupSteps";
import styles from "./SetupPage.module.css";
import { StepBody } from "./setup/StepBody";

function isStep(value: string | null): value is StepId {
  return STEPS.some((step) => step === value);
}

/**
 * The Setup: the steps a new PC takes, top to bottom, each checked by the app. The list on the
 * left tells which are done; the step shown, on the right, says in a line why it is needed and
 * holds what does it. It opens on the first step not done (`?step=` names another).
 */
export function SetupPage() {
  const { t } = useTranslation();
  const [params, setParams] = useSearchParams();
  const { report, overview, facts, done, read } = useSetupSteps();
  const asked = params.get("step");
  const shown: StepId = isStep(asked) ? asked : firstOpen(done);

  // Once all is read, the step shown stays put as its switch is pressed.
  useEffect(() => {
    if (read && !isStep(asked)) {
      setParams({ step: firstOpen(done) }, { replace: true });
    }
  }, [read, asked, done, setParams]);

  const place = STEPS.indexOf(shown);
  const previous = STEPS[place - 1];
  const next = STEPS[place + 1];
  const count = STEPS.filter((step) => done[step]).length;
  const running = overview.data?.running != null;
  const go = (step: StepId) => setParams({ step });
  return (
    <>
      <PageTitle>{t("pages.setupPage.title")}</PageTitle>
      <div className={styles.page}>
        <div className={styles.head}>
          <h1 className={styles.title}>{t("pages.setupPage.title")}</h1>
          <div className={styles.progress}>
            <span className={styles.count}>
              {t("pages.setupPage.progress", { done: count, total: STEPS.length })}
            </span>
            <span
              role="progressbar"
              aria-label={t("pages.setupPage.title")}
              aria-valuemin={0}
              aria-valuemax={STEPS.length}
              aria-valuenow={count}
              className={styles.bar}
            >
              <span style={{ width: `${(count / STEPS.length) * 100}%` }} />
            </span>
            <Button
              className={styles.check}
              disabled={report.isFetching}
              onClick={() => void report.refetch()}
            >
              <Icon name="refresh" />
              {t(report.isFetching ? "pages.setupPage.checking" : "pages.setupPage.check")}
            </Button>
          </div>
        </div>
        <div className={styles.columns}>
          <ol aria-label={t("pages.setupPage.steps")} className={styles.steps}>
            {STEPS.map((step, index) => (
              <li key={step}>
                <button
                  type="button"
                  aria-current={step === shown ? "step" : undefined}
                  className={styles.step}
                  onClick={() => go(step)}
                >
                  <span className={done[step] ? `${styles.mark} ${styles.done}` : styles.mark}>
                    {done[step] ? <Icon name="check" /> : index + 1}
                  </span>
                  <span className={styles.stepText}>
                    <span className={styles.stepTitle}>{t(`pages.setupPage.${step}.title`)}</span>
                    <span className={styles.stepState}>
                      {t(done[step] ? "pages.setupPage.done" : "pages.setupPage.todo")}
                    </span>
                  </span>
                </button>
              </li>
            ))}
          </ol>
          <section aria-labelledby="step-title" className={styles.detail}>
            <div className={styles.detailHead}>
              <span className={styles.overline}>
                {t("pages.setupPage.stepOf", { number: place + 1, total: STEPS.length })}
              </span>
              <h2 id="step-title" className={styles.detailTitle}>
                {t(`pages.setupPage.${shown}.title`)}
              </h2>
              <p className={styles.why}>{t(`pages.setupPage.${shown}.why`)}</p>
            </div>
            {report.isError && (
              <p role="alert" className={styles.problem}>
                {errorMessage(t, report.error)}
              </p>
            )}
            <StepBody
              step={shown}
              facts={facts}
              schedule={overview.data?.schedule}
              running={running}
            />
            <div className={styles.foot}>
              {previous !== undefined ? (
                <Button onClick={() => go(previous)}>
                  <Icon name="back" />
                  {t("pages.setupPage.previous")}
                </Button>
              ) : (
                <span />
              )}
              {next !== undefined ? (
                <Button variant="primary" onClick={() => go(next)}>
                  {t("pages.setupPage.next")}
                  <Icon name="forward" />
                </Button>
              ) : (
                <Link to={paths.overview} className={styles.finish}>
                  {t("pages.setupPage.finish")}
                  <Icon name="go" />
                </Link>
              )}
            </div>
          </section>
        </div>
      </div>
    </>
  );
}
