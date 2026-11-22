/**
 * Short words for why a slot or a run failed. The engine writes its reasons in English
 * (flow.py, runner.py); the known ones read as a few words here, the rest point to the
 * activity log, which keeps the engine's own text.
 */
import type { TFunction } from "i18next";
import type { Formatter } from "./useFormat";

type Phrase = (t: TFunction, f: Formatter, match: RegExpExecArray) => string;

/**
 * The app never reached its home screen. Runs before the saved login asked to check the login;
 * a logout is told apart since (flow.py).
 */
const NOT_READY = /check that it is logged in$|; check the app on MuMu \d+$/;

/** The reasons the engine gives, as it writes them, and their words. */
const REASONS: [RegExp, Phrase][] = [
  [/^Slot .+ is fully booked$/, (t) => t("reasons.slotFull")],
  [
    /^Court (.+) is fully booked$/,
    (t, f, match) => t("reasons.courtFull", { court: f.court(match[1] ?? "") }),
  ],
  [
    /^The app refused the booking: (.*)$/s,
    (t, _f, match) => t("reasons.refused", { message: match[1] ?? "" }),
  ],
  [/^Booking quota used up:/, (t) => t("reasons.quotaFull")],
  [/^Skipped: the booking quota is used up$/, (t) => t("reasons.quotaSkipped")],
  [/^Outcome unknown:/, (t) => t("reasons.unknown")],
  [/ not open after \d+ attempt/, (t) => t("reasons.notOpen")],
  [/ but the next screen did not appear$/, (t) => t("reasons.stuck")],
  [/^Another run is in progress/, (t) => t("reasons.busy")],
  [/^The app is logged out/, (t) => t("reasons.loggedOut")],
  [
    /^The app refused the saved login: (.*); save it again/s,
    (t, _f, match) => t("reasons.loginRefused", { message: match[1] ?? "" }),
  ],
  [
    /stayed disabled after typing the login$|\(\d+ tap\(s\)\); check the app$|^The app logged out again/,
    (t) => t("reasons.loginFailed"),
  ],
  [
    /after logging in with the saved login|no earlier run saw the saved login/,
    (t) => t("reasons.wrongAccount"),
  ],
  [NOT_READY, (t) => t("reasons.notReady")],
  [/ is not installed on .+; install it$/, (t) => t("reasons.appMissing")],
];

/** Return a few words for an engine reason; an unknown one says to see the activity log. */
export function failureReason(t: TFunction, f: Formatter, reason: string | null): string {
  for (const [pattern, phrase] of REASONS) {
    const match = reason === null ? null : pattern.exec(reason);
    if (match !== null) {
      return phrase(t, f, match);
    }
  }
  return t("reasons.other");
}
