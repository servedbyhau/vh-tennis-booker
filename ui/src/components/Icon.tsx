import {
  AlarmClock,
  Check,
  ChevronLeft,
  ChevronRight,
  Clock,
  Download,
  Image,
  KeyRound,
  LifeBuoy,
  ListChecks,
  Lock,
  Pencil,
  Phone,
  Plus,
  StickyNote,
  Trash2,
  UserRound,
  X,
  type LucideIcon,
} from "lucide-react";
import styles from "./Icon.module.css";

/** The drawings the app uses, all of one set (Lucide), by what they stand for here. */
const DRAWINGS = {
  /** A time set ahead, such as the wake time or a run on schedule. */
  clock: Clock,
  /** Someone: a customer, who speaks for them, or a run started by hand. */
  person: UserRound,
  /** How to reach someone. */
  phone: Phone,
  /** Something written down. */
  note: StickyNote,
  /** A login. */
  key: KeyRound,
  /** Something that opens as a picture. */
  picture: Image,
  /** Something locked, or kept to itself. */
  lock: Lock,
  /** Tasks to tick. */
  tasks: ListChecks,
  /** What happens by itself every morning. */
  alarm: AlarmClock,
  /** What to do when something goes wrong. */
  help: LifeBuoy,
  add: Plus,
  edit: Pencil,
  remove: Trash2,
  /** Agree, keep what was typed. */
  check: Check,
  /** Close what is open, give it up. */
  close: X,
  /** Save as a file. */
  save: Download,
  /** The one before, the one after. */
  back: ChevronLeft,
  forward: ChevronRight,
} as const satisfies Record<string, LucideIcon>;

export type IconName = keyof typeof DRAWINGS;

/**
 * A small icon in the colour of the text around it, sized to it. Screen readers skip it: it
 * only adds to the words next to it, and a button of an icon alone has a label of its own.
 */
export function Icon({ name }: { name: IconName }) {
  const Drawing = DRAWINGS[name];
  return <Drawing className={styles.icon} aria-hidden="true" focusable="false" />;
}
