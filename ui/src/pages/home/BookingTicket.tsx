import { useState } from "react";
import { useTranslation } from "react-i18next";
import { errorMessage } from "../../api/errors";
import { useSaveSettings } from "../../api/mutations";
import { useAccounts, useSettings } from "../../api/queries";
import type { AccountSubdivision, Overview, ScheduleState, Settings } from "../../api/types";
import {
  courtChoices,
  firstCourt,
  inSubdivision,
  isSport,
  MAX_SLOTS,
  SUBDIVISIONS,
  shownSubdivision,
  slotChoices,
  sportChoices,
  toggleSlot,
} from "../../booking";
import { Icon } from "../../components/Icon";
import { Overline } from "../../components/Overline";
import { QueryView } from "../../components/QueryView";
import { localToday } from "../../format";
import { machineAt, useMachines } from "../../machines";
import { clashes } from "../../readiness";
import { useFormat } from "../../useFormat";
import styles from "./BookingTicket.module.css";
import { MachineBar } from "./MachineBar";
import { TicketFrame } from "./TicketFrame";

/** The slots sit in rows of this many: the six of the morning, then the seven after. */
const GRID_COLUMNS = 7;

/** What one MuMu instance books: the top of the settings, or one of their instances. */
type Booking = Pick<Settings, "mumu_index" | "slots" | "subdivision" | "sport" | "court">;

/** Return the subdivision the account of MuMu instance `index` told last, if any. */
function toldBy(accounts: readonly AccountSubdivision[] | undefined, index: number) {
  return accounts?.find((account) => account.device === index)?.subdivision;
}

/** Return what instance `index` books (0: the top of the settings), the last if it is gone. */
function bookingOf(settings: Settings, index: number): { index: number; booking: Booking } {
  const all = [settings, ...settings.instances];
  const place = Math.min(index, all.length - 1);
  return { index: place, booking: all[place] ?? settings };
}

/** Return the settings with ``change`` made to instance ``index`` (0: the top). */
function changed(settings: Settings, index: number, change: Partial<Booking>): Settings {
  if (index === 0) {
    return { ...settings, ...change };
  }
  const instances = settings.instances.map((instance, place) =>
    place === index - 1 ? { ...instance, ...change } : instance,
  );
  return { ...settings, instances };
}

type SaveSettings = ReturnType<typeof useSaveSettings>;

/** Return the settings to show: while a save is on its way, what it saves. */
function shownSettings(saved: Settings, save: SaveSettings): Settings {
  return save.isPending && save.variables !== undefined ? save.variables : saved;
}

interface NextBookingProps {
  schedule: ScheduleState;
  /** What the choices below hold, `undefined` until the settings have loaded. */
  booking: Booking | undefined;
}

/**
 * The top of the ticket shows what is set, and only that: the play day (always two days after
 * the start) and the court side by side, and the slots in booking order (the choices below
 * number them) on a row of their own, as the choices below hold them; the rows stay put whatever
 * the court's name. While the daily switch is off a line says that nothing is booked.
 */
function NextBooking({ schedule, booking }: NextBookingProps) {
  const { t } = useTranslation();
  const f = useFormat();
  const when = f.when(schedule.next_start, localToday());
  return (
    <>
      <Overline as="h2" id="next-title">
        {t("pages.ticket.title")}
      </Overline>
      <dl className={schedule.enabled ? styles.summary : `${styles.summary} ${styles.pale}`}>
        <div className={styles.field}>
          <Overline as="dt">{t("pages.ticket.day")}</Overline>
          <dd>{f.shortDay(schedule.next_play_date)}</dd>
        </div>
        <div className={styles.field}>
          <Overline as="dt">{t("pages.ticket.court")}</Overline>
          <dd>{booking === undefined ? "–" : f.court(booking.court)}</dd>
        </div>
        <div className={`${styles.field} ${styles.slotsField}`}>
          <Overline as="dt">{t("pages.ticket.chosenSlots")}</Overline>
          <dd className={styles.chosen}>
            {booking === undefined
              ? "–"
              : booking.slots.map((slot) => (
                  <span key={slot} className={styles.chosenSlot}>
                    {f.slot(slot)}
                  </span>
                ))}
          </dd>
        </div>
      </dl>
      {!schedule.enabled && (
        <p className={styles.plan}>
          <Icon name="clock" />
          <strong>{t("pages.ticket.offTitle")}</strong> {t("pages.ticket.offLine", { when })}
        </p>
      )}
    </>
  );
}

interface ChoicesProps {
  saved: Settings;
  save: SaveSettings;
  /** The subdivision each account told last, `undefined` until read. */
  accounts: readonly AccountSubdivision[] | undefined;
  /** Where the choices shown are in the settings (0: the top, then each instance). */
  instance: number;
}

/**
 * The subdivision, sport, court and slots to book, for each MuMu instance when several book
 * side by side, each with its own account. Each press saves at once: the whole settings go
 * back as they came with the one change, so the developer's values stay; another sport takes
 * its first court, another subdivision keeps the sport if it has it. Presses wait while a save
 * is on its way, so two saves never cross. The subdivision follows the account until one is
 * pressed.
 */
function Choices({ saved, save, accounts, instance }: ChoicesProps) {
  const { t } = useTranslation();
  const f = useFormat();
  const [warning, setWarning] = useState<string | null>(null);
  const busy = save.isPending;
  const settings = shownSettings(saved, save);
  const { index, booking: shown } = bookingOf(settings, instance);
  const { booking: own } = bookingOf(saved, index);
  const full = shown.slots.length >= MAX_SLOTS;
  const told = toldBy(accounts, shown.mumu_index);
  const subdivision = shownSubdivision(shown.subdivision, told);
  const byAccount = shown.subdivision === "" && told !== undefined;
  const machines = useMachines();
  const place = machines.find((machine) => machine.entry === index)?.place;
  // As the choices hold it: told at the press that makes two machines book the same.
  const clash = clashes(settings, machines).find(
    ({ places }) => place !== undefined && places.includes(place),
  );

  function choose(change: Partial<Booking>) {
    if (busy) {
      return;
    }
    setWarning(null);
    save.mutate(changed(saved, index, change));
  }

  function toggle(slot: string) {
    if (busy) {
      return;
    }
    const chosen = shown.slots.includes(slot);
    if (chosen && shown.slots.length === 1) {
      setWarning(t("pages.ticket.oneSlot"));
    } else if (!chosen && full) {
      setWarning(t("pages.ticket.full", { max: MAX_SLOTS }));
    } else {
      choose({ slots: toggleSlot(shown.slots, slot) });
    }
  }

  let note = <span className={styles.note}>{t("pages.ticket.pressToSave")}</span>;
  if (warning !== null) {
    note = <span className={styles.warning}>{warning}</span>;
  } else if (save.isError) {
    note = <span className={styles.warning}>{errorMessage(t, save.error)}</span>;
  } else if (clash !== undefined) {
    note = (
      <span className={styles.warning}>
        {t("pages.ticket.clash", {
          machines: clash.places
            .filter((other) => other !== place)
            .map((other) => other + 1)
            .join(", "),
          slot: f.slot(clash.slot),
        })}
      </span>
    );
  } else if (busy) {
    note = <span className={styles.note}>{t("pages.ticket.saving")}</span>;
  } else if (save.isSuccess) {
    note = <span className={styles.note}>{t("pages.ticket.saved")}</span>;
  }

  // A court set by hand stays a choice, but not under another sport on its way.
  const courts = courtChoices(
    subdivision,
    shown.sport,
    own.sport === shown.sport ? own.court : shown.court,
  );
  const { morning, afternoon } = slotChoices(shown.slots);
  // The morning row keeps its empty places, so the afternoon starts a row of its own.
  const gaps = (GRID_COLUMNS - (morning.length % GRID_COLUMNS)) % GRID_COLUMNS;
  const cells = [...morning, ...Array<null>(gaps).fill(null), ...afternoon];

  return (
    <div aria-busy={busy} className={styles.choices}>
      <div role="group" aria-labelledby="subdivision-label" className={styles.group}>
        <div className={styles.slotsHead}>
          <Overline as="span" id="subdivision-label">
            {t("pages.ticket.subdivision")}
          </Overline>
          {byAccount && <span className={styles.note}>{t("pages.ticket.byAccount")}</span>}
        </div>
        <div className={styles.buttons}>
          {SUBDIVISIONS.map((item) => {
            const on = subdivision.id === item.id;
            return (
              <button
                key={item.id}
                type="button"
                aria-pressed={on}
                aria-disabled={busy || undefined}
                className={`${styles.choice} ${styles.court}`}
                onClick={() =>
                  shown.subdivision !== item.id && choose(inSubdivision(item, shown.sport))
                }
              >
                {item.name}
              </button>
            );
          })}
        </div>
      </div>

      <div role="group" aria-labelledby="sport-label" className={styles.group}>
        <Overline as="span" id="sport-label">
          {t("pages.ticket.sport")}
        </Overline>
        <div className={`${styles.buttons} ${styles.wrap}`}>
          {sportChoices(subdivision, shown.sport).map((sport) => {
            const on = shown.sport === sport;
            return (
              <button
                key={sport}
                type="button"
                aria-pressed={on}
                aria-disabled={busy || undefined}
                className={`${styles.choice} ${styles.sport}`}
                onClick={() => !on && choose({ sport, court: firstCourt(subdivision, sport) })}
              >
                {isSport(sport) ? t(`sports.${sport}`) : sport}
              </button>
            );
          })}
        </div>
      </div>

      <div role="group" aria-labelledby="court-label" className={styles.group}>
        <Overline as="span" id="court-label">
          {t("pages.ticket.court")}
        </Overline>
        <div className={`${styles.buttons} ${styles.wrap}`}>
          {courts.map((court) => {
            const on = shown.court === court;
            return (
              <button
                key={court}
                type="button"
                aria-pressed={on}
                aria-disabled={busy || undefined}
                className={`${styles.choice} ${styles.court}`}
                onClick={() => !on && choose({ court })}
              >
                {f.courtLabel(court)}
              </button>
            );
          })}
        </div>
      </div>

      <div role="group" aria-labelledby="slots-label" className={styles.group}>
        <div className={styles.slotsHead}>
          <Overline as="span" id="slots-label">
            {t("pages.ticket.slots", { max: MAX_SLOTS })}
          </Overline>
          <span aria-live="polite">{note}</span>
        </div>
        <div className={styles.grid}>
          {cells.map((slot, index) => {
            if (slot === null) {
              return <span key={`gap-${index}`} aria-hidden="true" />;
            }
            const order = shown.slots.indexOf(slot) + 1;
            const blocked = order === 0 && full;
            return (
              <button
                key={slot}
                type="button"
                aria-pressed={order > 0}
                aria-disabled={busy || blocked || undefined}
                aria-label={
                  order > 0 ? t("pages.ticket.slot", { slot: f.slot(slot), order }) : undefined
                }
                className={blocked ? `${styles.slot} ${styles.blocked}` : styles.slot}
                onClick={() => toggle(slot)}
              >
                {f.slot(slot)}
                {order > 0 && (
                  <span aria-hidden="true" className={styles.order}>
                    {order}
                  </span>
                )}
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
}

interface BookingTicketProps {
  overview: Overview;
  /** The machine shown (0: the first), chosen on the machines' tabs on top. */
  machine: number;
  onMachine: (place: number) => void;
}

/**
 * The next booking as a ticket in two parts: on top what is set (the play day, court and
 * slots), under the perforation the sport, court and slots to choose, saved on each press. A
 * press shows on top at once, as the save goes out.
 */
export function BookingTicket({ overview, machine, onMachine }: BookingTicketProps) {
  const { t } = useTranslation();
  const settings = useSettings();
  const accounts = useAccounts();
  const save = useSaveSettings();
  const machines = useMachines();
  const shown = machineAt(machines, machine);
  const { entry } = shown;
  const { schedule } = overview;
  const booking =
    settings.data === undefined || entry === null
      ? undefined
      : bookingOf(shownSettings(settings.data, save), entry).booking;
  return (
    <TicketFrame
      aria-labelledby="next-title"
      tabs={<MachineBar machines={machines} machine={machine} onMachine={onMachine} />}
      top={<NextBooking schedule={schedule} booking={booking} />}
      contained
    >
      <div className={styles.scroll}>
        {entry === null ? (
          <p className={styles.off}>{t("pages.ticket.useOff", { number: shown.place + 1 })}</p>
        ) : (
          <QueryView query={settings}>
            {(saved) => (
              // Keyed by the machine, so a warning of one is gone on another.
              <Choices
                key={shown.key}
                saved={saved}
                save={save}
                accounts={accounts.data}
                instance={entry}
              />
            )}
          </QueryView>
        )}
      </div>
    </TicketFrame>
  );
}
