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
  /** The icon in a colour: right (`ok`), or something to do (`bad`). */
  tone?: "ok" | "bad";
  /** Its switch, named after the title, if it has one. */
  children?: ReactNode;
}

/** A line of a card of the Setup: its icon, its name and its switch. */
export function SetupRow({ icon, title, hint, problem, remind, tone, children }: SetupRowProps) {
  const classes = [styles.row, remind && styles.remind, tone && styles[tone]].filter(Boolean);
  return (
    <div className={classes.join(" ")}>
      <span className={styles.icon}>
        <Icon name={icon} />
      </span>
      <div className={styles.text}>
        <span className={styles.title}>{title}</span>
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
