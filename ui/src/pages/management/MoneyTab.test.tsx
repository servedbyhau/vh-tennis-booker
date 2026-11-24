import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { Charge } from "../../api/types";
import i18n from "../../i18n";
import { paths } from "../../paths";
import { renderApp } from "../../test/app";
import { type Reply, reply, requestsTo } from "../../test/backend";
import { overview } from "../../test/overview";
import { settings } from "../../test/settings";
import { byCustomer, formatMoney, statementOf } from "./money";

const AN = "a".repeat(32);

function charge(code: string, fields: Partial<Charge> = {}): Charge {
  return {
    code,
    customer_id: AN,
    customer: "Anh An",
    account: "Căn A",
    sport: "pickleball",
    court: "S9 - Sân Pickleball",
    play_date: "2026-11-26",
    slot: "18:00 - 19:00",
    golden: true,
    amount: 150000,
    set_by_hand: false,
    cancelled: false,
    free: false,
    paid_at: null,
    ...fields,
  };
}

const CHARGES = [
  charge("1"),
  charge("2", {
    slot: "07:00 - 08:00",
    golden: false,
    amount: 100000,
    paid_at: "2026-11-24T08:00:00",
  }),
  charge("3", { cancelled: true, amount: 0 }),
];

async function open(extra: Record<string, Reply> = {}) {
  const app = renderApp(paths.money, {
    "GET /api/status": reply(overview()),
    "GET /api/settings": reply(settings()),
    "GET /api/money/charges": reply({
      month: "2026-11",
      months: ["2026-11", "2026-10"],
      charges: CHARGES,
      free_customers: [],
    }),
    "GET /api/money/prices": reply({ golden_from: "17:00", golden_to: "21:00", prices: [] }),
    ...extra,
  });
  await screen.findByRole("region", { name: "Anh An" });
  return app;
}

beforeEach(() => {
  vi.useFakeTimers({ toFake: ["Date"] });
  vi.setSystemTime(new Date(2026, 10, 15, 9, 30));
});

afterEach(() => {
  vi.useRealTimers();
});

describe("Money", () => {
  it("sums the month and lists each customer's tickets with their price", async () => {
    await open();

    expect(screen.getByText("250.000 đ")).toBeInTheDocument(); // owed: the cancelled one is not
    expect(screen.getAllByText("100.000 đ").length).toBeGreaterThan(0);
    const card = within(screen.getByRole("region", { name: "Anh An" }));
    expect(card.getByText("còn 150.000 đ")).toBeInTheDocument();
    expect(card.getAllByText(/giờ vàng/)).toHaveLength(2); // the golden one and the cancelled one
    expect(card.getByText("đã huỷ")).toBeInTheDocument();
    expect(
      within(screen.getByRole("group", { name: "Tháng chơi" }))
        .getAllByRole("button")
        .map((button) => button.textContent),
    ).toEqual(["Tháng 11/2026", "Tháng 10/2026"]);
  });

  it("marks one ticket paid, or all of a customer's at once", async () => {
    const app = await open({
      "PUT /api/money/charges/1": { status: 204, body: null },
      "PUT /api/money/paid": { status: 204, body: null },
    });
    const card = within(screen.getByRole("region", { name: "Anh An" }));

    fireEvent.click(
      card.getByRole("button", { name: "Đã thu tiền vé ngày T5 26/11", pressed: false }),
    );
    fireEvent.click(card.getByRole("button", { name: /Đã thu hết/ }));

    await waitFor(() => expect(requestsTo(app.fetch, "PUT /api/money/charges/1")).toBe(1));
    await waitFor(() => expect(requestsTo(app.fetch, "PUT /api/money/paid")).toBe(1));
  });

  it("saves the prices typed", async () => {
    const app = await open({
      "PUT /api/money/prices": reply({ golden_from: "17:00", golden_to: "21:00", prices: [] }),
    });

    fireEvent.change(screen.getByLabelText("Pickleball Giá thường"), {
      target: { value: "100.000" },
    });
    fireEvent.change(screen.getByLabelText("Pickleball Giá giờ vàng"), {
      target: { value: "150000" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Lưu bảng giá" }));

    await waitFor(() => expect(requestsTo(app.fetch, "PUT /api/money/prices")).toBe(1));
    const sent = app.fetch.mock.calls
      .map(([request]) => request)
      .find((request) => request.method === "PUT");
    expect(await sent?.clone().json()).toEqual({
      golden_from: "17:00",
      golden_to: "21:00",
      prices: [{ sport: "pickleball", normal: 100000, golden: 150000 }],
    });
  });
});

describe("Money sums", () => {
  it("writes the statement to send, cancelled tickets left out", () => {
    const [item] = byCustomer(CHARGES, "?");
    expect(item).toBeDefined();
    const t = i18n.getFixedT("vi");

    expect(statementOf(t, "2026-11", item!).split("\n")).toEqual([
      "Bảng kê tháng 11/2026 · Anh An",
      "26/11 18:00–19:00 Pickleball S9: 150.000 đ",
      "26/11 07:00–08:00 Pickleball S9: 100.000 đ",
      "Tổng 250.000 đ · đã trả 100.000 đ · còn lại 150.000 đ",
    ]);
    expect(formatMoney(1500000)).toBe("1.500.000 đ");
  });
});
