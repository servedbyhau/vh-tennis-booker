import type { Ticket } from "../api/types";

/** A ticket of the first machine as GET /api/tickets gives it, with made-up values. */
export function ticket(code: string, fields: Partial<Ticket> = {}): Ticket {
  return {
    code,
    device: 0,
    customer: null,
    account: null,
    court: "S6 - Sân tennis",
    play_date: "2026-10-16",
    slot: "18:00 - 19:00",
    status: "registered",
    status_text: "Đã đăng ký",
    created_at: "2026-10-14T06:00",
    seen_at: "2026-10-14T06:01:12.000",
    has_photo: true,
    machine: 0,
    ...fields,
  };
}
