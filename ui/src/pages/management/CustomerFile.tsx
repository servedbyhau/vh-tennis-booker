import { useState } from "react";
import { useTranslation } from "react-i18next";
import { errorMessage } from "../../api/errors";
import { useImportCustomers } from "../../api/mutations";
import type { ImportResult } from "../../api/types";
import { Button } from "../../components/Button";
import buttonStyles from "../../components/Button.module.css";
import { Icon } from "../../components/Icon";
import styles from "./CustomerFile.module.css";

/** The customers' file and its template, as the backend writes them. */
const FILE = "/api/customers/file";
const TEMPLATE = "/api/customers/file/template";
const LINK = `${buttonStyles.button} ${buttonStyles.secondary} ${buttonStyles.normal}`;

/** Why the backend leaves a row out, each worded in the language files. */
const PROBLEMS = ["no_name", "bad_phone", "twice", "taken", "no_password"] as const;

function isProblem(code: string): code is (typeof PROBLEMS)[number] {
  return (PROBLEMS as readonly string[]).includes(code);
}

/** What a file changes, a line a kind, and the rows it leaves out with why. */
function Plan({ result }: { result: ImportResult }) {
  const { t } = useTranslation();
  const lines = [
    [result.new_customers, "newCustomers"],
    [result.changed_customers, "changedCustomers"],
    [result.new_accounts, "newAccounts"],
    [result.changed_accounts, "changedAccounts"],
  ] as const;
  const shown = lines.filter(([items]) => items.length > 0);
  return (
    <div className={styles.plan}>
      {shown.length === 0 && result.problems.length === 0 && (
        <p className={styles.muted}>{t("pages.customers.file.nothing")}</p>
      )}
      {shown.length > 0 && (
        <ul className={styles.lines}>
          {shown.map(([items, key]) => (
            <li key={key}>
              <strong>{t(`pages.customers.file.${key}`, { count: items.length })}</strong>{" "}
              <span className={styles.muted}>{items.join(", ")}</span>
            </li>
          ))}
        </ul>
      )}
      {result.problems.length > 0 && (
        <>
          <p className={styles.warn}>
            {t("pages.customers.file.left", { count: result.problems.length })}
          </p>
          <ul className={styles.lines}>
            {result.problems.map((problem) => (
              <li key={problem.line} className={styles.muted}>
                {t("pages.customers.file.line", { line: problem.line })}{" "}
                {isProblem(problem.code)
                  ? t(`pages.customers.file.problems.${problem.code}`, {
                      phone: problem.phone,
                      owner: problem.owner,
                    })
                  : problem.code}
              </li>
            ))}
          </ul>
        </>
      )}
    </div>
  );
}

/**
 * The customers as an Excel file: written out (with the passwords when asked), or read back to
 * add many at once, what it changes shown first.
 */
export function CustomerFile({ onClose }: { onClose: () => void }) {
  const { t } = useTranslation();
  const [passwords, setPasswords] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const read = useImportCustomers();
  const result = read.data;
  const choose = (chosen: File | null) => {
    setFile(chosen);
    read.reset();
    if (chosen !== null) {
      read.mutate({ file: chosen, apply: false });
    }
  };
  return (
    <div className={styles.body}>
      <div className={styles.head}>
        <h2 className={styles.title}>{t("pages.customers.file.title")}</h2>
        <Button onClick={onClose}>{t("pages.customers.file.close")}</Button>
      </div>

      <section aria-labelledby="file-export" className={styles.part}>
        <h3 id="file-export" className={styles.section}>
          {t("pages.customers.file.exportTitle")}
        </h3>
        <p className={styles.muted}>{t("pages.customers.file.exportHint")}</p>
        <label className={styles.check}>
          <input
            type="checkbox"
            checked={passwords}
            onChange={(event) => setPasswords(event.target.checked)}
          />
          {t("pages.customers.file.withPasswords")}
        </label>
        {passwords && <p className={styles.warn}>{t("pages.customers.file.passwordsWarning")}</p>}
        <div className={styles.actions}>
          <a href={passwords ? `${FILE}?passwords=true` : FILE} download className={LINK}>
            <Icon name="save" /> {t("pages.customers.file.download")}
          </a>
        </div>
      </section>

      <section aria-labelledby="file-import" className={styles.part}>
        <h3 id="file-import" className={styles.section}>
          {t("pages.customers.file.importTitle")}
        </h3>
        <p className={styles.muted}>{t("pages.customers.file.importHint")}</p>
        <div className={styles.actions}>
          <a href={TEMPLATE} download className={LINK}>
            <Icon name="save" /> {t("pages.customers.file.template")}
          </a>
          <label className={LINK}>
            {t("pages.customers.file.choose")}
            <input
              type="file"
              accept=".xlsx"
              className="visually-hidden"
              onChange={(event) => choose(event.target.files?.[0] ?? null)}
            />
          </label>
          {file !== null && <span className={styles.muted}>{file.name}</span>}
        </div>
        {read.isPending && <p className={styles.muted}>{t("pages.customers.file.reading")}</p>}
        {read.isError && (
          <p role="alert" className={styles.warn}>
            {errorMessage(t, read.error)}
          </p>
        )}
        {result !== undefined && (
          <div role="status">
            {result.applied && (
              <p className={styles.done}>
                <Icon name="check" /> {t("pages.customers.file.applied")}
              </p>
            )}
            <Plan result={result} />
          </div>
        )}
        {result !== undefined && !result.applied && file !== null && (
          <div className={styles.actions}>
            <Button
              variant="primary"
              disabled={
                read.isPending ||
                result.new_customers.length +
                  result.changed_customers.length +
                  result.new_accounts.length +
                  result.changed_accounts.length ===
                  0
              }
              onClick={() => read.mutate({ file, apply: true })}
            >
              {t("pages.customers.file.apply")}
            </Button>
            <Button onClick={() => choose(null)}>{t("pages.customers.file.cancel")}</Button>
          </div>
        )}
      </section>
    </div>
  );
}
