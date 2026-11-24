import { useMutation, useQueryClient } from "@tanstack/react-query";
import type { Language } from "../i18n";
import type { AccountChange, CustomerFields, NewAccount } from "./types";
import {
  addAccount,
  addCustomer,
  attachAccount,
  changeCharge,
  cancelTicket,
  changeAccount,
  changeCustomer,
  detachAccount,
  getNotifications,
  markFree,
  markPaid,
  markSent,
  openMachine,
  removeAccount,
  readQuota,
  removeCustomer,
  saveNotifications,
  savePrices,
  saveSettings,
  startDryRun,
  switchInstance,
  switchSchedule,
} from "./endpoints";
import { queryKeys } from "./queries";

/**
 * Start the cancel of a ticket in the app; how it goes is read from then on (`useCancelState`), and
 * the Overview shows the machine taken meanwhile.
 */
export function useCancelTicket() {
  const cache = useQueryClient();
  return useMutation({
    mutationFn: cancelTicket,
    onSuccess: async (state) => {
      cache.setQueryData(queryKeys.cancel, state);
      await cache.invalidateQueries({ queryKey: queryKeys.overview });
    },
  });
}

/** Start reading a machine's quota again; how it goes is read from then on (`useQuotaTask`). */
export function useReadQuota() {
  const cache = useQueryClient();
  return useMutation({
    mutationFn: readQuota,
    onSuccess: async (state) => {
      cache.setQueryData(queryKeys.quotaTask, state);
      await cache.invalidateQueries({ queryKey: queryKeys.overview });
    },
  });
}

/** Read the charges again once the money changed. */
function useMoneyChange<T>(change: (value: T) => Promise<unknown>) {
  const cache = useQueryClient();
  return useMutation({
    mutationFn: change,
    onSuccess: () => cache.invalidateQueries({ queryKey: ["charges"] }),
  });
}

/** Replace the price list; the charges not set by hand follow it. */
export function useSavePrices() {
  const cache = useQueryClient();
  return useMutation({
    mutationFn: savePrices,
    onSuccess: async (prices) => {
      cache.setQueryData(queryKeys.prices, prices);
      await cache.invalidateQueries({ queryKey: ["charges"] });
    },
  });
}

/** Mark a charge paid or not, or set its amount. */
export function useChangeCharge() {
  return useMoneyChange(changeCharge);
}

/** Mark several charges paid, or not. */
export function useMarkPaid() {
  return useMoneyChange(markPaid);
}

/** Book for a customer for free, or not. */
export function useMarkFree() {
  return useMoneyChange(markFree);
}

/** Mark a ticket sent to its customer, or not; the tickets are read again. */
export function useMarkSent() {
  const cache = useQueryClient();
  return useMutation({
    mutationFn: markSent,
    onSuccess: () => cache.invalidateQueries({ queryKey: queryKeys.tickets }),
  });
}

/** Open a machine's MuMu: launched, or its window shown. */
export function useOpenMachine() {
  return useMutation({ mutationFn: openMachine });
}

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

/** Change an account's label and, unless `null`, its phone number and password. */
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
