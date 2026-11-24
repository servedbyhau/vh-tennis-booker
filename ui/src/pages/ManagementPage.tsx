import { useState } from "react";
import { useTranslation } from "react-i18next";
import { NavLink, Outlet } from "react-router";
import { paths } from "../paths";
import styles from "./ManagementPage.module.css";
import type { ManagementState } from "./management/state";

const SECTIONS = [
  { to: paths.management, title: "pages.board.title" },
  { to: paths.machines, title: "pages.machines.title" },
  { to: paths.customers, title: "pages.customers.title" },
  { to: paths.tickets, title: "pages.tickets.title" },
  { to: paths.quota, title: "pages.quota.title" },
  { to: paths.money, title: "pages.money.title" },
  { to: paths.history, title: "pages.history.title" },
  { to: paths.stats, title: "pages.stats.title" },
] as const;

/**
 * The management, apart from the booking: the overview first, then the machines, the customers,
 * the tickets and the History.
 */
export function ManagementPage() {
  const { t } = useTranslation();
  const [withDry, setWithDry] = useState(false);
  const [customer, setCustomer] = useState<string | null>(null);
  const state: ManagementState = {
    withDry,
    onWithDry: setWithDry,
    customer,
    onCustomer: setCustomer,
  };
  return (
    <>
      <h1 className="visually-hidden">{t("nav.management")}</h1>
      <nav aria-label={t("pages.management.sections")} className={styles.sections}>
        {SECTIONS.map(({ to, title }) => (
          <NavLink key={to} to={to} end className={styles.section}>
            {t(title)}
          </NavLink>
        ))}
      </nav>
      <Outlet context={state} />
    </>
  );
}
