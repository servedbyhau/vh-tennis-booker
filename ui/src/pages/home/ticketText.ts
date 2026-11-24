/** The words a ticket is listed and shown under. */
import type { TFunction } from "i18next";
import type { RunSummary } from "../../api/types";
import type { Machine } from "../../machines";

/**
 * Name the machine of MuMu instance `device` as its tab does ("Máy 2"); one the ticket has no
 * tab for any more is named by its instance ("MuMu 5").
 */
export function machineName(t: TFunction, machines: readonly Machine[], device: number): string {
  const machine = machines.find((item) => item.mumuIndex === device);
  return machine === undefined
    ? t("pages.ticket.mumuName", { index: device })
    : t("pages.ticket.instanceName", { number: machine.place + 1 });
}

/**
 * Say whose account a run or a ticket is of, "Anh An · Căn A"; `null` while it is not known, as
 * on a machine without a chosen account.
 */
export function holderText({
  customer,
  account,
}: Pick<RunSummary, "customer" | "account">): string | null {
  return customer === null ? null : [customer, account].filter(Boolean).join(" · ");
}
