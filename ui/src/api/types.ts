/**
 * Short names for the backend's types, generated in schema.d.ts from the OpenAPI schema.
 * After a backend change: `python tools/export_openapi.py`, then `npm run api:types`.
 */
import type { components, paths } from "./schema";

type Schemas = components["schemas"];

export type { paths };

/** Everything the Overview shows, in one call (`GET /api/status`). */
export type Overview = Schemas["Overview"];
/** The run that holds the emulator now. */
export type Running = Schemas["Running"];
export type ScheduleState = Schemas["ScheduleState"];
export type ScheduleSwitch = Schemas["ScheduleSwitch"];

/** One run as the History list shows it. */
export type RunSummary = Schemas["RunSummary"];
/** One run in full: its slots, steps and technical log lines. */
export type RunDetail = Schemas["RunDetail"];
export type SlotResult = Schemas["SlotResult"];
/** One step of the activity log; `kind` is the message key, `data` its values. */
export type Step = Schemas["Step"];
/** Every kind of step the engine and the app record (the backend's `EventKind`). */
export type StepKind = Schemas["EventKind"];
/** The Activity filter a step belongs to. */
export type StepCategory = Step["category"];
export type LogLine = Schemas["LogLine"];

/** One ticket of an account, as a run last read it in the app (`GET /api/tickets`). */
export type Ticket = Schemas["Ticket"];

/** The subdivision a MuMu instance's account last told (`GET /api/accounts`). */
export type AccountSubdivision = Schemas["AccountSubdivision"];

export type Settings = Schemas["Settings"];
export type LabelSettings = Schemas["LabelSettings"];
/** Whether every run ends with a Windows notification, and its language. */
export type NotificationSettings = Schemas["NotificationSettings"];
export type KeepOnState = Schemas["KeepOnState"];
/** A customer with the Vinhomes accounts they gave; phone numbers masked, never a password. */
export type Customer = Schemas["CustomerRecord"];
export type CustomerAccount = Schemas["CustomerAccount"];
export type QuotaReading = Schemas["QuotaReading"];
export type CustomerFields = Schemas["CustomerFields"];
export type NewAccount = Schemas["NewAccount"];
export type AccountChange = Schemas["AccountChange"];
export type AccountLogin = Schemas["AccountLogin"];

export type SetupItem = Schemas["SetupItem"];
/** The state of one device setup item (the backend's `Status` enum). */
export type SetupStatus = Schemas["Status"];

export type DryRunStarted = Schemas["DryRunStarted"];
export type Prices = Schemas["Prices"];
export type ImportResult = Schemas["ImportResult"];
export type Charge = Schemas["Charge"];
export type Charges = Schemas["Charges"];
export type ChargeChange = Schemas["ChargeChange"];
/** A task on a machine started last from the app (a cancel, a quota read), going on or over. */
export type TaskState = Schemas["TaskState"];
/** The ticket cancel started last from the app (`court-booker cancel`). */
export type CancelState = TaskState;
export type Health = Schemas["Health"];

/** Every error body: `error` is a stable code the UI translates, `detail` the English text. */
export type Problem = Schemas["Problem"];
