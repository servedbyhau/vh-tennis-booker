import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Button } from "../../components/Button";
import type { Machine } from "../../machines";
import { useNewMachine } from "./machineMaking";
import { SetupRow } from "./SetupRow";
import styles from "./SetupRow.module.css";

/**
 * A machine whose MuMu instance is not on the PC yet: a button that makes it, a copy of the first
 * machine's, after a question; then how it goes.
 */
export function NewMachineRow({ machine, running }: { machine: Machine; running: boolean }) {
  const { t } = useTranslation();
  const [asked, setAsked] = useState(false);
  const made = useNewMachine();
  const title = t("pages.ticket.instanceName", { number: machine.place + 1 });
  const hint = asked
    ? t("pages.setup.machine.ask")
    : (made.text ?? t("pages.setup.machine.missing"));
  return (
    <SetupRow
      icon="machine"
      title={title}
      hint={made.failed ? undefined : hint}
      problem={made.failed ? made.text : null}
    >
      {asked ? (
        <span className={styles.buttons}>
          <Button
            variant="primary"
            className={styles.small}
            onClick={() => {
              setAsked(false);
              made.make();
            }}
          >
            {t("pages.setup.machine.yes")}
          </Button>
          <Button className={styles.small} onClick={() => setAsked(false)}>
            {t("pages.setup.machine.no")}
          </Button>
        </span>
      ) : (
        <Button
          className={styles.small}
          disabled={running || made.running}
          onClick={() => setAsked(true)}
        >
          {t("pages.setup.machine.create")}
        </Button>
      )}
    </SetupRow>
  );
}
