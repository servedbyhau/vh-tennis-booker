import { useTranslation } from "react-i18next";
import { Outlet, useMatch } from "react-router";
import styles from "./App.module.css";
import { SiteHeader } from "./components/SiteHeader";
import { paths } from "./paths";

/**
 * Lay out every screen: the header, then the current screen in the main area. The home
 * screen fills the window, the accounts page takes its width; the not-found and error pages
 * make one centred column.
 */
export function App() {
  const { t } = useTranslation();
  const home = useMatch(paths.overview) !== null;
  const accounts = useMatch(paths.accounts) !== null;
  const layout = [styles.page, home && styles.fill, accounts && styles.wide];
  return (
    <div className={layout.filter(Boolean).join(" ")}>
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
