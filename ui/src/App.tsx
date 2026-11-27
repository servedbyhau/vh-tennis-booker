import { useTranslation } from "react-i18next";
import { Outlet, useMatch } from "react-router";
import styles from "./App.module.css";
import { SiteHeader } from "./components/SiteHeader";
import { paths } from "./paths";

/**
 * Lay out every screen: the header, then the current screen in the main area. The
 * pages of the header fill the window; the not-found and error pages make one centred
 * column.
 */
export function App() {
  const { t } = useTranslation();
  const booking = useMatch(paths.overview) !== null;
  const setup = useMatch(paths.setup) !== null;
  const management = useMatch(`${paths.management}/*`) !== null;
  const fill = booking || setup || management;
  return (
    <div className={fill ? `${styles.page} ${styles.fill}` : styles.page}>
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
