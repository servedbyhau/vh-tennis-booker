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
    expect(listed()).toEqual(["[Anh AnNguyễn Văn An22 tài khoản]", "Chị Bình00 tài khoản"]);
    const facts = card("Anh An").getAllByRole("definition");
    expect(facts.map((fact) => fact.textContent)).toEqual([
      "Nguyễn Văn An",
      "Zalo An",
      "gọi trước",
    ]);
    expect(
      card("Anh An")
        .getAllByRole("listitem")
        .map((row) => row.textContent),
    ).toEqual(["09••••••11Căn A", "09••••••22"]);
  });

  it("shows the one pressed, with no form left open, and keeps it in the address", async () => {
    const { router } = await openPage();
    press("Thêm tài khoản");
    choose(/^Chị Bình/);
    expect(card("Chị Bình").getByText("Chưa có tài khoản nào.")).toBeVisible();
    expect(card("Chị Bình").getByText("Chưa có thông tin liên hệ.")).toBeVisible();
    expect(screen.queryByRole("form")).not.toBeInTheDocument();
    expect(router.state.location.search).toBe("?customer=a2");
    expect(listed()).toEqual(["Anh AnNguyễn Văn An22 tài khoản", "[Chị Bình00 tài khoản]"]);
  });

  it("says what to do without customers", async () => {
    await openPage([]);
    expect(screen.getByText(/^Chưa có khách nào\./)).toBeVisible();
  });

  it("adds one, its name ready to type, and shows it", async () => {
    const { fetch, router } = await openPage([AN], { "POST /api/customers": reply(BINH, 201) });
    press("Thêm khách");
    expect(screen.getByLabelText("Tên khách hoặc nhóm")).toHaveFocus();
    expect(listed()).toEqual(["Anh AnNguyễn Văn An22 tài khoản"]); // none shown meanwhile
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
    press("Sửa");
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

  it("asks before it removes one, and says what is lost", async () => {
    const { fetch } = await openPage([AN], { "DELETE /api/customers/a1": reply(null, 204) });
    press("Xóa");
    const question = screen.getByRole("alertdialog", { name: "Xóa Anh An?" });
    expect(question).toHaveFocus(); // a second press removes nothing
    expect(question).toHaveTextContent("Mất luôn 2 tài khoản và mật khẩu đã lưu");
    expect(question).toHaveTextContent(
      "Máy 2 đang dùng 09••••••11, xóa rồi máy này không còn tài khoản.",
    );
    fireEvent.click(within(question).getByRole("button", { name: "Giữ lại" }));
    expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument();
    expect(requestsTo(fetch, "DELETE /api/customers/a1")).toBe(0);

    press("Xóa");
    fireEvent.click(within(screen.getByRole("alertdialog")).getByRole("button", { name: "Xóa" }));
    await waitFor(() => expect(requestsTo(fetch, "DELETE /api/customers/a1")).toBe(1));
    const [request] = fetch.mock.calls
      .map(([sentRequest]) => sentRequest)
      .filter((r) => r.method === "DELETE");
    expect(new URL(request!.url).search).toBe("?detach=true");
  });

  it("says why one was not removed", async () => {
    await openPage([AN], {
      "DELETE /api/customers/a1": reply({ error: "lock_held", detail: "running" }, 409),
    });
    press("Xóa");
    fireEvent.click(within(screen.getByRole("alertdialog")).getByRole("button", { name: "Xóa" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Đang có một lần chạy khác. Hãy chờ nó xong rồi thử lại.",
    );
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
  it("adds one, its password in plain sight until it is saved", async () => {
    const { fetch } = await openPage([BINH], {
      "POST /api/customers/a2/accounts": reply(BINH, 201),
    });
    press("Thêm tài khoản");
    expect(screen.getByLabelText("Mật khẩu")).not.toHaveAttribute("type", "password");
    type("Số điện thoại", "0900000022");
    type("Mật khẩu", "mat-khau");
    type("Tên", "Căn C");
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

  const LOGIN = reply({ phone: "0900000022", password: "cu" });

  it("fills the form with what is saved, and sends only what changed", async () => {
    const { fetch } = await openPage([AN], {
      "GET /api/customer-accounts/b2/login": LOGIN,
      "PUT /api/customer-accounts/b2": reply(AN),
    });
    expect(requestsTo(fetch, "GET /api/customer-accounts/b2/login")).toBe(0); // not before
    press("Sửa", 2);
    const form = await screen.findByRole("form");
    expect(
      [...form.querySelectorAll("label")].map((field) => [
        field.textContent,
        field.querySelector("input")?.value,
      ]),
    ).toEqual([
      ["Tên", ""],
      ["Số điện thoại", "0900000022"],
      ["Mật khẩu", "cu"],
    ]);
    type("Tên", "Căn D");
    press("Lưu");
    await waitFor(() => expect(screen.queryByRole("form")).not.toBeInTheDocument());
    expect(await sent(fetch, "PUT /api/customer-accounts/b2")).toEqual({
      label: "Căn D",
      phone: null,
      password: null,
    });
    expect(document.body.innerHTML).not.toContain("0900000022");

    press("Sửa", 2);
    await screen.findByRole("form");
    type("Số điện thoại", "0900000033");
    type("Mật khẩu", "moi");
    press("Lưu");
    await waitFor(() => expect(screen.queryByRole("form")).not.toBeInTheDocument());
    expect(await sent(fetch, "PUT /api/customer-accounts/b2")).toEqual({
      label: "",
      phone: "0900000033",
      password: "moi",
    });
    // Read anew each time: nothing keeps it.
    expect(requestsTo(fetch, "GET /api/customer-accounts/b2/login")).toBe(2);
  });

  it("asks for the whole login again once it is gone", async () => {
    await openPage([customer("a1", { accounts: [account("b1", { phone: null })] })], {
      "GET /api/customer-accounts/b1/login": reply({ phone: null, password: null }),
    });
    press("Sửa", 1);
    expect(await screen.findByLabelText("Số điện thoại")).toHaveValue("");
    expect(screen.getByLabelText("Số điện thoại")).toBeRequired();
    expect(screen.getByLabelText("Mật khẩu")).toBeRequired();
  });

  it("removes one after a question", async () => {
    const { fetch } = await openPage([AN], {
      "DELETE /api/customer-accounts/b2": reply(null, 204),
    });
    press("Xóa", 2); // the customer's, then one per account
    const question = screen.getByRole("alertdialog", { name: "Xóa 09••••••22?" });
    expect(question).toHaveTextContent("Mất luôn mật khẩu đã lưu, không lấy lại được.");
    expect(question).not.toHaveTextContent("đang dùng");
    fireEvent.click(within(question).getByRole("button", { name: "Xóa" }));
    await waitFor(() => expect(requestsTo(fetch, "DELETE /api/customer-accounts/b2")).toBe(1));
    await waitFor(() => expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument());
  });

  it("opens an account's form under it, and shuts it on a second press", async () => {
    await openPage([AN], {
      "GET /api/customer-accounts/b1/login": LOGIN,
    });
    press("Sửa", 1);
    const [first] = card("Anh An").getAllByRole("listitem");
    expect(await within(first!).findByRole("form")).toBeVisible();
    press("Sửa", 1);
    expect(screen.queryByRole("form")).not.toBeInTheDocument();
  });

  it("opens one form at a time", async () => {
    await openPage();
    press("Thêm tài khoản");
    press("Sửa");
    expect(screen.getAllByRole("form")).toHaveLength(1);
  });
});

describe("the pages", () => {
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
