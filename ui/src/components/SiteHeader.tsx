import { useTranslation } from "react-i18next";
import { useOverview } from "../api/queries";
import { LanguageSwitch } from "./LanguageSwitch";
import styles from "./SiteHeader.module.css";
import { StatusLine } from "./StatusLine";
import { UpdateButton } from "./UpdateButton";

/**
 * Show the app's name with the installed version, the status line, the update button (in the
 * desktop window, when a newer version is out) and the language switch, ruled off in ink.
 */
export function SiteHeader() {
  const { t } = useTranslation();
  const overview = useOverview();
  const version = overview.data?.version;
  return (
    <header className={styles.header}>
      <span className={styles.brand}>
        court booker
        <span className={styles.dot} aria-hidden="true">
          .
        </span>
        {version && (
          <span className={styles.version} title={t("update.current", { version })}>
            v{version}
          </span>
        )}
      </span>
      <div className={styles.status}>
        {overview.data && <StatusLine overview={overview.data} />}
      </div>
      <UpdateButton />
      <LanguageSwitch />
    </header>
  );
}
