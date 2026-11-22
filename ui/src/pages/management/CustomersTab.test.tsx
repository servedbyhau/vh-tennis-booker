import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { Customer } from "../../api/types";
import i18n from "../../i18n";
import { paths } from "../../paths";
import { renderApp } from "../../test/app";
import { type Reply, reply, requestsTo } from "../../test/backend";
import { account, customer } from "../../test/customers";
import { overview } from "../../test/overview";
import { settings } from "../../test/settings";

const AN = customer("a1", {
  representative: "Nguyễn Văn An",
  contact: "Zalo An",
  note: "gọi trước",
  accounts: [account("b1", { device: 1 }), account("b2", { label: "", phone: "09••••••22" })],
});
const BINH = customer("a2", { name: "Chị Bình" });

async function openPage(customers: Customer[] = [AN, BINH], extra: Record<string, Reply> = {}) {
  const app = renderApp(paths.management, {
    "GET /api/status": reply(overview()),
    "GET /api/settings": reply(settings()),
    "GET /api/customers": reply(customers),
    ...extra,
  });
  await screen.findByRole("button", { name: "Thêm khách" });
  return app;
}

function card(name: string) {
  return within(screen.getByRole("region", { name }));
}

/** Read the JSON body of the last request to "METHOD /path". */
async function sent(fetch: Awaited<ReturnType<typeof openPage>>["fetch"], key: string) {
  const found = fetch.mock.calls
    .map(([request]) => request)
    .filter((request) => `${request.method} ${new URL(request.url).pathname}` === key)
    .at(-1);
  return found === undefined ? undefined : ((await found.clone().json()) as unknown);
}

function type(label: string, value: string) {
  fireEvent.change(screen.getByLabelText(label), { target: { value } });
}

function press(name: string, nth = 0) {
  fireEvent.click(screen.getAllByRole("button", { name })[nth]!);
}

/** The customers listed; the one shown in brackets. */
function listed() {
  return within(screen.getByRole("navigation", { name: "Khách hàng" }))
    .getAllByRole("button")
    .map((item) =>
      item.getAttribute("aria-current") === "true" ? `[${item.textContent}]` : item.textContent,
    );
}

function choose(name: RegExp) {
  fireEvent.click(
    within(screen.getByRole("navigation", { name: "Khách hàng" })).getByRole("button", { name }),
  );
}

describe("Management customers", () => {
  it("lists them, the first one shown with its accounts", async () => {
    await openPage();
    expect(listed()).toEqual(["[Anh AnNguyễn Văn An · 2 tài khoản]", "Chị Bình0 tài khoản"]);
    const facts = card("Anh An").getAllByRole("definition");
    expect(facts.map((fact) => fact.textContent)).toEqual([
      "Nguyễn Văn An",
      "Zalo An",
      "gọi trước",
    ]);
    expect(
      card("Anh An")
        .getAllByRole("row")
        .slice(1)
        .map((row) => row.textContent),
    ).toEqual(["09••••••11Căn ASửa", "09••••••22Sửa"]);
  });

  it("shows the one pressed, with no form left open, and keeps it in the address", async () => {
    const { router } = await openPage();
    press("Thêm tài khoản");
    choose(/^Chị Bình/);
    expect(card("Chị Bình").getByText("Chưa có tài khoản nào.")).toBeVisible();
    expect(card("Chị Bình").getByText(/^Chưa có thông tin liên hệ\./)).toBeVisible();
    expect(screen.queryByRole("form")).not.toBeInTheDocument();
    expect(router.state.location.search).toBe("?customer=a2");
    expect(listed()).toEqual(["Anh AnNguyễn Văn An · 2 tài khoản", "[Chị Bình0 tài khoản]"]);
  });

  it("says what to do without customers", async () => {
    await openPage([]);
    expect(screen.getByText(/^Chưa có khách nào\./)).toBeVisible();
  });

  it("adds one, its name ready to type, and shows it", async () => {
    const { fetch, router } = await openPage([AN], { "POST /api/customers": reply(BINH, 201) });
    press("Thêm khách");
    expect(screen.getByLabelText("Tên khách hoặc nhóm")).toHaveFocus();
    expect(listed()).toEqual(["Anh AnNguyễn Văn An · 2 tài khoản"]); // none shown meanwhile
    type("Tên khách hoặc nhóm", "Nhóm Bình");
    type("Người đại diện", "Chị Bình");
    type("Liên hệ (SĐT, Zalo)", "Zalo Bình");
    type("Ghi chú", "mới");
    press("Lưu");
    await waitFor(() => expect(router.state.location.search).toBe("?customer=a2"));
    expect(await sent(fetch, "POST /api/customers")).toEqual({
      name: "Nhóm Bình",
      representative: "Chị Bình",
      contact: "Zalo Bình",
      note: "mới",
    });
    expect(requestsTo(fetch, "GET /api/customers")).toBe(2);
    expect(screen.queryByRole("form")).not.toBeInTheDocument();
  });

  it("goes back to the one shown when adding is given up", async () => {
    await openPage([AN]);
    press("Thêm khách");
    press("Hủy");
    expect(card("Anh An").getByRole("heading", { name: "Anh An" })).toBeVisible();
  });

  it("changes one", async () => {
    const { fetch } = await openPage([AN], { "PUT /api/customers/a1": reply(AN) });
    press("Sửa khách");
    expect(screen.getByLabelText("Tên khách hoặc nhóm")).toHaveValue("Anh An");
    type("Tên khách hoặc nhóm", "An");
    press("Lưu");
    await waitFor(() => expect(requestsTo(fetch, "PUT /api/customers/a1")).toBe(1));
    expect(await sent(fetch, "PUT /api/customers/a1")).toEqual({
      name: "An",
      representative: "Nguyễn Văn An",
      contact: "Zalo An",
      note: "gọi trước",
    });
  });

  it("does not remove one whose account is in use", async () => {
    await openPage([AN]);
    press("Sửa khách");
    expect(
      screen.getByText("Đang được một máy dùng để đặt. Bỏ chọn ở màn Đặt sân rồi mới xóa được."),
    ).toBeVisible();
    expect(screen.queryByRole("button", { name: "Xóa" })).not.toBeInTheDocument();
  });

  it("removes one in two presses", async () => {
    const { fetch } = await openPage([BINH], { "DELETE /api/customers/a2": reply(null, 204) });
    press("Sửa khách");
    press("Xóa");
    expect(requestsTo(fetch, "DELETE /api/customers/a2")).toBe(0);
    press("Giữ lại");
    press("Xóa");
    press("Xóa thật");
    await waitFor(() => expect(requestsTo(fetch, "DELETE /api/customers/a2")).toBe(1));
  });

  it("is worded in English too", async () => {
    await i18n.changeLanguage("en");
    renderApp(paths.management, {
      "GET /api/status": reply(overview()),
      "GET /api/customers": reply([AN]),
    });
    expect(await screen.findByRole("button", { name: "Add customer" })).toBeVisible();
    expect(screen.getByRole("heading", { name: "Vinhomes accounts" })).toBeVisible();
    await i18n.changeLanguage("vi");
  });
});

describe("Management accounts", () => {
  it("adds one and shows its password nowhere", async () => {
    const { fetch } = await openPage([BINH], {
      "POST /api/customers/a2/accounts": reply(BINH, 201),
    });
    press("Thêm tài khoản");
    expect(screen.getByLabelText("Mật khẩu")).toHaveAttribute("type", "password");
    type("Số điện thoại", "0900000022");
    type("Mật khẩu", "mat-khau");
    type("Tên gợi nhớ", "Căn C");
    press("Lưu");
    await waitFor(() => expect(screen.queryByRole("form")).not.toBeInTheDocument());
    expect(await sent(fetch, "POST /api/customers/a2/accounts")).toEqual({
      phone: "0900000022",
      password: "mat-khau",
      label: "Căn C",
    });
    expect(document.body.innerHTML).not.toContain("mat-khau");
  });

  it("says why one was refused and keeps the form", async () => {
    await openPage([BINH], {
      "POST /api/customers/a2/accounts": reply({ error: "phone_taken", detail: "taken" }, 409),
    });
    press("Thêm tài khoản");
    type("Số điện thoại", "0900000022");
    type("Mật khẩu", "x");
    press("Lưu");
    expect(await screen.findByRole("alert")).toHaveTextContent("Số này đã có ở một khách.");
    expect(screen.getByLabelText("Số điện thoại")).toHaveValue("0900000022");
  });

  it("keeps the password unless a new one is typed", async () => {
    const { fetch } = await openPage([AN], { "PUT /api/customer-accounts/b2": reply(AN) });
    press("Sửa", 1);
    expect(screen.queryByRole("textbox", { name: "Số điện thoại" })).not.toBeInTheDocument();
    type("Tên gợi nhớ", "Căn D");
    press("Lưu");
    await waitFor(() => expect(screen.queryByRole("form")).not.toBeInTheDocument());
    expect(await sent(fetch, "PUT /api/customer-accounts/b2")).toEqual({
      label: "Căn D",
      password: null,
    });

    press("Sửa", 1);
    type("Mật khẩu mới (để trống nếu giữ nguyên)", "moi");
    press("Lưu");
    await waitFor(() => expect(screen.queryByRole("form")).not.toBeInTheDocument());
    expect(await sent(fetch, "PUT /api/customer-accounts/b2")).toEqual({
      label: "",
      password: "moi",
    });
  });

  it("removes only one that is not in use", async () => {
    const { fetch } = await openPage([AN], {
      "DELETE /api/customer-accounts/b2": reply(null, 204),
    });
    press("Sửa", 0);
    expect(
      screen.getByText("Đang được một máy dùng để đặt. Bỏ chọn ở màn Đặt sân rồi mới xóa được."),
    ).toBeVisible();
    press("Sửa", 1); // the other account's form in its place
    press("Xóa");
    press("Xóa thật");
    await waitFor(() => expect(requestsTo(fetch, "DELETE /api/customer-accounts/b2")).toBe(1));
  });

  it("opens one form at a time", async () => {
    await openPage();
    press("Thêm tài khoản");
    press("Sửa khách");
    expect(screen.getAllByRole("form")).toHaveLength(1);
  });
});

describe("the two pages", () => {
  it("are a press apart in the header", async () => {
    await openPage();
    const pages = within(screen.getByRole("navigation", { name: "Trang" }));
    expect(pages.getByRole("link", { name: "Quản lý" })).toHaveAttribute("aria-current", "page");

    fireEvent.click(pages.getByRole("link", { name: "Đặt sân" }));

    expect(await screen.findByRole("region", { name: "Lần đặt tiếp theo" })).toBeInTheDocument();
    expect(pages.getByRole("link", { name: "Đặt sân" })).toHaveAttribute("aria-current", "page");
    expect(pages.getByRole("link", { name: "Quản lý" })).not.toHaveAttribute("aria-current");
  });
});
