import { screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { Customer, Settings } from "../../api/types";
import { paths } from "../../paths";
import { renderApp } from "../../test/app";
import { type Reply, reply } from "../../test/backend";
import { account, customer } from "../../test/customers";
import { overview } from "../../test/overview";
import { runSummary } from "../../test/runs";
import { settings } from "../../test/settings";
import { ticket } from "../../test/tickets";

/** Two machines: the first books tennis, the second pickleball with MuMu 1. */
const SETTINGS: Settings = settings({
  instances: [
    {
      mumu_index: 1,
      slots: ["17:00 - 18:00"],
      subdivision: "",
      sport: "pickleball",
      court: "S9 - Sân Pickleball",
      venue_keyword: "Origami",
      days: [],
    },
  ],
});

const AN: Customer = customer("a1", {
  name: "Anh An",
  accounts: [account("b1", { device: 0, phone: "0900000012" })],
});
const BINH: Customer = customer("a2", {
  name: "Chị Bình",
  accounts: [account("b2", { device: 1, phone: "0900000062" })],
});

const BOOKED = runSummary(7, { device: 0, started_at: "2026-10-15T05:45:00.000" });
const FAILED = runSummary(8, {
  device: 1,
  status: "failed",
  error: "The app did not reach its home screen",
  booked: 0,
  total: 0,
  slots: [],
});

async function open(path: string, extra: Record<string, Reply> = {}) {
  const app = renderApp(path, {
    "GET /api/status": reply(overview()),
    "GET /api/settings": reply(SETTINGS),
    "GET /api/mumu-instances": reply({ indexes: [0, 1, 2] }),
    "GET /api/customers": reply([AN, BINH]),
    "GET /api/runs": reply([BOOKED]),
    "GET /api/tickets": reply([
      ticket("1000001", {
        play_date: "2026-10-15",
        slot: "18:00 - 19:00",
        sent_at: "2026-10-15T07:00:00",
        ...AN,
      }),
      ticket("1000002", {
        play_date: "2026-10-16",
        customer: "Chị Bình",
        sent_at: "2026-10-15T07:00:00",
      }),
      ticket("1000003", { play_date: "2026-10-16", status: "cancelled" }),
    ]),
    ...extra,
  });
  await screen.findByRole("heading", { level: 2, name: /Các máy|Máy 1/ });
  return app;
}

beforeEach(() => {
  vi.useFakeTimers({ toFake: ["Date"] });
  vi.setSystemTime(new Date(2026, 9, 15, 9, 30));
});

afterEach(() => {
  vi.useRealTimers();
});

describe("Management overview", () => {
  it("opens first with the machines, each with its account, what it books and its last run", async () => {
    await open(paths.management);

    const machines = within(screen.getByRole("region", { name: "Các máy" }));
    expect(machines.getByText("Lượt 06:00 gần nhất: T5 15/10")).toBeInTheDocument();
    const rows = machines.getAllByRole("row").map((row) => row.textContent);
    expect(rows[0]).toContain("Tài khoản");
    expect(rows[1]).toContain("Máy 1");
    expect(rows[1]).toContain("Căn A0900000012");
    expect(rows[3]).toContain("Đang tắt");
    // Nothing to look at: no such part, and no figures or tickets.
    expect(screen.queryByRole("region", { name: "Cần xử lý" })).not.toBeInTheDocument();
    expect(screen.queryByText(/vé sắp chơi|Vé mấy ngày tới/)).not.toBeInTheDocument();
  });

  it("lists what to look at, the worst first, each leading where it is set right", async () => {
    await open(paths.management, {
      "GET /api/status": reply(overview({ schedule: { ...overview().schedule, enabled: false } })),
      "GET /api/customers": reply([AN, { ...BINH, accounts: [account("b2", { device: null })] }]),
      "GET /api/runs": reply([FAILED, BOOKED]),
      "GET /api/tickets": reply([ticket("1000005", { play_date: "2026-10-16" })]),
    });
    const alerts = within(screen.getByRole("region", { name: "Cần xử lý" }));

    const texts = alerts.getAllByRole("link").map((link) => link.textContent);
    expect(texts).toContain("Tự đặt đang tắt: sáng mai không đặt sân.");
    expect(texts).toContain("Máy 2 chưa chọn tài khoản nên sẽ không đặt.");
    expect(texts).toContain("Máy 2: lượt đặt gần nhất bị lỗi. Xem trong Lịch sử.");
    expect(texts).toContain("1 vé hôm nay và ngày mai chưa gửi cho khách.");
    expect(alerts.getByRole("link", { name: /bị lỗi/ })).toHaveAttribute(
      "href",
      `${paths.history}?run=8`,
    );
  });
});
