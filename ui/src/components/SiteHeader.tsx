import { useOverview } from "../api/queries";
import { LanguageSwitch } from "./LanguageSwitch";
import styles from "./SiteHeader.module.css";
import { StatusLine } from "./StatusLine";
import { UpdateButton } from "./UpdateButton";

/**
 * Show the app's name, the status line, the update button (in the desktop window, when a newer
 * version is out) and the language switch, ruled off in ink.
 */
export function SiteHeader() {
  const overview = useOverview();
  return (
    <header className={styles.header}>
      <span className={styles.brand}>
        court booker
        <span className={styles.dot} aria-hidden="true">
          .
        </span>
      </span>
      <div className={styles.status}>
        {overview.data && <StatusLine overview={overview.data} />}
      </div>
      <UpdateButton />
      <LanguageSwitch />
    </header>
  );
}
