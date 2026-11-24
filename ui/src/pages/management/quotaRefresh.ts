import { useQueryClient } from "@tanstack/react-query";
import { useEffect } from "react";
import { useTranslation } from "react-i18next";
import { errorMessage } from "../../api/errors";
import { useReadQuota } from "../../api/mutations";
import { queryKeys, useQuotaTask } from "../../api/queries";

/** The exit codes of `court-booker quota` that have words of their own. */
const QUOTA_FAILURES = ["1", "2", "3", "4", "5"] as const;

/**
 * The quota read again of the account on machine `device` (none without a machine): how the one
 * started from here goes and how it ended, read every 2 s; the customers are read again once over.
 */
export function useQuotaRefresh(device: number | null) {
  const { t } = useTranslation();
  const cache = useQueryClient();
  const state = useQuotaTask();
  const start = useReadQuota();
  const mine = device !== null && state.data?.machine === device ? state.data : undefined;
  const started = device !== null && start.data?.machine === device;
  const ended = started && mine !== undefined && !mine.running;

  useEffect(() => {
    if (ended) {
      void cache.invalidateQueries({ queryKey: queryKeys.customers });
      void cache.invalidateQueries({ queryKey: queryKeys.overview });
    }
  }, [ended, cache]);

  let text: string | null = null;
  if (start.isError && start.variables === device) {
    text = errorMessage(t, start.error);
  } else if (mine?.running === true || (start.isPending && start.variables === device)) {
    text = t("quota.refresh.running");
  } else if (ended) {
    const exit = String(mine.exit_code);
    text =
      mine.exit_code === 0
        ? t("quota.refresh.done")
        : t(`quota.refresh.failed.${QUOTA_FAILURES.find((known) => known === exit) ?? "other"}`);
  }
  return {
    text,
    running: mine?.running === true || start.isPending,
    read: () => {
      if (device !== null) {
        start.mutate(device);
      }
    },
  };
}
