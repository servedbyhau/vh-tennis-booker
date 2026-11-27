import { useTranslation } from "react-i18next";
import { NavLink } from "react-router";
import { useOverview } from "../api/queries";
import { paths } from "../paths";
import { LanguageSwitch } from "./LanguageSwitch";
import styles from "./SiteHeader.module.css";
import { StatusLine } from "./StatusLine";
import { UpdateButton } from "./UpdateButton";

/**
 * Show the app's name with the installed version, the pages in the middle, the status line, the update button (in the desktop window, when a
 * newer version is out) and the language switch.
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
      <nav aria-label={t("nav.label")} className={styles.nav}>
        <NavLink to={paths.overview} end className={styles.link}>
          {t("nav.booking")}
        </NavLink>
        <NavLink to={paths.setup} className={styles.link}>
          {t("nav.setup")}
        </NavLink>
        <NavLink to={paths.management} className={styles.link}>
          {t("nav.management")}
        </NavLink>
      </nav>
      <div className={styles.end}>
        {overview.data && <StatusLine overview={overview.data} />}
        <UpdateButton />
        <LanguageSwitch />
      </div>
    </header>
  );
}
