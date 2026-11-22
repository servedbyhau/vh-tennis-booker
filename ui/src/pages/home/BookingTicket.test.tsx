import { act, fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { AccountSubdivision, Overview, ScheduleState, Settings } from "../../api/types";
import { paths } from "../../paths";
import { renderApp } from "../../test/app";
import { type Reply, reply, requestsTo } from "../../test/backend";
import { overview } from "../../test/overview";
import { settings } from "../../test/settings";

interface Backend {
  status?: Overview;
  saved?: Settings;
  /** The subdivision each account told last, as GET /api/accounts gives it. */
  accounts?: AccountSubdivision[];
  extra?: Record<string, Reply>;
}

// Only stand-in backends here: a real PUT /api/schedule rewrites the Windows task.
function renderTicket({
  status = overview(),
  saved = settings(),
  accounts = [],
  extra = {},
}: Backend = {}) {
  const replies: Record<string, Reply> = {
    "GET /api/status": reply(status),
    "GET /api/settings": reply(saved),
    "PUT /api/settings": reply(saved),
    "GET /api/runs": reply([]),
    "GET /api/accounts": reply(accounts),
    "GET /api/notifications": reply({ enabled: true, language: "vi" }),
    ...extra,
  };
  return { replies, ...renderApp(paths.overview, replies) };
}

/** The schedule with some fields changed. */
function schedule(fields: Partial<ScheduleState>): Overview {
  const status = overview();
  return { ...status, schedule: { ...status.schedule, ...fields } };
}

/** The values on top of the ticket: play day, court, slots. */
function shown(top: HTMLElement): (string | null)[] {
  return within(top)
    .getAllByRole("definition")
    .map((value) => value.textContent);
}

function ticket() {
  return screen.findByRole("region", { name: "Lần đặt tiếp theo" });
}

/** The bodies of the requests sent with `method` to `path`. */
async function bodies(
  fetch: ReturnType<typeof renderTicket>["fetch"],
  key: string,
): Promise<unknown[]> {
  const sent = fetch.mock.calls
    .map(([request]) => request)
    .filter((request) => `${request.method} ${new URL(request.url).pathname}` === key);
  return Promise.all(sent.map((request) => request.clone().json() as Promise<unknown>));
}

beforeEach(() => {
  // "Today" is 15/10: the next start, 16/10 at 06:00, is "sáng mai".
  vi.useFakeTimers({ toFake: ["Date"] });
  vi.setSystemTime(new Date(2026, 9, 15, 10, 0));
});

afterEach(() => {
  vi.useRealTimers();
});

describe("BookingTicket start", () => {
  it("shows what is set: the play day, court and slots, with no line while it is on", async () => {
    renderTicket();

    const top = await ticket();
    // The slots in booking order, without numbers: the choices below number them.
    await waitFor(() =>
      expect(shown(top)).toEqual(["CN 18/10", "Tennis S6", "15:00–16:0016:00–17:00"]),
    );
    expect(within(top).queryByText(/máy thức/)).toBeNull();
    expect(within(top).queryByRole("switch")).not.toBeInTheDocument(); // in the Setup
    expect(within(top).queryByText("Đang tắt")).not.toBeInTheDocument();
  });

  it("says that nothing is booked while the daily switch is off", async () => {
    renderTicket({ status: schedule({ enabled: false }) });
    const top = await ticket();
    expect(within(top).getByText("Đang tắt")).toBeInTheDocument();
    expect(within(top).getByText("Máy sẽ không tự đặt sân sáng mai.")).toBeInTheDocument();
  });
});

describe("BookingTicket choices", () => {
  it("offers no play day: it is always two days after the start", async () => {
    renderTicket();

    await screen.findByRole("group", { name: "Sân" });
    expect(screen.queryByRole("button", { name: /18\/10/ })).not.toBeInTheDocument();
  });

  it("shows the court and the slots in booking order, the rest blocked at two", async () => {
    renderTicket({ saved: settings({ slots: ["16:00 - 17:00", "15:00 - 16:00"] }) });

    const courts = await screen.findByRole("group", { name: "Sân" });
    expect(within(courts).getByRole("button", { name: "S6" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    const slots = screen.getByRole("group", { name: /^Khung giờ/ });
    expect(within(slots).getByRole("button", { name: "16:00–17:00, lượt 1" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    expect(within(slots).getByRole("button", { name: "15:00–16:00, lượt 2" })).toBeInTheDocument();
    expect(within(slots).getByRole("button", { name: "18:00–19:00" })).toHaveAttribute(
      "aria-disabled",
      "true",
    );
    expect(within(slots).getAllByRole("button")).toHaveLength(13);
    expect(within(slots).getByText("Bấm là lưu")).toBeInTheDocument();
  });

  it("saves a press at once, keeping the developer's settings", async () => {
    const saved = settings();
    const { fetch, replies } = renderTicket({ saved });
    const courts = await screen.findByRole("group", { name: "Sân" });
    replies["PUT /api/settings"] = reply({ ...saved, court: "S9 - Sân tennis" });

    fireEvent.click(within(courts).getByRole("button", { name: "S9" }));

    await waitFor(() =>
      expect(within(courts).getByRole("button", { name: "S9" })).toHaveAttribute(
        "aria-pressed",
        "true",
      ),
    );
    expect(await bodies(fetch, "PUT /api/settings")).toEqual([
      { ...saved, court: "S9 - Sân tennis" },
    ]);
    expect(await screen.findByText("✓ Đã lưu")).toBeInTheDocument();
  });

  it("offers each sport, and the courts of the one chosen", async () => {
    renderTicket({ saved: settings({ sport: "basketball", court: "S8 - Sân bóng rổ nửa sân" }) });

    const sports = await screen.findByRole("group", { name: "Môn" });
    expect(within(sports).getAllByRole("button")).toHaveLength(8);
    expect(within(sports).getByRole("button", { name: "Bóng rổ" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    const courts = screen.getByRole("group", { name: "Sân" });
    expect(within(courts).getAllByRole("button")).toHaveLength(7);
    expect(within(courts).getByRole("button", { name: "S8 · nửa sân" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    expect(shown(await ticket())[1]).toBe("Bóng rổ S8 · nửa sân");
  });

  it("shows the subdivision of the account until one is pressed", async () => {
    renderTicket({
      saved: settings({ court: "BE7 - Sân tennis" }),
      accounts: [{ device: 0, subdivision: "bs", seen_at: "2026-10-15T05:50:10.000" }],
    });

    const subdivisions = await screen.findByRole("group", { name: /Phân khu/ });
    await waitFor(() =>
      expect(within(subdivisions).getByRole("button", { name: "BS" })).toHaveAttribute(
        "aria-pressed",
        "true",
      ),
    );
    expect(within(subdivisions).getByText("Theo tài khoản")).toBeInTheDocument();
    const sports = screen.getByRole("group", { name: "Môn" });
    expect(within(sports).getAllByRole("button")).toHaveLength(6);
    const courts = screen.getByRole("group", { name: "Sân" });
    expect(
      within(courts)
        .getAllByRole("button")
        .map((button) => button.textContent),
    ).toEqual(["BE7", "BCX3 · 01", "BCX3 · 02", "CX2 · 01", "CX2 · 02"]);
    expect(shown(await ticket())[1]).toBe("Tennis BE7");
  });

  it("saves another subdivision, keeping the sport it has, with its first court", async () => {
    const saved = settings({ sport: "multi", court: "S7 - Sân đa năng" });
    const { fetch, replies } = renderTicket({ saved });
    const subdivisions = await screen.findByRole("group", { name: /Phân khu/ });
    expect(within(subdivisions).queryByText("Theo tài khoản")).toBeNull();
    const bs = {
      ...saved,
      subdivision: "bs",
      sport: "volleyball",
      court: "BCX3 - Sân bóng chuyền hơi 01",
    };
    replies["PUT /api/settings"] = reply(bs);

    fireEvent.click(within(subdivisions).getByRole("button", { name: "BS" }));

    const sports = screen.getByRole("group", { name: "Môn" });
    await waitFor(() =>
      expect(within(sports).getByRole("button", { name: "Bóng chuyền" })).toHaveAttribute(
        "aria-pressed",
        "true",
      ),
    );
    expect(await bodies(fetch, "PUT /api/settings")).toEqual([bs]);
  });

  it("saves another sport with its first court", async () => {
    const saved = settings();
    const { fetch, replies } = renderTicket({ saved });
    const sports = await screen.findByRole("group", { name: "Môn" });
    const badminton = { ...saved, sport: "badminton", court: "S6 - Sân cầu lông" };
    replies["PUT /api/settings"] = reply(badminton);

    fireEvent.click(within(sports).getByRole("button", { name: "Cầu lông" }));

    const courts = screen.getByRole("group", { name: "Sân" });
    await waitFor(() =>
      expect(within(courts).getByRole("button", { name: "S6" })).toHaveAttribute(
        "aria-pressed",
        "true",
      ),
    );
    expect(within(courts).getAllByRole("button")).toHaveLength(3);
    expect(await bodies(fetch, "PUT /api/settings")).toEqual([badminton]);
  });

  it("shows a second machine, off, without an instance, and switches it on", async () => {
    const other = {
      mumu_index: 1,
      slots: ["15:00 - 16:00"],
      subdivision: "",
      sport: "tennis",
      court: "S6 - Sân tennis",
      venue_keyword: "Origami",
    };
    const { fetch, replies } = renderTicket();
    const instances = await screen.findByRole("group", { name: "Máy" });
    // Off: pale, and no setup of its own counted.
    const second = within(instances).getByRole("button", { name: "Máy 2, đang tắt" });

    fireEvent.click(second);

    const use = screen.getByRole("switch", { name: "Đặt sân bằng máy 2 (MuMu 1)" });
    expect(use).toHaveAttribute("aria-checked", "false");
    expect(screen.queryByRole("group", { name: "Sân" })).not.toBeInTheDocument();
    expect(
      screen.getByText("Máy 2 đang tắt. Bật ở Thiết lập để đặt bằng máy này."),
    ).toBeInTheDocument();

    replies["PUT /api/instances/1"] = reply(settings({ instances: [other] }));
    fireEvent.click(use);

    expect(await screen.findByRole("group", { name: "Sân" })).toBeInTheDocument();
    expect(await bodies(fetch, "PUT /api/instances/1")).toEqual([{ enabled: true }]);
    expect(screen.getByRole("switch", { name: "Đặt sân bằng máy 2 (MuMu 1)" })).toHaveAttribute(
      "aria-checked",
      "true",
    );
  });

  it("shows a third machine, off, and books with MuMu 2 once switched on", async () => {
    const third = {
      mumu_index: 2,
      slots: ["20:00 - 21:00"],
      subdivision: "",
      sport: "tennis",
      court: "S9 - Sân tennis",
      venue_keyword: "Origami",
    };
    const { fetch, replies } = renderTicket();
    const instances = await screen.findByRole("group", { name: "Máy" });

    fireEvent.click(within(instances).getByRole("button", { name: "Máy 3, đang tắt" }));

    const use = screen.getByRole("switch", { name: "Đặt sân bằng máy 3 (MuMu 2)" });
    expect(use).toHaveAttribute("aria-checked", "false");
    expect(
      screen.getByText("Máy 3 đang tắt. Bật ở Thiết lập để đặt bằng máy này."),
    ).toBeInTheDocument();

    replies["PUT /api/instances/2"] = reply(settings({ instances: [third] }));
    fireEvent.click(use);

    // Its own choices, while the second machine stays off in its place.
    const courts = await screen.findByRole("group", { name: "Sân" });
    expect(within(courts).getByRole("button", { name: "S9" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    expect(await bodies(fetch, "PUT /api/instances/2")).toEqual([{ enabled: true }]);
    expect(within(instances).getByRole("button", { name: "Máy 2, đang tắt" })).toBeVisible();
    expect(within(instances).getByRole("button", { name: /^Máy 3/ })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
  });

  it("shows and saves the choices of each MuMu instance", async () => {
    const other = {
      mumu_index: 1,
      slots: ["20:00 - 21:00"],
      subdivision: "",
      sport: "tennis",
      court: "S9 - Sân tennis",
      venue_keyword: "Origami",
    };
    const saved = settings({ instances: [other] });
    const { fetch, replies } = renderTicket({ saved });
    const instances = await screen.findByRole("group", { name: "Máy" });
    let courts = screen.getByRole("group", { name: "Sân" });
    expect(within(instances).getByRole("button", { name: /^Máy 1/ })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    expect(within(courts).getByRole("button", { name: "S6" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );

    fireEvent.click(within(instances).getByRole("button", { name: /^Máy 2/ }));

    courts = screen.getByRole("group", { name: "Sân" }); // the choices of another machine
    expect(within(courts).getByRole("button", { name: "S9" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    const slots = screen.getByRole("group", { name: /^Khung giờ/ });
    expect(within(slots).getByRole("button", { name: "20:00–21:00, lượt 1" })).toBeInTheDocument();
    expect(shown(await ticket())).toEqual(["CN 18/10", "Tennis S9", "20:00–21:00"]);
    const moved = { ...other, court: "S10 - Sân tennis" };
    replies["PUT /api/settings"] = reply({ ...saved, instances: [moved] });

    fireEvent.click(within(courts).getByRole("button", { name: "S10" }));

    await waitFor(() =>
      expect(within(courts).getByRole("button", { name: "S10" })).toHaveAttribute(
        "aria-pressed",
        "true",
      ),
    );
    // The first instance keeps its own court.
    expect(await bodies(fetch, "PUT /api/settings")).toEqual([{ ...saved, instances: [moved] }]);
  });

  it("marks the machines with something left to prepare", async () => {
    const other = {
      mumu_index: 1,
      slots: ["20:00 - 21:00"],
      subdivision: "",
      sport: "tennis",
      court: "S9 - Sân tennis",
      venue_keyword: "Origami",
    };
    renderTicket({ saved: settings({ instances: [other] }) });
    const instances = await screen.findByRole("group", { name: "Máy" });
    expect(
      within(instances).getByRole("button", { name: /^Máy 2.*còn việc chuẩn bị$/ }),
    ).toBeVisible();
    // Off: not one of those that book.
    expect(within(instances).getByRole("button", { name: "Máy 3, đang tắt" })).toBeVisible();
  });

  it("takes no press while a save is on its way", async () => {
    let answer: (response: Response) => void = () => undefined;
    const { fetch } = renderTicket();
    const courts = await screen.findByRole("group", { name: "Sân" });
    const stub = fetch.getMockImplementation();
    fetch.mockImplementation((request) =>
      request.method === "PUT"
        ? new Promise<Response>((resolve) => {
            answer = resolve;
          })
        : stub!(request),
    );

    fireEvent.click(within(courts).getByRole("button", { name: "S8" }));
    expect(await screen.findByText("Đang lưu…")).toBeInTheDocument();
    expect(shown(await ticket())[1]).toBe("Tennis S8"); // the top follows the press at once
    expect(within(courts).getByRole("button", { name: "S8" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    fireEvent.click(within(courts).getByRole("button", { name: "S9" }));

    expect(requestsTo(fetch, "PUT /api/settings")).toBe(1);
    await act(async () => {
      answer(Response.json(settings({ court: "S8 - Sân tennis" })));
      await Promise.resolve();
    });
    expect(await screen.findByText("✓ Đã lưu")).toBeInTheDocument();
  });

  it("adds a slot after the ones chosen", async () => {
    const saved = settings({ slots: ["18:00 - 19:00"] });
    const { fetch } = renderTicket({ saved });
    const slots = await screen.findByRole("group", { name: /^Khung giờ/ });

    fireEvent.click(within(slots).getByRole("button", { name: "07:00–08:00" }));

    await waitFor(async () =>
      expect(await bodies(fetch, "PUT /api/settings")).toEqual([
        { ...saved, slots: ["18:00 - 19:00", "07:00 - 08:00"] },
      ]),
    );
  });

  it("says why a third slot is not added, and saves nothing", async () => {
    const { fetch } = renderTicket();
    const slots = await screen.findByRole("group", { name: /^Khung giờ/ });

    fireEvent.click(within(slots).getByRole("button", { name: "18:00–19:00" }));

    expect(within(slots).getByText("Đã đủ 2 khung: bỏ một khung trước")).toBeInTheDocument();
    expect(requestsTo(fetch, "PUT /api/settings")).toBe(0);
  });

  it("keeps the last slot", async () => {
    const { fetch } = renderTicket({ saved: settings({ slots: ["18:00 - 19:00"] }) });
    const slots = await screen.findByRole("group", { name: /^Khung giờ/ });

    fireEvent.click(within(slots).getByRole("button", { name: "18:00–19:00, lượt 1" }));

    expect(within(slots).getByText("Cần ít nhất một khung giờ")).toBeInTheDocument();
    expect(requestsTo(fetch, "PUT /api/settings")).toBe(0);
  });

  it("shows more than two slots set by hand, and takes one off", async () => {
    const saved = settings({ slots: ["15:00 - 16:00", "16:00 - 17:00", "18:00 - 19:00"] });
    const { fetch } = renderTicket({ saved });
    const slots = await screen.findByRole("group", { name: /^Khung giờ/ });
    expect(within(slots).getByRole("button", { name: "18:00–19:00, lượt 3" })).toBeInTheDocument();

    fireEvent.click(within(slots).getByRole("button", { name: "15:00–16:00, lượt 1" }));

    await waitFor(async () =>
      expect(await bodies(fetch, "PUT /api/settings")).toEqual([
        { ...saved, slots: ["16:00 - 17:00", "18:00 - 19:00"] },
      ]),
    );
  });

  it("says why a save failed and shows the saved choice again", async () => {
    const invalid = reply({ error: "invalid_settings", detail: "court: unknown" }, 422);
    renderTicket({ extra: { "PUT /api/settings": invalid } });
    const courts = await screen.findByRole("group", { name: "Sân" });

    fireEvent.click(within(courts).getByRole("button", { name: "S10" }));

    expect(await screen.findByText("Một số cài đặt chưa hợp lệ.")).toBeInTheDocument();
    expect(within(courts).getByRole("button", { name: "S6" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
  });
});
