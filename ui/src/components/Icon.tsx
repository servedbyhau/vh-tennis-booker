import {
  AlarmClock,
  AppWindow,
  ArrowRight,
  Bell,
  CalendarX,
  Check,
  ChevronsUpDown,
  ChevronLeft,
  ChevronRight,
  Clock,
  Copy,
  Download,
  HardDriveDownload,
  Image,
  KeyRound,
  LifeBuoy,
  ListChecks,
  Lock,
  RotateCw,
  Search,
  MonitorSmartphone,
  Pencil,
  Phone,
  Play,
  Plug,
  Plus,
  StickyNote,
  Trash2,
  Upload,
  UserRound,
  UserRoundX,
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
  /** The Windows notification. */
  bell: Bell,
  /** The Vinhomes app installed from a file. */
  install: HardDriveDownload,
  /** A file to choose and send. */
  upload: Upload,
  /** The PC kept on while plugged in. */
  power: Plug,
  /** A MuMu instance. */
  machine: MonitorSmartphone,
  /** Start something now. */
  play: Play,
  /** What to do when something goes wrong. */
  help: LifeBuoy,
  add: Plus,
  edit: Pencil,
  remove: Trash2,
  /** A ticket to cancel. */
  cancel: CalendarX,
  /** Read again in the app. */
  refresh: RotateCw,
  /** A machine's MuMu window. */
  window: AppWindow,
  /** Agree, keep what was typed. */
  check: Check,
  /** Close what is open, give it up. */
  close: X,
  /** Find among many. */
  search: Search,
  /** Copy, to paste elsewhere. */
  copy: Copy,
  /** Save as a file. */
  save: Download,
  /** Open the list under it, to choose another. */
  choose: ChevronsUpDown,
  /** Nothing chosen. */
  none: UserRoundX,
  /** Go to another page. */
  go: ArrowRight,
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
