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
  note: "gọi trước",
  accounts: [account("b1", { device: 1 }), account("b2", { label: "", phone: "09••••••22" })],
});
const BINH = customer("a2", { name: "Chị Bình" });

async function openTab(customers: Customer[] = [AN, BINH], extra: Record<string, Reply> = {}) {
  const app = renderApp(paths.overview, {
    "GET /api/status": reply(overview()),
    "GET /api/settings": reply(settings()),
    "GET /api/runs": reply([]),
    "GET /api/customers": reply(customers),
    ...extra,
  });
  await screen.findByRole("region", { name: "Lần đặt tiếp theo" });
  fireEvent.click(screen.getByRole("tab", { name: "Khách hàng" }));
  await within(panel()).findByRole("button", { name: "Thêm khách" });
  return app;
}

function panel() {
  return screen.getByRole("tabpanel", { name: "Khách hàng" });
}

function section(name: string) {
  return within(within(panel()).getByRole("region", { name }));
}

/** Read the JSON body of the last request to "METHOD /path". */
async function sent(fetch: Awaited<ReturnType<typeof openTab>>["fetch"], key: string) {
  const found = fetch.mock.calls
    .map(([request]) => request)
    .filter((request) => `${request.method} ${new URL(request.url).pathname}` === key)
    .at(-1);
  return found === undefined ? undefined : ((await found.clone().json()) as unknown);
}

function type(label: string, value: string) {
  fireEvent.change(within(panel()).getByLabelText(label), { target: { value } });
}

describe("CustomersTab list", () => {
  it("lists each customer with their accounts and the machine of each", async () => {
    await openTab();

    expect(section("Anh An").getByText("gọi trước")).toBeVisible();
    expect(
      section("Anh An")
        .getAllByRole("listitem")
        .map((item) => item.textContent),
    ).toEqual(["09••••••11Căn AMáy 2Sửa", "09••••••22Sửa"]);
    expect(section("Chị Bình").getByText("Chưa có tài khoản nào.")).toBeVisible();
  });

  it("says what to do without customers", async () => {
    await openTab([]);
    expect(within(panel()).getByText(/^Chưa có khách nào\./)).toBeVisible();
  });

  it("says when an account lost its saved login", async () => {
    await openTab([customer("a1", { accounts: [account("b1", { phone: null })] })]);
    expect(section("Anh An").getByText("mất mật khẩu, xóa rồi thêm lại")).toBeVisible();
  });

  it("is worded in English too", async () => {
    await i18n.changeLanguage("en");
    renderApp(paths.overview, {
      "GET /api/status": reply(overview()),
      "GET /api/customers": reply([AN]),
    });
    await screen.findByRole("region", { name: "Next booking" });
    fireEvent.click(screen.getByRole("tab", { name: "Customers" }));
    expect(await screen.findByRole("button", { name: "Add customer" })).toBeVisible();
    await i18n.changeLanguage("vi");
  });
});

describe("CustomersTab customers", () => {
  it("adds one, then reads the list again", async () => {
    const { fetch } = await openTab([], { "POST /api/customers": reply(BINH, 201) });
    fireEvent.click(within(panel()).getByRole("button", { name: "Thêm khách" }));
    type("Tên khách", "Chị Bình");
    type("Ghi chú", "mới");

    fireEvent.click(within(panel()).getByRole("button", { name: "Lưu" }));

    await waitFor(() => expect(requestsTo(fetch, "GET /api/customers")).toBe(2));
    expect(await sent(fetch, "POST /api/customers")).toEqual({ name: "Chị Bình", note: "mới" });
    expect(within(panel()).queryByRole("form")).not.toBeInTheDocument();
  });

  it("changes one", async () => {
    const { fetch } = await openTab([AN], { "PUT /api/customers/a1": reply(AN) });
    fireEvent.click(section("Anh An").getAllByRole("button", { name: "Sửa" })[0]!);
    expect(within(panel()).getByLabelText("Tên khách")).toHaveValue("Anh An");
    type("Tên khách", "An");

    fireEvent.click(within(panel()).getByRole("button", { name: "Lưu" }));

    await waitFor(() => expect(requestsTo(fetch, "PUT /api/customers/a1")).toBe(1));
    expect(await sent(fetch, "PUT /api/customers/a1")).toEqual({ name: "An", note: "gọi trước" });
  });

  it("does not remove one whose account books on a machine", async () => {
    await openTab([AN]);
    fireEvent.click(section("Anh An").getAllByRole("button", { name: "Sửa" })[0]!);
    expect(within(panel()).getByText(/^Đang gắn vào Máy 2\./)).toBeVisible();
    expect(within(panel()).queryByRole("button", { name: "Xóa" })).not.toBeInTheDocument();
  });

  it("removes one in two presses", async () => {
    const { fetch } = await openTab([BINH], { "DELETE /api/customers/a2": reply(null, 204) });
    fireEvent.click(section("Chị Bình").getByRole("button", { name: "Sửa" }));
    fireEvent.click(within(panel()).getByRole("button", { name: "Xóa" }));
    expect(requestsTo(fetch, "DELETE /api/customers/a2")).toBe(0);
    fireEvent.click(within(panel()).getByRole("button", { name: "Giữ lại" }));
    fireEvent.click(within(panel()).getByRole("button", { name: "Xóa" }));

    fireEvent.click(within(panel()).getByRole("button", { name: "Xóa thật" }));

    await waitFor(() => expect(requestsTo(fetch, "DELETE /api/customers/a2")).toBe(1));
  });
});

describe("CustomersTab accounts", () => {
  it("adds one and shows its password nowhere", async () => {
    const { fetch } = await openTab([BINH], {
      "POST /api/customers/a2/accounts": reply(BINH, 201),
    });
    fireEvent.click(section("Chị Bình").getByRole("button", { name: "Thêm tài khoản" }));
    expect(within(panel()).getByLabelText("Mật khẩu")).toHaveAttribute("type", "password");
    type("Số điện thoại", "0900000022");
    type("Mật khẩu", "mat-khau");
    type("Tên gợi nhớ, ví dụ Căn A", "Căn C");

    fireEvent.click(within(panel()).getByRole("button", { name: "Lưu" }));

    await waitFor(() => expect(within(panel()).queryByRole("form")).not.toBeInTheDocument());
    expect(await sent(fetch, "POST /api/customers/a2/accounts")).toEqual({
      phone: "0900000022",
      password: "mat-khau",
      label: "Căn C",
    });
    expect(document.body.innerHTML).not.toContain("mat-khau");
  });

  it("says why one was refused and keeps the form", async () => {
    await openTab([BINH], {
      "POST /api/customers/a2/accounts": reply({ error: "phone_taken", detail: "taken" }, 409),
    });
    fireEvent.click(section("Chị Bình").getByRole("button", { name: "Thêm tài khoản" }));
    type("Số điện thoại", "0900000022");
    type("Mật khẩu", "x");
    fireEvent.click(within(panel()).getByRole("button", { name: "Lưu" }));
    expect(await within(panel()).findByRole("alert")).toHaveTextContent(
      "Số này đã có ở một khách.",
    );
    expect(within(panel()).getByLabelText("Số điện thoại")).toHaveValue("0900000022");
  });

  it("keeps the password unless a new one is typed", async () => {
    const { fetch } = await openTab([AN], { "PUT /api/customer-accounts/b2": reply(AN) });
    const edit = () => section("Anh An").getAllByRole("button", { name: "Sửa" })[2]!;
    fireEvent.click(edit());
    expect(within(panel()).queryByLabelText("Số điện thoại")).not.toBeInTheDocument();
    type("Tên gợi nhớ, ví dụ Căn A", "Căn D");
    fireEvent.click(within(panel()).getByRole("button", { name: "Lưu" }));
    await waitFor(() => expect(within(panel()).queryByRole("form")).not.toBeInTheDocument());
    expect(await sent(fetch, "PUT /api/customer-accounts/b2")).toEqual({
      label: "Căn D",
      password: null,
    });

    fireEvent.click(edit());
    type("Mật khẩu mới (để trống nếu giữ nguyên)", "moi");
    fireEvent.click(within(panel()).getByRole("button", { name: "Lưu" }));
    await waitFor(() => expect(within(panel()).queryByRole("form")).not.toBeInTheDocument());
    expect(await sent(fetch, "PUT /api/customer-accounts/b2")).toEqual({
      label: "",
      password: "moi",
    });
  });

  it("removes only one that is on no machine", async () => {
    const { fetch } = await openTab([AN], { "DELETE /api/customer-accounts/b2": reply(null, 204) });
    fireEvent.click(section("Anh An").getAllByRole("button", { name: "Sửa" })[1]!);
    expect(within(panel()).getByText(/^Đang gắn vào Máy 2\./)).toBeVisible();
    fireEvent.click(within(panel()).getByRole("button", { name: "Hủy" }));

    fireEvent.click(section("Anh An").getAllByRole("button", { name: "Sửa" })[2]!);
    fireEvent.click(within(panel()).getByRole("button", { name: "Xóa" }));
    fireEvent.click(within(panel()).getByRole("button", { name: "Xóa thật" }));
    await waitFor(() => expect(requestsTo(fetch, "DELETE /api/customer-accounts/b2")).toBe(1));
  });

  it("opens one form at a time", async () => {
    await openTab();
    fireEvent.click(section("Anh An").getByRole("button", { name: "Thêm tài khoản" }));
    fireEvent.click(section("Chị Bình").getByRole("button", { name: "Thêm tài khoản" }));
    expect(within(panel()).getAllByRole("form")).toHaveLength(1);
  });
});
