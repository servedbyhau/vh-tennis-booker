import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { Customer, Overview } from "../../api/types";
import { STORAGE_KEY } from "../../manualSteps";
import { paths } from "../../paths";
import { renderApp } from "../../test/app";
import { type Reply, reply, requestsTo } from "../../test/backend";
import { account, customer } from "../../test/customers";
import { overview } from "../../test/overview";
import { settings } from "../../test/settings";

const ALL = { mumu: true, app: true, login: true };

/** Render the home screen on its Setup tab: a step is left, so it opens there. */
function renderSetup(status: Overview = overview(), extra: Record<string, Reply> = {}) {
  const replies: Record<string, Reply> = {
    "GET /api/status": reply(status),
    "GET /api/settings": reply(settings()),
    "GET /api/runs": reply([]),
    "GET /api/notifications": reply({ enabled: true, language: "vi" }),
    ...extra,
  };
  return { replies, ...renderApp(paths.overview, replies) };
}

/** The Setup tab, whatever its count. */
function setupTab() {
  return screen.findByRole("tabpanel", { name: /^Thiết lập/ });
}

beforeEach(() => {
  // "Today" is 15/10.
  vi.useFakeTimers({ toFake: ["Date"] });
  vi.setSystemTime(new Date(2026, 9, 15, 10, 0));
});

afterEach(() => {
  vi.useRealTimers();
});

describe("SetupTab first use", () => {
  it("starts with how to use it, while anything is left", async () => {
    renderSetup();

    const tab = await setupTab();
    const start = within(tab).getByRole("region", {
      name: "Court Booker đặt sân thay bạn lúc 06:00 mỗi sáng, kể cả khi bạn ngủ",
    });
    expect(
      within(start)
        .getAllByRole("listitem")
        .map((item) => item.textContent),
    ).toEqual([
      "Làm các việc thiết lập bên dưới, một lần.",
      "Chọn môn, sân và khung giờ trên vé bên trái.",
      'Bấm "Chạy thử ngay", đạt thì bật "Tự đặt".',
    ]);
  });

  it("keeps how to use it in the guide once everything is set up", async () => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(ALL));
    renderSetup();
    // Everything is set up: the panel opens on the History once the status is in.
    await within(screen.getByRole("banner")).findByText(/Sẵn sàng/);
    fireEvent.click(screen.getByRole("tab", { name: "Thiết lập" }));

    const tab = await setupTab();
    expect(within(tab).queryByRole("region", { name: /Court Booker đặt sân thay bạn/ })).toBeNull();
    expect(within(tab).getByText("Cách dùng trong 3 bước")).toBeInTheDocument();
  });
});

describe("SetupTab steps the user does", () => {
  it("ticks a step, keeps it in the browser and counts down the tasks", async () => {
    renderSetup();
    const tab = await setupTab();
    expect(screen.getByRole("tab", { name: "Thiết lập, còn 3 việc" })).toBeInTheDocument();

    fireEvent.click(within(tab).getByRole("checkbox", { name: /Đã cài MuMu Player/ }));

    expect(within(tab).getByRole("checkbox", { name: /Đã cài MuMu Player/ })).toBeChecked();
    expect(screen.getByRole("tab", { name: "Thiết lập, còn 2 việc" })).toBeInTheDocument();
    expect(JSON.parse(localStorage.getItem(STORAGE_KEY) ?? "")).toEqual({
      mumu: true,
      app: false,
      login: false,
    });
    expect(
      within(screen.getByRole("banner")).getByText(/Còn 2 việc thiết lập/),
    ).toBeInTheDocument();
  });

  it("checks nothing with the backend", async () => {
    const { fetch } = renderSetup();
    const tab = await setupTab();

    fireEvent.click(within(tab).getByRole("checkbox", { name: /Đã đăng nhập app Vinhomes/ }));

    expect(requestsTo(fetch, "GET /api/setup")).toBe(0);
    expect(fetch.mock.calls.every(([request]) => request.method === "GET")).toBe(true);
  });
});

describe("SetupTab account", () => {
  const AN = customer("a1", {
    accounts: [
      account("b1", { device: 0 }),
      account("b2", { label: "Căn B", phone: "09••••••22" }),
      account("b3", { label: "", phone: "09••••••33", device: 1 }),
    ],
  });
  const BINH = customer("a2", {
    name: "Chị Bình",
    accounts: [account("b4", { label: "", phone: "09••••••44" })],
  });

  async function openPicker(customers: Customer[], extra: Record<string, Reply> = {}) {
    const app = renderSetup(overview(), { "GET /api/customers": reply(customers), ...extra });
    const tab = await setupTab();
    return { tab: within(tab), ...app };
  }

  function options(select: HTMLElement) {
    return within(select)
      .getAllByRole<HTMLOptionElement>("option")
      .map((option) => `${option.textContent}${option.disabled ? " (off)" : ""}`);
  }

  it("shows the customer and the account the machine books with", async () => {
    const { tab } = await openPicker([AN, BINH]);

    expect(await tab.findByLabelText("Khách hàng")).toHaveValue("a1");
    expect(tab.getByLabelText("Tài khoản")).toHaveValue("b1");
    expect(options(tab.getByLabelText("Khách hàng"))).toEqual(["Không gắn", "Anh An", "Chị Bình"]);
    expect(options(tab.getByLabelText("Tài khoản"))).toEqual([
      "Chọn tài khoản (off)",
      "09••••••11 · Căn A",
      "09••••••22 · Căn B",
      "09••••••33 · đang ở Máy 2 (off)", // one account, one machine
    ]);
    expect(
      tab.getByText('Lượt chạy sau dùng tài khoản này. Bấm "Chạy thử ngay" để kiểm tra luôn.'),
    ).toBeVisible();
  });

  it("attaches the account picked", async () => {
    const { tab, fetch } = await openPicker([AN, BINH], {
      "PUT /api/machines/0/account": reply(AN),
    });
    fireEvent.change(await tab.findByLabelText("Tài khoản"), { target: { value: "b2" } });

    await waitFor(() => expect(requestsTo(fetch, "PUT /api/machines/0/account")).toBe(1));
    await waitFor(() => expect(requestsTo(fetch, "GET /api/customers")).toBe(2));
  });

  it("attaches nothing while only the customer is chosen", async () => {
    const { tab, fetch } = await openPicker([AN, BINH], {
      "PUT /api/machines/0/account": reply(BINH),
    });
    fireEvent.change(await tab.findByLabelText("Khách hàng"), { target: { value: "a2" } });

    expect(tab.getByLabelText("Tài khoản")).toHaveValue("");
    expect(tab.getByText(/^Chọn tài khoản để đổi\./)).toBeVisible();
    expect(fetch.mock.calls.every(([request]) => request.method === "GET")).toBe(true);

    fireEvent.change(tab.getByLabelText("Tài khoản"), { target: { value: "b4" } });
    await waitFor(() => expect(requestsTo(fetch, "PUT /api/machines/0/account")).toBe(1));
  });

  it("detaches with no customer", async () => {
    const { tab, fetch } = await openPicker([AN], {
      "DELETE /api/machines/0/account": reply(null, 204),
    });
    fireEvent.change(await tab.findByLabelText("Khách hàng"), { target: { value: "" } });
    await waitFor(() => expect(requestsTo(fetch, "DELETE /api/machines/0/account")).toBe(1));
  });

  it("says what a machine without an account books with", async () => {
    const { tab } = await openPicker([BINH]);
    expect(await tab.findByLabelText("Khách hàng")).toHaveValue("");
    expect(tab.queryByLabelText("Tài khoản")).not.toBeInTheDocument();
    expect(tab.getByText(/^Chưa gắn: máy đặt bằng tài khoản đang đăng nhập/)).toBeVisible();
  });

  it("says why an account was not attached", async () => {
    const { tab } = await openPicker([AN], {
      "PUT /api/machines/0/account": reply({ error: "lock_held", detail: "running" }, 409),
    });
    fireEvent.change(await tab.findByLabelText("Tài khoản"), { target: { value: "b2" } });
    expect(await tab.findByRole("alert")).toHaveTextContent(
      "Đang có một lần chạy khác. Hãy chờ nó xong rồi thử lại.",
    );
    expect(tab.getByLabelText("Tài khoản")).toHaveValue("b1"); // as it is
  });

  it("points to the customers while there are none", async () => {
    const { tab } = await openPicker([]);
    expect(await tab.findByText("Chưa có khách nào. Thêm ở tab Khách hàng.")).toBeVisible();
  });
});

describe("SetupTab without auto setup", () => {
  it("has no button: the runs and the daily switch set up MuMu and waking", async () => {
    renderSetup();

    const tab = await setupTab();
    expect(
      within(tab).queryByRole("button", { name: "Thiết lập tự động" }),
    ).not.toBeInTheDocument();
    expect(within(tab).queryByText("Court Booker làm thay bạn")).not.toBeInTheDocument();
  });
});

describe("SetupTab guide", () => {
  it("holds no notification switch: it is on the ticket", async () => {
    renderSetup();
    const tab = await setupTab();

    expect(within(tab).queryByRole("switch")).not.toBeInTheDocument();
  });

  it("opens a guide row on a press", async () => {
    renderSetup();
    const tab = await setupTab();
    const morning = within(tab).getByText("Mỗi sáng diễn ra thế nào").closest("details");
    expect(morning).not.toHaveAttribute("open");

    fireEvent.click(within(tab).getByText("Mỗi sáng diễn ra thế nào"));

    expect(morning).toHaveAttribute("open");
    expect(morning).toHaveTextContent(
      "05:50 máy tự thức dậy, mở MuMu và app Vinhomes. 06:00 đặt các khung đã chọn",
    );
    const trouble = within(tab).getByText("Khi có sự cố").closest("details");
    expect(trouble).toHaveTextContent('Báo "Hết chỗ"Khung đó có người đặt trước.');
  });
});
