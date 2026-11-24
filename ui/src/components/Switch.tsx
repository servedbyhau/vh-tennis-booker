import styles from "./Switch.module.css";

interface SwitchProps {
  /** What the switch turns on and off; screen readers announce it with the state. */
  label: string;
  checked: boolean;
  onChange: (checked: boolean) => void;
  disabled?: boolean;
}

/** An on/off switch: a track with a knob, at the right of it and blue while on. */
export function Switch({ label, checked, onChange, disabled }: SwitchProps) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={label}
      disabled={disabled}
      className={styles.switch}
      onClick={() => onChange(!checked)}
    >
      <span aria-hidden="true" className={styles.knob} />
    </button>
  );
}
