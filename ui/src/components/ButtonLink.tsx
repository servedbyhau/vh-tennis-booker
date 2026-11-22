import type { ComponentPropsWithoutRef } from "react";
import styles from "./Button.module.css";

interface ButtonLinkProps extends ComponentPropsWithoutRef<"a"> {
  /** As a `Button`'s. */
  variant?: "primary" | "secondary";
}

/** A link that looks like a `Button`: for a file to save, which the browser does by itself. */
export function ButtonLink({ variant = "secondary", className, ...props }: ButtonLinkProps) {
  const classes = [styles.button, styles[variant], styles.normal, className].filter(Boolean);
  return <a className={classes.join(" ")} {...props} />;
}
