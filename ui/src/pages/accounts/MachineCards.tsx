import { useTranslation } from "react-i18next";
import type { Customer } from "../../api/types";
import { Button } from "../../components/Button";
import { accountOn, useMachines } from "../../machines";
import styles from "./MachineCards.module.css";

interface MachineCardsProps {
  customers: readonly Customer[];
  disabled: boolean;
  onDetach: (mumuIndex: number) => void;
}

/** One card per machine: the customer it books for and their account, or none. */
export function MachineCards({ customers, disabled, onDetach }: MachineCardsProps) {
  const { t } = useTranslation();
  const machines = useMachines();
  return (
    <ul className={styles.cards}>
      {machines.map((machine) => {
        const { mumuIndex } = machine;
        const found = mumuIndex === null ? null : accountOn(customers, mumuIndex);
        const name = t("pages.ticket.instanceName", { number: machine.place + 1 });
        return (
          <li
            key={machine.key}
            aria-label={name}
            className={found === null ? `${styles.card} ${styles.none}` : styles.card}
          >
            <div className={styles.head}>
              <span className={styles.machine}>{name}</span>
              {!machine.enabled && (
                <span className={styles.off}>{t("pages.accounts.machines.off")}</span>
              )}
            </div>
            {found === null ? (
              <>
                <p className={styles.name}>{t("pages.accounts.machines.none")}</p>
                <p className={styles.account}>{t("pages.accounts.machines.noneHint")}</p>
              </>
            ) : (
              <>
                <p className={styles.name}>{found.customer.name}</p>
                <p className={styles.account}>
                  {[found.account.phone, found.account.label].filter(Boolean).join(" · ")}
                </p>
                {mumuIndex !== null && (
                  <Button
                    className={styles.detach}
                    disabled={disabled}
                    aria-label={t("pages.accounts.machines.detachFrom", { machine: name })}
                    onClick={() => onDetach(mumuIndex)}
                  >
                    {t("pages.accounts.machines.detach")}
                  </Button>
                )}
              </>
            )}
          </li>
        );
      })}
    </ul>
  );
}
