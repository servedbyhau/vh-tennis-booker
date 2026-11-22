import { useId } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router";
import { useCustomers } from "../../api/queries";
import { QueryView } from "../../components/QueryView";
import { accountOn } from "../../machines";
import { paths } from "../../paths";
import styles from "./SetupTab.module.css";

/** The account a machine books with, in a line; the accounts page changes it. */
export function MachineAccount({ mumuIndex }: { mumuIndex: number }) {
  const { t } = useTranslation();
  const id = useId();
  const customers = useCustomers();
  return (
    <section aria-labelledby={`${id}-title`}>
      <h3 id={`${id}-title`} className={styles.heading}>
        {t("pages.setup.account.title")}
      </h3>
      <QueryView query={customers}>
        {(list) => {
          const found = accountOn(list, mumuIndex);
          return (
            <p className={styles.account}>
              {found === null
                ? t("pages.setup.account.none")
                : [found.customer.name, found.account.phone, found.account.label]
                    .filter(Boolean)
                    .join(" · ")}
            </p>
          );
        }}
      </QueryView>
      <p className={styles.note}>
        <Link to={paths.accounts}>{t("pages.setup.account.manage")}</Link>
      </p>
    </section>
  );
}
