import type { ReactNode } from "react";
import { Icon, type IconName } from "../../components/Icon";
import styles from "./SetupRow.module.css";

interface SetupRowProps {
  icon: IconName;
  title: string;
  /** A few words under it. */
  hint?: string;
  /** What went wrong with the last press. */
  problem?: string | null;
  /** Set off: the one thing to do next. */
  remind?: boolean;
  /** Its switch, named after the title. */
  children: ReactNode;
}

/** One thing of the Setup to turn on and off: its icon, its name and its switch. */
export function SetupRow({ icon, title, hint, problem, remind, children }: SetupRowProps) {
  return (
    <div className={remind ? `${styles.row} ${styles.remind}` : styles.row}>
      <span className={styles.icon}>
        <Icon name={icon} />
      </span>
      <div className={styles.text}>
        <span aria-hidden="true" className={styles.title}>
          {title}
        </span>
        {problem ? (
          <span role="alert" className={styles.problem}>
            {problem}
          </span>
        ) : (
          hint !== undefined && <span className={styles.hint}>{hint}</span>
        )}
      </div>
      {children}
    </div>
  );
}
