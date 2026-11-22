import { useTranslation } from "react-i18next";
import { Outlet, useMatch } from "react-router";
import styles from "./App.module.css";
import { SiteHeader } from "./components/SiteHeader";
import { paths } from "./paths";

/**
 * Lay out every screen: the header, then the current screen in the main area. The
 * booking and the customers fill the window; the not-found and error pages make one centred
 * column.
 */
export function App() {
  const { t } = useTranslation();
  const booking = useMatch(paths.overview) !== null;
  const customers = useMatch(paths.customers) !== null;
  return (
    <div className={booking || customers ? `${styles.page} ${styles.fill}` : styles.page}>
      <a className={styles.skipLink} href="#main">
        {t("app.skipToContent")}
      </a>
      <SiteHeader />
      <main id="main" tabIndex={-1} className={styles.main}>
        <Outlet />
      </main>
    </div>
  );
}
