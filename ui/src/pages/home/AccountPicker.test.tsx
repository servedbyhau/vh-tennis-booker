import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { Customer } from "../../api/types";
import { paths } from "../../paths";
import { renderApp } from "../../test/app";
import { type Reply, reply, requestsTo } from "../../test/backend";
import { account, customer } from "../../test/customers";
import { overview } from "../../test/overview";
import { settings } from "../../test/settings";

describe("AccountPicker", () => {
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

  function openPicker(customers: Customer[], extra: Record<string, Reply> = {}) {
    const app = renderApp(paths.overview, {
      "GET /api/status": reply(overview()),
      "GET /api/settings": reply(settings()),
      "GET /api/runs": reply([]),
      "GET /api/customers": reply(customers),
      ...extra,
    });
    const panel = screen.getByRole("region", { name: "Thiết lập" });
    return { tab: within(panel), ...app };
  }

  function options(select: HTMLElement) {
    return within(select)
      .getAllByRole<HTMLOptionElement>("option")
      .map((option) => `${option.textContent}${option.disabled ? " (off)" : ""}`);
  }

  it("shows the customer and the account the machine books with", async () => {
    const { tab } = openPicker([AN, BINH]);

    expect(await tab.findByLabelText("Khách hàng")).toHaveValue("a1");
    expect(tab.getByLabelText("Tài khoản")).toHaveValue("b1");
    expect(options(tab.getByLabelText("Khách hàng"))).toEqual(["Không chọn", "Anh An", "Chị Bình"]);
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
    const { tab, fetch } = openPicker([AN, BINH], {
      "PUT /api/machines/0/account": reply(AN),
    });
    fireEvent.change(await tab.findByLabelText("Tài khoản"), { target: { value: "b2" } });

    await waitFor(() => expect(requestsTo(fetch, "PUT /api/machines/0/account")).toBe(1));
    await waitFor(() => expect(requestsTo(fetch, "GET /api/customers")).toBe(2));
  });

  it("attaches nothing while only the customer is chosen", async () => {
    const { tab, fetch } = openPicker([AN, BINH], {
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
    const { tab, fetch } = openPicker([AN], {
      "DELETE /api/machines/0/account": reply(null, 204),
    });
    fireEvent.change(await tab.findByLabelText("Khách hàng"), { target: { value: "" } });
    await waitFor(() => expect(requestsTo(fetch, "DELETE /api/machines/0/account")).toBe(1));
  });

  it("says what a machine without an account books with", async () => {
    const { tab } = openPicker([BINH]);
    expect(await tab.findByLabelText("Khách hàng")).toHaveValue("");
    expect(tab.queryByLabelText("Tài khoản")).not.toBeInTheDocument();
    expect(tab.getByText(/^Chưa chọn: máy đặt bằng tài khoản đang đăng nhập/)).toBeVisible();
  });

  it("says why an account was not attached", async () => {
    const { tab } = openPicker([AN], {
      "PUT /api/machines/0/account": reply({ error: "lock_held", detail: "running" }, 409),
    });
    fireEvent.change(await tab.findByLabelText("Tài khoản"), { target: { value: "b2" } });
    expect(await tab.findByRole("alert")).toHaveTextContent(
      "Đang có một lần chạy khác. Hãy chờ nó xong rồi thử lại.",
    );
    expect(tab.getByLabelText("Tài khoản")).toHaveValue("b1"); // as it is
  });

  it("points to the customers while there are none", async () => {
    const { tab } = openPicker([]);
    expect(await tab.findByText("Chưa có khách nào. Thêm ở trang Quản lý.")).toBeVisible();
  });
});
