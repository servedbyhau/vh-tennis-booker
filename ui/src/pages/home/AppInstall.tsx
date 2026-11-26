import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef } from "react";
import { useTranslation } from "react-i18next";
import { errorMessage } from "../../api/errors";
import { useStartAppInstall } from "../../api/mutations";
import { queryKeys, useAppInstallTask } from "../../api/queries";
import { IconButton } from "../../components/IconButton";
import { SetupRow } from "./SetupRow";

/** The exit codes of `court-booker install-app` that have words of their own. */
const FAILURES = ["1", "2", "3", "5"] as const;

/**
 * The Vinhomes app installed from a file the user downloaded (an APK or XAPK): the backend checks
 * that the app's own key signed it, then installs it on every MuMu instance. The row is its title
 * and a button; how it goes, read every 2 s, and how it ended show under the title.
 */
export function AppInstallRow({ running }: { running: boolean }) {
  const { t } = useTranslation();
  const cache = useQueryClient();
  const picker = useRef<HTMLInputElement>(null);
  const task = useAppInstallTask().data;
  const start = useStartAppInstall();
  const busy = task?.running === true || start.isPending;
  const ended = start.isSuccess && task !== undefined && !task.running;

  useEffect(() => {
    if (ended) {
      void cache.invalidateQueries({ queryKey: queryKeys.overview });
    }
  }, [ended, cache]);

  let text: string | undefined;
  let failed = false;
  if (start.isError) {
    text = errorMessage(t, start.error);
    failed = true;
  } else if (busy) {
    text = t("pages.setup.app.running");
  } else if (ended) {
    const exit = String(task.exit_code);
    failed = task.exit_code !== 0;
    text = failed
      ? t(`pages.setup.app.failed.${FAILURES.find((known) => known === exit) ?? "other"}`)
      : t("pages.setup.app.done");
  }
  const title = t("pages.setup.app.title");
  return (
    <SetupRow
      icon="install"
      title={title}
      hint={failed ? undefined : text}
      problem={failed ? (text ?? null) : null}
    >
      <input
        ref={picker}
        type="file"
        accept=".apk,.xapk,.apks"
        className="visually-hidden"
        tabIndex={-1}
        aria-label={t("pages.setup.app.file")}
        onChange={(event) => {
          const file = event.target.files?.[0];
          event.target.value = "";
          if (file !== undefined) {
            start.mutate(file);
          }
        }}
      />
      <IconButton
        icon="upload"
        label={t("pages.setup.app.choose")}
        disabled={running || busy}
        onClick={() => picker.current?.click()}
      />
    </SetupRow>
  );
}
