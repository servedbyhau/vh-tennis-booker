import { useTranslation } from "react-i18next";
import type { Machine } from "../../machines";
import { useReadiness } from "../../readiness";
import styles from "./MachineBar.module.css";

interface MachineBarProps {
  machines: readonly Machine[];
  /** The machine shown (0: the first). */
  machine: number;
  onMachine: (place: number) => void;
}

/**
 * The machines on top of the ticket, as index cards like the panel's tabs: the one pressed
 * shows its choices on the ticket and its setup beside it. A red mark tells a
 * machine that books with something to look at first (its account, a court and slot
 * another one books too), in words on hover; a machine switched off is
 * pale. Nothing shows with one machine.
 */
export function MachineBar({ machines, machine, onMachine }: MachineBarProps) {
  const { t } = useTranslation();
  const { accountless, clashing, short } = useReadiness();
  if (machines.length < 2) {
    return null;
  }
  const shown = Math.min(machine, machines.length - 1);

  /** What to look at on a machine, in a few words each. */
  function problems(item: Machine): string[] {
    return [
      ...(clashing.some(({ places }) => places.includes(item.place))
        ? [t("pages.ticket.instanceClash")]
        : []),
      ...(accountless.some(({ place }) => place === item.place)
        ? [t("pages.ticket.instanceNoAccount")]
        : []),
      ...(short.some(({ place }) => place === item.place) ? [t("pages.ticket.instanceQuota")] : []),
    ];
  }

  return (
    <div role="group" aria-label={t("pages.ticket.instance")} className={styles.bar}>
      {machines.map((item) => (
        <button
          key={item.key}
          type="button"
          aria-pressed={item.place === shown}
          title={[item.mumuIndex === null ? "" : `MuMu ${item.mumuIndex}`, ...problems(item)]
            .filter(Boolean)
            .join(" · ")}
          className={item.enabled ? styles.machine : `${styles.machine} ${styles.off}`}
          onClick={() => onMachine(item.place)}
        >
          {t("pages.ticket.instanceName", { number: item.place + 1 })}
          {!item.enabled && (
            <span className="visually-hidden">{`, ${t("pages.ticket.instanceOff")}`}</span>
          )}
          {problems(item).length > 0 && (
            <>
              <span aria-hidden="true" className={styles.mark}>
                !
              </span>
              <span className="visually-hidden">{`, ${problems(item).join(", ")}`}</span>
            </>
          )}
        </button>
      ))}
    </div>
  );
}
