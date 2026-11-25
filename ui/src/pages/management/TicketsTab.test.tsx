import { act, fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { Ticket } from "../../api/types";
import i18n from "../../i18n";
import { paths } from "../../paths";
import { renderApp } from "../../test/app";
import { type Reply, reply, requestsTo } from "../../test/backend";
import { step } from "../../test/liveSocket";
import { overview } from "../../test/overview";
import { settings } from "../../test/settings";
import { ticket } from "../../test/tickets";

const AN = { customer: "Anh An", account: "Căn A" };
const BINH = { customer: "Chị Bình", account: "0900000044" };

/** Two customers' tickets around 15/10, with made-up codes. */
const TICKETS = [
  ticket("1000004", {
    play_date: "2026-10-17",
    device: 1,
    court: "S9 - Sân Pickleball",
    ...BINH,
  }),
  ticket("1000003", { slot: "19:00 - 20:00", has_photo: false, status: "processing", ...AN }),
  ticket("1000002", { slot: "18:00 - 19:00", ...AN }),
  ticket("1000001", { slot: "08:00 - 09:00", status: "cancelled", has_photo: false }),
  ticket("1000000", { play_date: "2026-10-12", status: "other", status_text: "Đã sử dụng" }),
];

/** Open the tickets section with `tickets`. */
async function openTab(tickets: Ticket[] = TICKETS, extra: Record<string, Reply> = {}) {
  const app = renderApp(paths.tickets, {
    "GET /api/status": reply(overview()),
    "GET /api/settings": reply(settings()),
    "GET /api/runs": reply([]),
    "GET /api/tickets": reply(tickets),
    ...extra,
  });
  await screen.findByRole("region", { name: "Vé" });
  return app;
}

function panel() {
  return screen.getByRole("region", { name: "Vé" });
}

/** Each day listed, with the text of its tickets. */
async function days() {
  await within(panel()).findAllByRole("region");
  return within(panel())
    .queryAllByRole("region")
    .map((day) => [
      within(day).getByRole("heading").textContent,
      ...within(day)
        .getAllByRole("listitem")
        .map((row) => row.textContent),
    ]);
}

async function openTicket(name: RegExp) {
  fireEvent.click(await within(panel()).findByRole("button", { name }));
  return screen.getByRole("dialog");
}

beforeEach(() => {
  vi.useFakeTimers({ toFake: ["Date"] });
  vi.setSystemTime(new Date(2026, 9, 15, 9, 30));
});

afterEach(() => {
  vi.useRealTimers();
});

describe("Tickets list", () => {
  it("lists every customer's tickets to use by day, cancelled ones left out", async () => {
    await openTab();

    expect(await days()).toEqual([
      [
        "Thứ Sáu 16/102 vé · 2 chưa gửi",
        // The usual status left out, the picture marked, the customer named as several are.
        "18:00–19:00 · Tennis S6Xem véCăn A · Anh AnChưa gửi",
        "19:00–20:00 · Tennis S6ĐANG XỬ LÝCăn A · Anh AnChưa gửi",
      ],
      [
        "Thứ Bảy 17/101 vé · 1 chưa gửi",
        "18:00–19:00 · Pickleball S9Xem vé0900000044 · Chị BìnhChưa gửi",
      ],
    ]);
  });

  it("leaves out the tickets whose day of play is over, today's kept", async () => {
    await openTab([
      ticket("1000006", { play_date: "2026-10-15", slot: "06:00 - 07:00" }),
      ticket("1000005", { play_date: "2026-10-14" }),
    ]);
    expect((await days()).map(([day]) => day)).toEqual(["Thứ Năm 15/101 vé · 1 chưa gửi"]);
  });

  it("lists a status of the app's own in its words", async () => {
    await openTab([ticket("1000000", { status: "other", status_text: "Đã sử dụng" })]);
    expect((await days())[0]?.[1]).toContain("Đã sử dụng");
  });

  it("lists the tickets of one customer, and those whose holder is not known", async () => {
    await openTab([...TICKETS, ticket("1000009", { slot: "06:00 - 07:00", device: 1 })]);
    await days();
    const customers = within(within(panel()).getByRole("group", { name: "Vé của khách" }));
    expect(customers.getAllByRole("button").map((button) => button.textContent)).toEqual([
      "Mọi khách",
      "Anh An",
      "Chị Bình",
      "Không rõ khách",
    ]);

    fireEvent.click(customers.getByRole("button", { name: "Chị Bình" }));
    expect((await days()).map(([day]) => day)).toEqual(["Thứ Bảy 17/101 vé · 1 chưa gửi"]);

    fireEvent.click(customers.getByRole("button", { name: "Không rõ khách" }));
    expect((await days()).map((day) => day.slice(1))).toEqual([
      ["06:00–07:00 · Tennis S6Xem véMáy 2Chưa gửi"], // the machine it was read on
    ]);
  });

  it("offers no customer to choose with one alone", async () => {
    await openTab([ticket("1000002", AN)]);
    await days();
    expect(within(panel()).queryByRole("group", { name: "Vé của khách" })).not.toBeInTheDocument();
  });

  it("names the MuMu instance of a machine that has no tab any more", async () => {
    await openTab([ticket("1000002", { device: 7 })]);
    expect((await days())[0]?.[1]).toContain("MuMu 7");
  });

  it("keeps the customer chosen while another section shows", async () => {
    await openTab();
    await days();
    fireEvent.click(within(panel()).getByRole("button", { name: "Chị Bình" }));
    fireEvent.click(screen.getByRole("link", { name: "Lịch sử" }));

    fireEvent.click(screen.getByRole("link", { name: "Vé" }));

    expect((await days()).map(([day]) => day)).toEqual(["Thứ Bảy 17/101 vé · 1 chưa gửi"]);
  });

  it("lists every customer's once the one chosen has no ticket left", async () => {
    const { fetch, live } = await openTab();
    await days();
    fireEvent.click(within(panel()).getByRole("button", { name: "Chị Bình" }));
    const left = TICKETS.filter(({ device }) => device === 0);
    fetch.mockImplementation((input) =>
      Promise.resolve(
        input instanceof Request && input.url.endsWith("/api/tickets")
          ? Response.json(left)
          : Response.json([]),
      ),
    );

    act(() => {
      live.current().open();
      live.current().send(step(9, { kind: "tickets_saved", category: "step", data: {} }));
    });

    await waitFor(async () =>
      expect((await days()).map(([day]) => day)).toEqual(["Thứ Sáu 16/102 vé · 2 chưa gửi"]),
    );
  });

  it.each([
    ["there is none", []],
    ["all are over or cancelled", [TICKETS[3]!, TICKETS[4]!]],
  ])("says when there is nothing to list: %s", async (_, tickets) => {
    await openTab(tickets);
    expect(await within(panel()).findByText(/^Chưa có vé nào\./)).toBeInTheDocument();
  });

  it("offers to try again when the tickets cannot be read", async () => {
    renderApp(paths.tickets, { "GET /api/status": reply(overview()) });
    expect(await within(panel()).findByRole("button", { name: "Thử lại" })).toBeInTheDocument();
  });

  it("reads the tickets again once a run has read them in the app", async () => {
    const { fetch, live } = await openTab();
    await days();

    act(() => {
      live.current().open();
      live
        .current()
        .send(
          step(9, { kind: "tickets_saved", category: "step", data: { tickets: 4, photos: 2 } }),
        );
    });

    await waitFor(() => expect(requestsTo(fetch, "GET /api/tickets")).toBe(2));
  });

  it("is worded in English too", async () => {
    await i18n.changeLanguage("en");
    renderApp(paths.tickets, {
      "GET /api/status": reply(overview()),
      "GET /api/tickets": reply(TICKETS),
    });
    expect(
      await screen.findByRole("button", { name: "Sent to the customer: 18:00–19:00 · Tennis S6" }),
    ).toHaveTextContent("Not sent");
    await i18n.changeLanguage("vi");
  });
});

describe("Ticket dialog", () => {
  it("shows the ticket's picture alone and saves it under a name that tells it", async () => {
    await openTab();
    const dialog = await openTicket(/^18:00–19:00 · Tennis/);
    const url = "/api/tickets/1000002/photo?seen=2026-10-14T06%3A01%3A12.000";

    expect(dialog).toHaveAccessibleName("18:00–19:00 · Tennis S6");
    expect(
      within(dialog).getByRole("img", { name: "Ảnh vé 18:00–19:00 · Tennis S6" }),
    ).toHaveAttribute("src", url);
    const save = within(dialog).getByRole("link", { name: "Lưu vé" });
    expect(save).toHaveAttribute("href", url);
    expect(save).toHaveAttribute("download", "2026-10-16 18h00-19h00 Tennis S6 1000002.png");
    expect(dialog.textContent).toBe("1/3");
  });

  describe("copy", () => {
    /** Items written to the clipboard, each by its types. */
    const write = vi.fn<(items: { parts: Record<string, Promise<Blob>> }[]) => Promise<void>>();

    beforeEach(() => {
      write.mockReset();
      vi.stubGlobal(
        "ClipboardItem",
        class {
          readonly parts: Record<string, Promise<Blob>>;
          constructor(parts: Record<string, Promise<Blob>>) {
            this.parts = parts;
          }
        },
      );
      Object.defineProperty(navigator, "clipboard", { value: { write }, configurable: true });
    });

    afterEach(() => {
      Reflect.deleteProperty(navigator, "clipboard");
      vi.unstubAllGlobals();
    });

    it("copies the picture and says so", async () => {
      await openTab(TICKETS, { "GET /api/tickets/1000002/photo": reply("a picture") });
      const dialog = await openTicket(/^18:00–19:00 · Tennis/);
      write.mockResolvedValue();

      fireEvent.click(within(dialog).getByRole("button", { name: "Copy ảnh" }));

      expect(await within(dialog).findByText("Đã copy ảnh, dán vào Zalo")).toBeVisible();
      const [items] = write.mock.calls[0]!;
      expect(await (await items[0]!.parts["image/png"]!).text()).toBe('"a picture"');
    });

    it("says when the picture could not be copied", async () => {
      await openTab();
      const dialog = await openTicket(/^18:00–19:00 · Tennis/);
      write.mockRejectedValue(new Error("denied"));
      fireEvent.click(within(dialog).getByRole("button", { name: "Copy ảnh" }));
      expect(await within(dialog).findByText("Không copy được ảnh, hãy dùng Lưu vé")).toBeVisible();
    });

    it("is not offered without a picture", async () => {
      await openTab();
      const dialog = await openTicket(/^19:00–20:00 · Tennis/);
      expect(within(dialog).queryByRole("button", { name: "Copy ảnh" })).not.toBeInTheDocument();
    });
  });

  it("moves through the tickets listed, with its buttons and the arrow keys", async () => {
    await openTab();
    const dialog = await openTicket(/^18:00–19:00 · Tennis/);
    expect(within(dialog).getByText("1/3")).toBeInTheDocument();
    expect(within(dialog).getByRole("button", { name: "Vé trước" })).toBeDisabled();

    fireEvent.click(within(dialog).getByRole("button", { name: "Vé sau" }));
    expect(dialog).toHaveAccessibleName("19:00–20:00 · Tennis S6");

    fireEvent.keyDown(dialog, { key: "ArrowRight" });
    expect(dialog).toHaveAccessibleName("18:00–19:00 · Pickleball S9");
    fireEvent.keyDown(dialog, { key: "ArrowRight" }); // the last one stays
    expect(within(dialog).getByText("3/3")).toBeInTheDocument();
    expect(within(dialog).getByRole("button", { name: "Vé sau" })).toBeDisabled();

    fireEvent.keyDown(dialog, { key: "ArrowLeft" });
    expect(within(dialog).getByText("2/3")).toBeInTheDocument();
  });

  it("says when a ticket has no picture", async () => {
    await openTab();
    const dialog = await openTicket(/^19:00–20:00 · Tennis/);
    expect(within(dialog).queryByRole("img")).not.toBeInTheDocument();
    expect(within(dialog).getByText(/^Vé này chưa có ảnh\./)).toBeInTheDocument();
    expect(within(dialog).queryByRole("link")).not.toBeInTheDocument(); // nothing to save
  });

  it("says when the picture does not open, for that ticket alone", async () => {
    await openTab();
    const dialog = await openTicket(/^18:00–19:00 · Tennis/);
    fireEvent.error(within(dialog).getByRole("img"));
    expect(within(dialog).getByText("Không mở được ảnh vé.")).toBeInTheDocument();
    expect(within(dialog).queryByRole("link")).not.toBeInTheDocument();

    fireEvent.keyDown(dialog, { key: "ArrowRight" });
    fireEvent.keyDown(dialog, { key: "ArrowRight" });
    expect(within(dialog).getByRole("img")).toBeInTheDocument();
  });

  it("closes with its button, Escape and a press beside it, and gives the focus back", async () => {
    await openTab();
    const row = await within(panel()).findByRole("button", { name: /^18:00–19:00 · Tennis/ });
    row.focus();
    fireEvent.click(row);
    expect(screen.getByRole("dialog")).toHaveFocus();
    fireEvent.click(screen.getByRole("button", { name: "Đóng" }));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(row).toHaveFocus();

    fireEvent.click(row);
    fireEvent.keyDown(screen.getByRole("dialog"), { key: "Escape" });
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();

    fireEvent.click(row);
    fireEvent.click(within(screen.getByRole("dialog")).getByRole("img"));
    expect(screen.getByRole("dialog")).toBeInTheDocument(); // a press inside keeps it
    fireEvent.click(screen.getByRole("dialog")); // between the picture and the buttons
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();

    fireEvent.click(row);
    fireEvent.click(screen.getByRole("dialog").parentElement!);
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("keeps the keys working when a move takes the control pressed away", async () => {
    await openTab();
    const dialog = await openTicket(/^18:00–19:00 · Tennis/);
    const next = within(dialog).getByRole("button", { name: "Vé sau" });
    next.focus();
    fireEvent.click(next);
    expect(next).toHaveFocus(); // there to press again
    fireEvent.click(next); // the last ticket: disabled from here on
    expect(dialog).toHaveFocus();

    const save = within(dialog).getByRole("link", { name: "Lưu vé" });
    save.focus();
    fireEvent.keyDown(save, { key: "ArrowLeft" }); // a ticket with nothing to save
    expect(dialog).toHaveFocus();
  });

  it("keeps Tab inside", async () => {
    await openTab();
    const dialog = await openTicket(/^19:00–20:00 · Tennis/);
    const first = within(dialog).getByRole("button", { name: "Vé trước" });
    const last = within(dialog).getByRole("button", { name: "Vé sau" });

    last.focus();
    fireEvent.keyDown(last, { key: "Tab" });
    expect(first).toHaveFocus();
    fireEvent.keyDown(first, { key: "Tab", shiftKey: true });
    expect(last).toHaveFocus();
  });
});

describe("Cancelling a ticket", () => {
  const RUNNING = {
    code: "1000002",
    machine: 0,
    started_at: "2026-10-15T09:30:00",
    running: true,
    exit_code: null,
  };

  /** Open the 18:00 ticket of Anh An, with the cancel answering `extra`. */
  async function openWith(extra: Record<string, Reply>, tickets: Ticket[] = TICKETS) {
    const app = await openTab(tickets, extra);
    const dialog = await openTicket(/^18:00–19:00 · Tennis/);
    return { app, dialog };
  }

  function ended(exit_code: number): Reply {
    return reply({ ...RUNNING, running: false, exit_code });
  }

  it("cancels the ticket in the app once asked, and says when it is done", async () => {
    const { app, dialog } = await openWith({
      "POST /api/tickets/1000002/cancel": reply(RUNNING, 202),
      "GET /api/tickets/cancel": ended(0),
    });

    fireEvent.click(within(dialog).getByRole("button", { name: "Huỷ vé" }));
    const asked = within(dialog).getByRole("region", { name: "Huỷ vé" });
    expect(asked.textContent).toContain(
      "Huỷ vé 18:00–19:00 · Tennis S6, Thứ Sáu 16/10? App Vinhomes trên Máy 1 sẽ huỷ vé",
    );
    expect(requestsTo(app.fetch, "POST /api/tickets/1000002/cancel")).toBe(0);

    fireEvent.click(within(asked).getByRole("button", { name: "Có, huỷ vé" }));

    expect(await within(dialog).findByText(/^Đang huỷ vé trong app Vinhomes/)).toBeVisible();
    expect(
      await within(dialog).findByText("Đã huỷ vé, hạn mức đã được hoàn.", {}, { timeout: 4000 }),
    ).toBeVisible();
    expect(requestsTo(app.fetch, "POST /api/tickets/1000002/cancel")).toBe(1);
  });

  it("sends nothing when the answer is no", async () => {
    const { app, dialog } = await openWith({ "GET /api/tickets/cancel": reply({}) });

    fireEvent.click(within(dialog).getByRole("button", { name: "Huỷ vé" }));
    fireEvent.click(within(dialog).getByRole("button", { name: "Không" }));

    expect(within(dialog).queryByRole("region", { name: "Huỷ vé" })).not.toBeInTheDocument();
    expect(requestsTo(app.fetch, "POST /api/tickets/1000002/cancel")).toBe(0);
  });

  it("says why when the backend refuses it", async () => {
    const { dialog } = await openWith({
      "POST /api/tickets/1000002/cancel": reply(
        { error: "lock_held", detail: "Another run is in progress" },
        409,
      ),
      "GET /api/tickets/cancel": reply({}),
    });

    fireEvent.click(within(dialog).getByRole("button", { name: "Huỷ vé" }));
    fireEvent.click(within(dialog).getByRole("button", { name: "Có, huỷ vé" }));

    expect(
      await within(dialog).findByText("Đang có một lần chạy khác. Hãy chờ nó xong rồi thử lại."),
    ).toBeVisible();
  });

  it("says why when the app did not cancel it", async () => {
    const { dialog } = await openWith({
      "POST /api/tickets/1000002/cancel": reply(RUNNING, 202),
      "GET /api/tickets/cancel": ended(5),
    });

    fireEvent.click(within(dialog).getByRole("button", { name: "Huỷ vé" }));
    fireEvent.click(within(dialog).getByRole("button", { name: "Có, huỷ vé" }));

    expect(
      await within(dialog).findByText(
        "Máy này đang chạy một lượt khác. Hãy thử lại sau.",
        {},
        { timeout: 4000 },
      ),
    ).toBeVisible();
  });

  it("says so, and sends nothing, for a ticket whose account is on no machine", async () => {
    const tickets = TICKETS.map((item) =>
      item.code === "1000002" ? { ...item, machine: null } : item,
    );
    const { app, dialog } = await openWith({ "GET /api/tickets/cancel": reply({}) }, tickets);

    fireEvent.click(within(dialog).getByRole("button", { name: "Huỷ vé" }));

    expect(within(dialog).getByRole("region", { name: "Huỷ vé" }).textContent).toContain(
      "không gắn máy nào",
    );
    expect(within(dialog).queryByRole("button", { name: "Có, huỷ vé" })).not.toBeInTheDocument();
    expect(requestsTo(app.fetch, "POST /api/tickets/1000002/cancel")).toBe(0);
  });

  it("offers no cancel for a slot begun already", async () => {
    await openTab([ticket("1000006", { play_date: "2026-10-15", slot: "08:00 - 09:00" })], {
      "GET /api/tickets/cancel": reply({}),
    });
    const dialog = await openTicket(/^08:00–09:00 · Tennis/);

    expect(within(dialog).queryByRole("button", { name: "Huỷ vé" })).not.toBeInTheDocument();
  });
});

describe("Tickets views", () => {
  it("shows the week as a grid of days and slots, the tickets not sent marked", async () => {
    await openTab([
      ticket("1000002", { slot: "18:00 - 19:00", sent_at: "2026-10-15T07:00:00", ...AN }),
      ticket("1000004", { play_date: "2026-10-17", slot: "17:00 - 18:00", ...BINH }),
    ]);
    fireEvent.click(await within(panel()).findByRole("button", { name: "Tuần" }));

    const grid = within(panel()).getByRole("table");
    const head = within(grid)
      .getAllByRole("columnheader")
      .map((cell) => cell.textContent);
    expect(head.slice(1, 4)).toEqual(["T5 15/10", "T6 16/10", "T7 17/10"]);
    const rows = within(grid).getAllByRole("row").slice(1);
    expect(rows.map((row) => within(row).getByRole("rowheader").textContent)).toEqual([
      "17:00–18:00",
      "18:00–19:00",
    ]);
    expect(within(grid).getByRole("button", { name: /Chị Bình/ })).toHaveAttribute(
      "title",
      "chưa gửi",
    );

    fireEvent.click(within(grid).getByRole("button", { name: /Anh An/ }));
    expect(screen.getByRole("dialog")).toHaveAccessibleName("18:00–19:00 · Tennis S6");
  });

  it("keeps the tickets not sent yet, and those of one sport", async () => {
    await openTab([
      ticket("1000002", { sent_at: "2026-10-15T07:00:00", ...AN }),
      ticket("1000004", {
        slot: "17:00 - 18:00",
        sport: "pickleball",
        court: "S9 - Sân Pickleball",
      }),
    ]);
    await days();

    fireEvent.click(within(panel()).getByRole("button", { name: "Chưa gửi khách" }));
    expect((await days()).flat().join(" ")).not.toContain("18:00–19:00");

    fireEvent.click(within(panel()).getByRole("button", { name: "Chưa gửi khách" }));
    fireEvent.click(within(panel()).getByRole("button", { name: "Tennis" }));
    expect((await days()).flat().join(" ")).not.toContain("Pickleball");
  });

  it("marks a ticket sent, or not, from its card", async () => {
    const app = await openTab(
      [ticket("1000002", AN), ticket("1000003", { slot: "19:00 - 20:00", sent_at: "x", ...AN })],
      {
        "PUT /api/tickets/1000002/sent": { status: 204, body: null },
        "PUT /api/tickets/1000003/sent": { status: 204, body: null },
      },
    );
    const first = await within(panel()).findByRole("button", {
      name: "Đã gửi cho khách: 18:00–19:00 · Tennis S6",
    });
    const second = within(panel()).getByRole("button", {
      name: "Đã gửi cho khách: 19:00–20:00 · Tennis S6",
    });
    expect([first, second].map((button) => button.getAttribute("aria-pressed"))).toEqual([
      "false",
      "true",
    ]);
    expect(second).toHaveTextContent("Đã gửi");

    fireEvent.click(first);
    fireEvent.click(second);

    await waitFor(() => expect(requestsTo(app.fetch, "PUT /api/tickets/1000002/sent")).toBe(1));
    await waitFor(() => expect(requestsTo(app.fetch, "PUT /api/tickets/1000003/sent")).toBe(1));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument(); // the picture stays shut
  });

  it("marks a ticket sent from its picture", async () => {
    const app = await openTab(TICKETS, {
      "PUT /api/tickets/1000002/sent": { status: 204, body: null },
    });
    const dialog = await openTicket(/^18:00–19:00 · Tennis/);

    const mark = within(dialog).getByRole("button", { name: "Đã gửi cho khách" });
    expect(mark).toHaveAttribute("aria-pressed", "false");
    fireEvent.click(mark);

    await waitFor(() => expect(requestsTo(app.fetch, "PUT /api/tickets/1000002/sent")).toBe(1));
  });
});
