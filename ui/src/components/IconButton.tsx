import type { ComponentPropsWithoutRef } from "react";
import { Icon, type IconName } from "./Icon";
import styles from "./IconButton.module.css";

interface IconButtonProps extends Omit<ComponentPropsWithoutRef<"button">, "aria-label" | "title"> {
  icon: IconName;
  /** What it does: the tooltip, and what screen readers say. */
  label: string;
  /** `solid`: filled, the one main action of a part; `danger`: red, for what removes. */
  variant?: "plain" | "solid" | "danger";
}

/** A round button of an icon alone, its words in the tooltip. */
export function IconButton({
  icon,
  label,
  variant = "plain",
  className,
  ...props
}: IconButtonProps) {
  const classes = [styles.button, styles[variant], className].filter(Boolean);
  return (
    <button type="button" aria-label={label} title={label} className={classes.join(" ")} {...props}>
      <Icon name={icon} />
    </button>
  );
}
