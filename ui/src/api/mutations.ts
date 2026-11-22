import { useMutation, useQueryClient } from "@tanstack/react-query";
import type { Language } from "../i18n";
import type { AccountChange, CustomerFields, NewAccount } from "./types";
import {
  addAccount,
  addCustomer,
  attachAccount,
  changeAccount,
  changeCustomer,
  detachAccount,
  getNotifications,
  removeAccount,
  removeCustomer,
  saveNotifications,
  saveSettings,
  startDryRun,
  switchInstance,
  switchSchedule,
} from "./endpoints";
import { queryKeys } from "./queries";

/** Save the booking settings; the overview shows the next booking with them. */
export function useSaveSettings() {
  const cache = useQueryClient();
  return useMutation({
    mutationFn: saveSettings,
    onSuccess: async (settings) => {
      cache.setQueryData(queryKeys.settings, settings);
      await Promise.all([
        cache.invalidateQueries({ queryKey: queryKeys.overview }),
        cache.invalidateQueries({ queryKey: ["events"] }),
      ]);
    },
  });
}

/** Switch a machine on or off: its `[[instances]]` table is added or removed. */
export function useSwitchInstance() {
  const cache = useQueryClient();
  return useMutation({
    mutationFn: ({ mumuIndex, enabled }: { mumuIndex: number; enabled: boolean }) =>
      switchInstance(mumuIndex, enabled),
    onSuccess: async (settings) => {
      cache.setQueryData(queryKeys.settings, settings);
      await cache.invalidateQueries({ queryKey: ["events"] });
    },
  });
}

/** Save the notification settings; the activity log shows the save. */
export function useSaveNotifications() {
  const cache = useQueryClient();
  return useMutation({
    mutationFn: saveNotifications,
    onSuccess: async (settings) => {
      cache.setQueryData(queryKeys.notifications, settings);
      await cache.invalidateQueries({ queryKey: ["events"] });
    },
  });
}

/**
 * Give the notification the language the user just chose for the UI, saving only when it
 * differs. A failure leaves the UI in its new language and the notification in the old.
 */
export function useSaveNotificationLanguage() {
  const cache = useQueryClient();
  return useMutation({
    mutationFn: async (language: Language) => {
      const saved = await cache.fetchQuery({
        queryKey: queryKeys.notifications,
        queryFn: getNotifications,
      });
      return saved.language === language ? saved : saveNotifications({ ...saved, language });
    },
    onSuccess: async (settings) => {
      cache.setQueryData(queryKeys.notifications, settings);
      await cache.invalidateQueries({ queryKey: ["events"] });
    },
  });
}

/** A change of the customers or their accounts; the list is read again after it, failed or not. */
function useCustomerChange<Variables, Result>(
  mutationFn: (variables: Variables) => Promise<Result>,
) {
  const cache = useQueryClient();
  return useMutation({
    mutationFn,
    onSettled: () => cache.invalidateQueries({ queryKey: queryKeys.customers }),
  });
}

/** Add a customer without accounts. */
export function useAddCustomer() {
  return useCustomerChange((fields: CustomerFields) => addCustomer(fields));
}

/** Change a customer's name and note. */
export function useChangeCustomer() {
  return useCustomerChange(({ id, fields }: { id: string; fields: CustomerFields }) =>
    changeCustomer(id, fields),
  );
}

/** Remove a customer with their accounts. */
export function useRemoveCustomer() {
  return useCustomerChange((id: string) => removeCustomer(id));
}

/** Add an account to a customer. */
export function useAddAccount() {
  return useCustomerChange(({ customerId, account }: { customerId: string; account: NewAccount }) =>
    addAccount(customerId, account),
  );
}

/** Change an account's label and, unless `null`, its password. */
export function useChangeAccount() {
  return useCustomerChange(({ id, fields }: { id: string; fields: AccountChange }) =>
    changeAccount(id, fields),
  );
}

/** Remove an account. */
export function useRemoveAccount() {
  return useCustomerChange((id: string) => removeAccount(id));
}

/** Attach an account to a machine, in place of the one it had. */
export function useAttachAccount() {
  return useCustomerChange(({ mumuIndex, accountId }: { mumuIndex: number; accountId: string }) =>
    attachAccount(mumuIndex, accountId),
  );
}

/** Attach no account to a machine. */
export function useDetachAccount() {
  return useCustomerChange((mumuIndex: number) => detachAccount(mumuIndex));
}

/** Switch the daily schedule on or off; the overview shows its new state. */
export function useSwitchSchedule() {
  const cache = useQueryClient();
  return useMutation({
    mutationFn: switchSchedule,
    onSuccess: async () => {
      await Promise.all([
        cache.invalidateQueries({ queryKey: queryKeys.overview }),
        cache.invalidateQueries({ queryKey: ["events"] }),
      ]);
    },
  });
}

/** Start a dry run; the overview shows it running, the live feed brings its steps. */
export function useStartDryRun() {
  const cache = useQueryClient();
  return useMutation({
    mutationFn: startDryRun,
    onSuccess: () => cache.invalidateQueries({ queryKey: queryKeys.overview }),
  });
}
