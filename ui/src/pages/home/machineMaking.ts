import { useQueryClient } from "@tanstack/react-query";
import { useEffect } from "react";
import { useTranslation } from "react-i18next";
import { errorMessage } from "../../api/errors";
import { useStartNewMachine } from "../../api/mutations";
import { queryKeys, useNewMachineTask } from "../../api/queries";

/** The exit codes of `court-booker new-machine` that have words of their own. */
const FAILURES = ["1", "2", "3", "5"] as const;

/**
 * A new machine's MuMu instance made from here: how it goes, read every 2 s, and how it ended.
 * Once made, the MuMu instances are read again, so the machine shows as one there is.
 */
export function useNewMachine() {
  const { t } = useTranslation();
  const cache = useQueryClient();
  const task = useNewMachineTask().data;
  const start = useStartNewMachine();
  const running = task?.running === true || start.isPending;
  const ended = start.isSuccess && task !== undefined && !task.running;

  useEffect(() => {
    if (ended) {
      void cache.invalidateQueries({ queryKey: queryKeys.mumuInstances });
      void cache.invalidateQueries({ queryKey: queryKeys.overview });
      void cache.invalidateQueries({ queryKey: queryKeys.setup });
    }
  }, [ended, cache]);

  let text: string | null = null;
  let failed = false;
  if (start.isError) {
    text = errorMessage(t, start.error);
    failed = true;
  } else if (running) {
    text = t("pages.setup.machine.running");
  } else if (ended) {
    const exit = String(task.exit_code);
    failed = task.exit_code !== 0;
    text = failed
      ? t(`pages.setup.machine.failed.${FAILURES.find((known) => known === exit) ?? "other"}`)
      : t("pages.setup.machine.done");
  }
  return { text, failed, running, make: () => start.mutate() };
}
