import styles from "./Icon.module.css";

/** Line drawings on a 16-unit grid, in the colour of the text around them. */
const PATHS = {
  /** A clock: a time set ahead, such as the wake time or a run on schedule. */
  clock: "M8 2.5a5.5 5.5 0 1 0 0 11a5.5 5.5 0 1 0 0-11zM8 5v3.25l2 1.25",
  /** A person: something someone started by hand. */
  person: "M8 2.5a2.5 2.5 0 1 0 0 5a2.5 2.5 0 1 0 0-5zM3 13.5c.7-2.4 2.6-3.5 5-3.5s4.3 1.1 5 3.5",
  /** A picture: something that opens as one. */
  picture:
    "M2.5 3h11v10h-11zM2.5 11l3.2-3.2l2.6 2.6l2-2l3.2 3.2M10.6 5.2a.9 .9 0 1 0 0 1.8a.9 .9 0 1 0 0-1.8z",
} as const;

export type IconName = keyof typeof PATHS;

/**
 * A small icon before a word or a value, sized to the text. It only adds to the words next
 * to it, so screen readers skip it.
 */
export function Icon({ name }: { name: IconName }) {
  return (
    <svg className={styles.icon} viewBox="0 0 16 16" aria-hidden="true" focusable="false">
      <path d={PATHS[name]} />
    </svg>
  );
}
