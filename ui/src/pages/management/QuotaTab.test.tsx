import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { QuotaReading } from "../../api/types";
import { paths } from "../../paths";
import { renderApp } from "../../test/app";
import { type Reply, reply, requestsTo } from "../../test/backend";
import { account, customer } from "../../test/customers";
import { overview } from "../../test/overview";
import { settings } from "../../test/settings";

function read(sport: string, used: number, month = "2026-10"): QuotaReading {
  const utility = { tennis: "Sân Tennis", pickleball: "Sân Pickleball" }[sport] ?? sport;
  return { utility, sport, month, used, month_limit: 8, read_at: "2026-10-15T06:03:10.000" };
}

const CUSTOMERS = [
  customer("a1", {
    name: "Anh An",
    accounts: [
      account("b1", { device: 0, quota: [read("tennis", 2), read("pickleball", 7)] }),
      account("b2", { label: "Căn B", device: null, quota: [read("tennis", 8)] }),
    ],
  }),
  customer("a2", {
    name: "Chị Bình",
    accounts: [account("b3", { label: "Căn C", phone: "0912345678", quota: [read("tennis", 1)] })],
  }),
];

async function open(extra: Record<string, Reply> = {}, address: string = paths.quota) {
  const app = renderApp(address, {
    "GET /api/status": reply(overview()),
    "GET /api/settings": reply(settings()),
    "GET /api/customers": reply(CUSTOMERS),
    ...extra,
  });
  const board = within(await screen.findByRole("region", { name: /^(Anh An|Chị Bình)$/ }));
  return Object.assign(board, { fetch: app.fetch });
}

/** The customers listed, the one shown in brackets. */
function listed() {
  return within(screen.getByRole("navigation", { name: "Khách hàng" }))
    .getAllByRole("button")
    .map((item) =>
      item.getAttribute("aria-current") === "true" ? `[${item.textContent}]` : item.textContent,
    );
}

describe("Quota board", () => {
  it("shows the first customer's accounts with what each booked of a sport, Full at the limit", async () => {
    const board = await open();

    const rows = board.getAllByRole("row").map((row) => row.textContent);
    expect(rows).toEqual([
      "Tài khoảnTennisPickleballĐọc lại hạn mức",
      "Căn A09000000112/87/8",
      "Căn B0900000011Full–",
    ]);
    // No machine column; read again only for the account on a machine, which it names.
    expect(board.queryByText("Máy")).not.toBeInTheDocument();
    expect(board.getAllByRole("button", { name: /^Đọc lại hạn mức trên/ })).toHaveLength(1);
    expect(board.getByRole("button", { name: /^Đọc lại hạn mức trên/ })).toHaveAccessibleName(
      "Đọc lại hạn mức trên Máy 1",
    );
  });

  it("marks the customers running out, and shows the one pressed", async () => {
    await open();
    expect(listed()).toEqual([
      "[Anh AnCó tài khoản sắp hết lượt22 tài khoản]",
      "Chị Bình11 tài khoản",
    ]);

    fireEvent.click(screen.getByRole("button", { name: /^Chị Bình/ }));

    const board = within(await screen.findByRole("region", { name: "Chị Bình" }));
    expect(board.getAllByRole("row").map((row) => row.textContent)).toEqual([
      "Tài khoảnTennisĐọc lại hạn mức",
      "Căn C09123456781/8",
    ]);
  });

  it("opens on the customer in the address, and finds one by an account's phone number", async () => {
    await open({}, `${paths.quota}?customer=a2`);
    expect(screen.getByRole("region", { name: "Chị Bình" })).toBeInTheDocument();

    fireEvent.change(screen.getByRole("searchbox"), { target: { value: "0900 0000 11" } });

    expect(listed()).toEqual(["[Anh AnCó tài khoản sắp hết lượt22 tài khoản]"]);
  });
});

describe("Reading a quota again", () => {
  const RUNNING = { code: null, machine: 0, started_at: "2026-10-15T09:30:00", running: true };

  it("reads the quota of an account on a machine again, and says when it is done", async () => {
    const board = await open({
      "POST /api/machines/0/quota": reply({ ...RUNNING, exit_code: null }, 202),
      "GET /api/machines/quota": reply({ ...RUNNING, running: false, exit_code: 0 }),
    });

    fireEvent.click(board.getByRole("button", { name: /^Đọc lại hạn mức trên/ }));

    expect(await board.findByText(/^Đang đọc hạn mức trong app Vinhomes/)).toBeVisible();
    expect(await board.findByText("Đã đọc lại hạn mức.", {}, { timeout: 4000 })).toBeVisible();
    expect(requestsTo(board.fetch, "POST /api/machines/0/quota")).toBe(1);
    await waitFor(() => expect(requestsTo(board.fetch, "GET /api/customers")).toBeGreaterThan(1));
  });

  it("says why when it is refused", async () => {
    const board = await open({
      "POST /api/machines/0/quota": reply({ error: "lock_held", detail: "busy" }, 409),
      "GET /api/machines/quota": reply({}),
    });

    fireEvent.click(board.getByRole("button", { name: /^Đọc lại hạn mức trên/ }));

    expect(
      await board.findByText("Đang có một lần chạy khác. Hãy chờ nó xong rồi thử lại."),
    ).toBeVisible();
  });
});
