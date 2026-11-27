import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { MachineSetup, SetupReport } from "../api/types";
import i18n from "../i18n";
import { renderApp } from "../test/app";
import { type Reply, reply, requestsTo } from "../test/backend";
import { account, customer } from "../test/customers";
import { overview } from "../test/overview";
import { settings } from "../test/settings";

const BUSY = "Đang có một lần chạy khác. Hãy chờ nó xong rồi thử lại.";

function machine(index: number, fields: Partial<MachineSetup> = {}): MachineSetup {
  return { mumu_index: index, screen: "ok", performance: "ok", app: "ok", ...fields };
}

/** A PC with MuMu instances 0 and 1, both with the app. */
function report(fields: Partial<SetupReport> = {}): SetupReport {
  return { mumu: "ok", wake_timers: "ok", machines: [machine(0), machine(1)], ...fields };
}

/** Machine 1 books with an account of Anh An. */
const CUSTOMERS = [customer("c1", { accounts: [account("a1", { device: 0 })] })];

interface Backend {
  setup?: Reply;
  keepOn?: boolean;
  customers?: unknown[];
  extra?: Record<string, Reply>;
}

// Only stand-in backends here: a real PUT /api/schedule rewrites the Windows task.
async function openPage(path: string, backend: Backend = {}) {
  const { setup = reply(report()), keepOn = true, customers = CUSTOMERS, extra = {} } = backend;
  const replies: Record<string, Reply> = {
    "GET /api/status": reply(overview()),
    "GET /api/settings": reply(settings()),
    "GET /api/mumu-instances": reply({ indexes: [0, 1] }),
    "GET /api/setup": setup,
    "GET /api/keep-on": reply({ on: keepOn, modern_standby: false }),
    "GET /api/customers": reply(customers),
    "GET /api/runs": reply([]),
    "GET /api/notifications": reply({ enabled: true, language: "vi" }),
    ...extra,
  };
  const app = renderApp(path, replies);
  const step = within(await screen.findByRole("region", { name: /./ }));
  return { replies, step, ...app };
}

/** The step shown, once its title is the one asked. */
async function stepNamed(name: string) {
  return within(await screen.findByRole("region", { name }));
}

beforeEach(() => {
  vi.useFakeTimers({ toFake: ["Date"] });
  vi.setSystemTime(new Date(2026, 9, 15, 10, 0));
});

afterEach(() => {
  vi.useRealTimers();
});

describe("SetupPage", () => {
  it("opens on the first step not done, and tells how many are", async () => {
    const { router } = await openPage("/setup", {
      setup: reply(report({ machines: [machine(0, { app: "user" }), machine(1)] })),
    });

    const app = await stepNamed("App Vinhomes");
    expect(app.getByText("Bước 4/6")).toBeVisible();
    expect(app.getByText("Chưa có app")).toBeVisible();
    expect(screen.getByText("5/6 bước xong")).toBeVisible();
    expect(router.state.location.search).toBe("?step=app");
    const steps = within(screen.getByRole("list", { name: "Các bước" }));
    expect(steps.getByRole("button", { name: /App Vinhomes/ })).toHaveTextContent("Cần làm");
    expect(steps.getByRole("button", { name: /Máy ảo/ })).toHaveTextContent("Xong");
  });

  it("goes from step to step", async () => {
    await openPage("/setup?step=mumu");
    const mumu = await stepNamed("MuMu Player");
    expect(mumu.getByText("Đã có MuMu Player")).toBeVisible();

    fireEvent.click(mumu.getByRole("button", { name: "Bước tiếp" }));
    const machines = await stepNamed("Máy ảo");
    fireEvent.click(machines.getByRole("button", { name: "Bước trước" }));
    await stepNamed("MuMu Player");

    fireEvent.click(screen.getByRole("button", { name: /Chạy thử và Tự đặt/ }));
    const daily = await stepNamed("Chạy thử và Tự đặt");
    expect(daily.getByRole("link", { name: "Xong, về Đặt sân" })).toHaveAttribute("href", "/");
  });

  it("checks again on demand, and says why the checks waited", async () => {
    const { fetch, replies } = await openPage("/setup?step=mumu");
    await stepNamed("MuMu Player");
    replies["GET /api/setup"] = reply({ error: "lock_held", detail: "busy" }, 409);

    fireEvent.click(screen.getByRole("button", { name: "Kiểm tra lại" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(BUSY);
    expect(requestsTo(fetch, "GET /api/setup")).toBe(2);
  });

  it("is worded in English too", async () => {
    await i18n.changeLanguage("en");
    await openPage("/setup?step=power");
    const power = await stepNamed("Keep the PC on");
    expect(power.getByText("Step 1 of 6")).toBeVisible();
    expect(screen.getByRole("link", { name: "Setup" })).toHaveAttribute("aria-current", "page");
  });
});

describe("SetupPage steps", () => {
  it("keeps the PC on while plugged in, and gives the values back when off", async () => {
    const { fetch, replies } = await openPage("/setup?step=power", { keepOn: false });
    const power = await stepNamed("Giữ máy luôn chạy");
    const toggle = await power.findByRole("switch", { name: "Giữ máy luôn chạy" });
    expect(toggle).not.toBeChecked();
    replies["PUT /api/keep-on"] = reply({ on: true, modern_standby: false });

    fireEvent.click(toggle);

    await waitFor(() => expect(toggle).toBeChecked());
    expect(requestsTo(fetch, "PUT /api/keep-on")).toBe(1);
    expect(power.getByText(/màn hình tắt sau 5 phút$/)).toBeVisible();
  });

  it("says how to install MuMu Player when the PC has none", async () => {
    await openPage("/setup", { setup: reply(report({ mumu: "user", machines: [] })) });
    const mumu = await stepNamed("MuMu Player");
    expect(mumu.getByText("Chưa có MuMu Player")).toBeVisible();
    expect(mumu.getByText(/^Tải ở mumuplayer.com/)).toBeVisible();
  });

  it("tells each machine, and one switched off stays off", async () => {
    await openPage("/setup?step=machines", {
      setup: reply(report({ machines: [machine(0, { performance: "fixable" }), machine(1)] })),
    });
    const machines = await stepNamed("Máy ảo");
    expect(machines.getByText("Tự chỉnh 2 nhân, 2 GB, 540×1600 khi chạy")).toBeVisible();
    expect(machines.getByText("2 nhân · 2 GB · 540×1600 · đang tắt")).toBeVisible();
    expect(machines.getByRole("button", { name: "Tạo máy ảo" })).toBeEnabled();
  });

  it("makes the MuMu instance of a machine that has none, after a question", async () => {
    const TASK = { code: null, machine: 0, started_at: "2026-10-15T10:00:00" };
    const { fetch } = await openPage("/setup?step=machines", {
      extra: {
        "POST /api/machines/new": reply({ ...TASK, running: true, exit_code: null }, 202),
        "GET /api/machines/new": reply({ ...TASK, running: false, exit_code: 0 }),
      },
    });
    const machines = await stepNamed("Máy ảo");

    fireEvent.click(machines.getByRole("button", { name: "Tạo máy ảo" }));
    expect(machines.getByText(/^Nhân bản máy ảo của Máy 1/)).toBeVisible();
    fireEvent.click(machines.getByRole("button", { name: "Tạo" }));

    await waitFor(() => expect(requestsTo(fetch, "POST /api/machines/new")).toBe(1));
    // Once made, MuMu's instances and the checks are read again.
    await waitFor(() => expect(requestsTo(fetch, "GET /api/setup")).toBe(2), { timeout: 4000 });
  });

  it("says the PC lacks the RAM for another machine, and does not offer it", async () => {
    await openPage("/setup?step=machines", {
      extra: { "GET /api/machines/room": reply({ room: false, reason: "ram" }) },
    });
    const machines = await stepNamed("Máy ảo");

    expect(await machines.findByText(/^Máy tính không đủ RAM cho máy ảo này/)).toBeVisible();
    expect(machines.getByRole("button", { name: "Tạo máy ảo" })).toBeDisabled();
  });

  it("installs the app from a file and checks again once done", async () => {
    const APP_TASK = { code: null, machine: 0, started_at: "2026-10-15T09:12:00" };
    const { fetch } = await openPage("/setup?step=app", {
      extra: {
        "POST /api/app/install": reply({ ...APP_TASK, running: true, exit_code: null }, 202),
        "GET /api/app/install": reply({ ...APP_TASK, running: false, exit_code: 0 }),
      },
    });
    const app = await stepNamed("App Vinhomes");

    fireEvent.change(app.getByLabelText("File APK hoặc XAPK của app Vinhomes"), {
      target: { files: [new File(["PK"], "vinhomes.xapk")] },
    });

    expect(
      await app.findByText("Đã cài app Vinhomes vào mọi máy ảo.", {}, { timeout: 4000 }),
    ).toBeVisible();
    await waitFor(() => expect(requestsTo(fetch, "GET /api/setup")).toBe(2));
  });

  it("offers to open a machine whose app is not known yet", async () => {
    const { fetch } = await openPage("/setup?step=app", {
      setup: reply(report({ machines: [machine(0, { app: "unknown" })] })),
      extra: { "POST /api/machines/0/open": { status: 204, body: null } },
    });
    const app = await stepNamed("App Vinhomes");
    expect(app.getByText("Chưa biết · mở máy để kiểm tra")).toBeVisible();

    fireEvent.click(app.getByRole("button", { name: "Mở MuMu 0 để xem màn hình" }));

    await waitFor(() => expect(requestsTo(fetch, "POST /api/machines/0/open")).toBe(1));
  });

  it("tells the machines that book without an account chosen", async () => {
    await openPage("/setup?step=accounts", { customers: [] });
    const accounts = await stepNamed("Tài khoản");
    expect(accounts.getByText("Chưa chọn tài khoản")).toBeVisible();
    expect(accounts.getByRole("link", { name: "Chọn ở Đặt sân" })).toHaveAttribute("href", "/");
  });

  it("ends with the daily booking and a dry run, not a booking now", async () => {
    await openPage("/setup?step=daily");
    const daily = await stepNamed("Chạy thử và Tự đặt");
    expect(daily.getByRole("switch", { name: "Tự đặt" })).toBeChecked();
    expect(daily.getByRole("button", { name: "Chạy thử" })).toBeVisible();
    expect(daily.queryByRole("button", { name: "Đặt ngay" })).not.toBeInTheDocument();
  });
});

describe("SetupPage in the header", () => {
  it("counts the steps left, and the status line leads to the step a booking lacks", async () => {
    const { router } = await openPage("/", {
      setup: reply(report({ machines: [machine(0, { app: "user" }), machine(1)] })),
      keepOn: false,
    });

    const link = await screen.findByRole("link", { name: "Thiết lập, còn 2 bước" });
    expect(link).toHaveTextContent("2");
    fireEvent.click(await screen.findByRole("link", { name: /^Máy 1 chưa có app Vinhomes/ }));

    await waitFor(() => expect(router.state.location.search).toBe("?step=app"));
  });

  it("checks no more on each focus outside the Setup page", async () => {
    const { fetch } = await openPage("/");
    await waitFor(() => expect(requestsTo(fetch, "GET /api/setup")).toBe(1));

    window.dispatchEvent(new Event("focus"));
    document.dispatchEvent(new Event("visibilitychange"));

    expect(requestsTo(fetch, "GET /api/setup")).toBe(1);
  });
});
