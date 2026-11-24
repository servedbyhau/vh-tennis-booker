import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import {
  addRequest,
  changeRequest,
  removeRequest,
  saveSettings,
  switchInstance,
} from "../../api/endpoints";
import { errorMessage } from "../../api/errors";
import { queryKeys, useCustomers, useRequests, useSettings } from "../../api/queries";
import type { BookingRequest, Customer, RequestFields } from "../../api/types";
import {
  courtChoices,
  firstCourt,
  SLOTS,
  sportChoices,
  SUBDIVISIONS,
  shownSubdivision,
  toggleSlot,
} from "../../booking";
import { Button } from "../../components/Button";
import { Icon } from "../../components/Icon";
import { IconButton } from "../../components/IconButton";
import { PageTitle } from "../../components/PageTitle";
import { Loading } from "../../components/States";
import { Switch } from "../../components/Switch";
import { accountOn, useMachines } from "../../machines";
import { useFormat } from "../../useFormat";
import styles from "./Board.module.css";
import { appliedTo, dayKey } from "./requests";

/** Monday first, as the week is read here. */
const WEEK = [0, 1, 2, 3, 4, 5, 6];

/** The first subdivision's first sport and court, a new request's choices. */
function firstChoice() {
  const subdivision = shownSubdivision("", undefined);
  const sport = subdivision.sports[0]?.id ?? "tennis";
  return { subdivision: subdivision.id, sport, court: firstCourt(subdivision, sport) };
}

/** The days in words: "T2, T4, T6", or every day. */
function DaysText({ days }: { days: readonly number[] }) {
  const { t } = useTranslation();
  return <>{days.length === 0 ? t("days.every") : days.map((day) => t(dayKey(day))).join(", ")}</>;
}

interface FormProps {
  customers: Customer[];
  request: BookingRequest | null;
  onClose: () => void;
}

/** A request's form: whose, the court, up to two slots, the days, the machine, a note. */
function RequestForm({ customers, request, onClose }: FormProps) {
  const { t } = useTranslation();
  const f = useFormat();
  const cache = useQueryClient();
  const machines = useMachines();
  const [fields, setFields] = useState<Required<RequestFields>>(
    request !== null
      ? {
          customer_id: request.customer_id,
          subdivision: request.subdivision,
          sport: request.sport,
          court: request.court,
          slots: request.slots,
          days: request.days ?? [],
          machine: request.machine ?? null,
          active: request.active,
          note: request.note,
        }
      : {
          customer_id: customers[0]?.id ?? "",
          ...firstChoice(),
          slots: [],
          days: [],
          machine: null,
          active: true,
          note: "",
        },
  );
  const [error, setError] = useState<unknown>(null);
  const [saving, setSaving] = useState(false);
  const subdivision = shownSubdivision(fields.subdivision, undefined);
  const set = (change: Partial<Required<RequestFields>>) =>
    setFields((old) => ({ ...old, ...change }));
  return (
    <form
      aria-label={t(request === null ? "pages.requests.add" : "pages.requests.edit")}
      className={styles.card}
      onSubmit={(event) => {
        event.preventDefault();
        setSaving(true);
        (request === null ? addRequest(fields) : changeRequest({ id: request.id, fields }))
          .then(async () => {
            await cache.invalidateQueries({ queryKey: queryKeys.requests });
            onClose();
          })
          .catch(setError)
          .finally(() => setSaving(false));
      }}
    >
      <h2 className={styles.sectionTitle}>
        {t(request === null ? "pages.requests.add" : "pages.requests.edit")}
      </h2>
      <label className={styles.line}>
        <span className={styles.label}>{t("pages.requests.customer")}</span>
        <select
          value={fields.customer_id}
          onChange={(event) => set({ customer_id: event.target.value })}
        >
          {customers.map((customer) => (
            <option key={customer.id} value={customer.id}>
              {customer.name}
            </option>
          ))}
        </select>
      </label>
      <label className={styles.line}>
        <span className={styles.label}>{t("pages.requests.subdivision")}</span>
        <select
          value={subdivision.id}
          onChange={(event) => {
            const chosen = shownSubdivision(event.target.value, undefined);
            const sport = chosen.sports[0]?.id ?? fields.sport;
            set({ subdivision: chosen.id, sport, court: firstCourt(chosen, sport) });
          }}
        >
          {SUBDIVISIONS.map((item) => (
            <option key={item.id} value={item.id}>
              {item.name}
            </option>
          ))}
        </select>
      </label>
      <label className={styles.line}>
        <span className={styles.label}>{t("pages.requests.sport")}</span>
        <select
          value={fields.sport}
          onChange={(event) =>
            set({ sport: event.target.value, court: firstCourt(subdivision, event.target.value) })
          }
        >
          {sportChoices(subdivision, fields.sport).map((sport) => (
            <option key={sport} value={sport}>
              {t(`sports.${sport}`, { defaultValue: sport })}
            </option>
          ))}
        </select>
      </label>
      <label className={styles.line}>
        <span className={styles.label}>{t("pages.requests.court")}</span>
        <select value={fields.court} onChange={(event) => set({ court: event.target.value })}>
          {courtChoices(subdivision, fields.sport, fields.court).map((court) => (
            <option key={court} value={court}>
              {f.court(court)}
            </option>
          ))}
        </select>
      </label>
      <div className={styles.line}>
        <span className={styles.label}>{t("pages.requests.slots")}</span>
        <span role="group" aria-label={t("pages.requests.slots")} className={styles.chips}>
          {SLOTS.map((slot) => (
            <button
              key={slot}
              type="button"
              aria-pressed={fields.slots.includes(slot)}
              className={`${styles.chip} ${fields.slots.includes(slot) ? styles.good : ""}`}
              onClick={() => set({ slots: toggleSlot(fields.slots, slot) })}
            >
              {f.slot(slot)}
            </button>
          ))}
        </span>
      </div>
      <div className={styles.line}>
        <span className={styles.label}>{t("pages.requests.days")}</span>
        <span role="group" aria-label={t("pages.requests.days")} className={styles.chips}>
          {WEEK.map((day) => (
            <button
              key={day}
              type="button"
              aria-pressed={fields.days.includes(day)}
              className={`${styles.chip} ${fields.days.includes(day) ? styles.good : ""}`}
              onClick={() =>
                set({
                  days: fields.days.includes(day)
                    ? fields.days.filter((other) => other !== day)
                    : [...fields.days, day].sort(),
                })
              }
            >
              {t(dayKey(day))}
            </button>
          ))}
          <span className={styles.muted}>{fields.days.length === 0 && t("days.every")}</span>
        </span>
      </div>
      <label className={styles.line}>
        <span className={styles.label}>{t("pages.requests.machine")}</span>
        <select
          value={fields.machine ?? ""}
          onChange={(event) =>
            set({ machine: event.target.value === "" ? null : Number(event.target.value) })
          }
        >
          <option value="">{t("pages.requests.noMachine")}</option>
          {machines.map((machine) =>
            machine.mumuIndex === null ? null : (
              <option key={machine.mumuIndex} value={machine.mumuIndex}>
                {t("pages.ticket.instanceName", { number: machine.place + 1 })}
              </option>
            ),
          )}
        </select>
      </label>
      <label className={styles.line}>
        <span className={styles.label}>{t("pages.requests.note")}</span>
        <input value={fields.note} onChange={(event) => set({ note: event.target.value })} />
      </label>
      <label className={styles.toggle}>
        <span className={styles.label}>{t("pages.requests.active")}</span>
        <Switch
          label={t("pages.requests.active")}
          checked={fields.active}
          onChange={(active) => set({ active })}
        />
      </label>
      {error !== null && (
        <p role="alert" className={styles.muted}>
          {errorMessage(t, error)}
        </p>
      )}
      <div className={styles.actions}>
        <Button type="submit" variant="primary" disabled={saving || fields.slots.length === 0}>
          {t("pages.requests.save")}
        </Button>
        <Button onClick={onClose}>{t("pages.requests.cancel")}</Button>
      </div>
    </form>
  );
}

interface RowProps {
  request: BookingRequest;
  customers: Customer[];
  onEdit: () => void;
}

/** One request: what it asks, on which machine, and whether that machine books it now. */
function RequestRow({ request, customers, onEdit }: RowProps) {
  const { t } = useTranslation();
  const f = useFormat();
  const cache = useQueryClient();
  const machines = useMachines();
  const settings = useSettings();
  const [state, setState] = useState<{ text: string; bad: boolean } | null>(null);
  const machine = machines.find((item) => item.mumuIndex === (request.machine ?? null));
  const attached =
    request.machine == null ? null : (accountOn(customers, request.machine)?.customer ?? null);
  const otherAccount = attached !== null && attached.id !== request.customer_id;

  async function apply() {
    if (machine === undefined || machine.mumuIndex === null || settings.data === undefined) {
      return;
    }
    setState(null);
    try {
      let current = settings.data;
      if (!machine.enabled) {
        current = await switchInstance(machine.mumuIndex, true);
      }
      const saved = await saveSettings(appliedTo(current, machine.mumuIndex, request));
      cache.setQueryData(queryKeys.settings, saved);
      setState({ text: t("pages.requests.applied"), bad: false });
    } catch (error) {
      setState({ text: errorMessage(t, error), bad: true });
    }
  }

  return (
    <li className={styles.alert}>
      <Icon name={request.active ? "check" : "close"} />
      <span className={styles.value}>
        <strong>{f.court(request.court)}</strong> ·{" "}
        {request.slots.map((slot) => f.slot(slot)).join(", ")} ·{" "}
        <DaysText days={request.days ?? []} />
        <br />
        <span className={styles.muted}>
          {machine === undefined
            ? t("pages.requests.noMachine")
            : t("pages.ticket.instanceName", { number: machine.place + 1 })}
          {request.note !== "" && ` · ${request.note}`}
          {!request.active && ` · ${t("pages.requests.paused")}`}
        </span>
        {otherAccount && (
          <>
            <br />
            <span className={`${styles.chip} ${styles.warn}`}>
              {t("pages.requests.otherAccount")}
            </span>
          </>
        )}
        {state !== null && (
          <>
            <br />
            <span
              role="status"
              className={`${styles.chip} ${state.bad ? styles.bad : styles.good}`}
            >
              {state.text}
            </span>
          </>
        )}
      </span>
      {machine !== undefined && request.active && (
        <Button onClick={() => void apply()}>{t("pages.requests.apply")}</Button>
      )}
      <IconButton icon="edit" label={t("pages.requests.edit")} onClick={onEdit} />
      <IconButton
        icon="remove"
        variant="danger"
        label={t("pages.requests.remove")}
        onClick={() => {
          void removeRequest(request.id).then(() =>
            cache.invalidateQueries({ queryKey: queryKeys.requests }),
          );
        }}
      />
    </li>
  );
}

/**
 * What each customer asks to book: a court, its slots, the days of the week and the machine
 * that books it. Applying a request sets that machine to book it (its court, slots and days),
 * which the daily task then does with the machine's account.
 */
export function RequestsTab() {
  const { t } = useTranslation();
  const customers = useCustomers();
  const requests = useRequests();
  const [editing, setEditing] = useState<BookingRequest | "new" | null>(null);
  if (customers.data === undefined || requests.data === undefined) {
    return <Loading />;
  }
  const list = customers.data;
  return (
    <>
      <PageTitle>{t("pages.requests.title")}</PageTitle>
      <div className={styles.page}>
        <p className={styles.muted}>{t("pages.requests.hint")}</p>
        <div className={styles.wide}>
          <div className={styles.column}>
            {list.length === 0 && <p className={styles.card}>{t("pages.requests.noCustomer")}</p>}
            {list.map((customer) => {
              const own = requests.data.filter((item) => item.customer_id === customer.id);
              return (
                <section key={customer.id} aria-label={customer.name} className={styles.card}>
                  <h2 className={styles.cardTitle}>{customer.name}</h2>
                  {own.length === 0 ? (
                    <p className={styles.muted}>{t("pages.requests.none")}</p>
                  ) : (
                    <ul className={styles.alerts}>
                      {own.map((item) => (
                        <RequestRow
                          key={item.id}
                          request={item}
                          customers={list}
                          onEdit={() => setEditing(item)}
                        />
                      ))}
                    </ul>
                  )}
                </section>
              );
            })}
          </div>
          <div className={styles.column}>
            {editing === null ? (
              <Button
                variant="primary"
                disabled={list.length === 0}
                onClick={() => setEditing("new")}
              >
                <Icon name="add" /> {t("pages.requests.add")}
              </Button>
            ) : (
              <RequestForm
                key={editing === "new" ? "new" : editing.id}
                customers={list}
                request={editing === "new" ? null : editing}
                onClose={() => setEditing(null)}
              />
            )}
          </div>
        </div>
      </div>
    </>
  );
}
