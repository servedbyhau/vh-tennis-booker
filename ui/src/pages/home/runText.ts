/** The words a run is listed and shown under in the History. */
import type { TFunction } from "i18next";
import type { RunSummary } from "../../api/types";
import { localToday, relativeDay } from "../../format";
import { runOrigin } from "../../runs";
import type { Formatter } from "../../useFormat";
import { holderText } from "./ticketText";

type RunFacts = Pick<RunSummary, "play_date" | "court" | "started_at">;

/** Name a run by what it booked ("Chơi Thứ Hai 26/10 · S6"), or by its day before a date. */
export function runTitle(t: TFunction, f: Formatter, run: RunFacts): string {
  return run.play_date !== null && run.court !== null
    ? t("pages.history.play", { day: f.day(run.play_date), court: f.court(run.court) })
    : t("pages.history.runOn", { day: f.day(run.started_at) });
}

/** Name a run in a list row: "T2 26/10 · S6", or the day it ran ("T2 12/10") before a date. */
export function runShortTitle(t: TFunction, f: Formatter, run: RunFacts): string {
  return run.play_date !== null && run.court !== null
    ? t("pages.history.short", { day: f.shortDay(run.play_date), court: f.court(run.court) })
    : f.shortDay(run.started_at);
}

/**
 * Say whose account a run booked with, else the MuMu instance of a run beside the first; empty
 * for one of the first that is not known.
 */
export function runHolder(
  t: TFunction,
  run: Pick<RunSummary, "device" | "customer" | "account">,
): string {
  return holderText(run) ?? (run.device ? t("pages.ticket.mumuName", { index: run.device }) : "");
}

/**
 * Say when and how a run went: "đặt sáng nay 24/10 · theo hẹn giờ", "chạy thử chiều hôm qua
 * 23/10". A day further away names itself already ("sáng Thứ Hai 19/10"). It ends with whose
 * account it booked with ("· Anh An · Căn A"), else with the MuMu instance of a run beside the
 * first ("· MuMu 1").
 */
export function runWhen(
  t: TFunction,
  f: Formatter,
  run: RunFacts & Pick<RunSummary, "dry_run" | "trigger" | "device" | "customer" | "account">,
  today: string = localToday(),
): string {
  const near = relativeDay(run.started_at, today) !== null;
  const when = near
    ? `${f.when(run.started_at, today)} ${f.shortDate(run.started_at)}`
    : f.when(run.started_at, today);
  const text = run.dry_run
    ? t("pages.history.dry", { when })
    : t("pages.history.booked", { when, by: runOrigin(t, run.trigger) });
  return [text, runHolder(t, run)].filter(Boolean).join(" · ");
}
