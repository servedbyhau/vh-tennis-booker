import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { Customer } from "../../api/types";
import { paths } from "../../paths";
import { renderApp } from "../../test/app";
import { type Reply, reply, requestsTo } from "../../test/backend";
import { account, customer } from "../../test/customers";
import { overview } from "../../test/overview";
import { settings } from "../../test/settings";

const AN = customer("a1", {
  accounts: [
    account("b1", { device: 0 }),
    account("b2", { label: "Căn B", phone: "09••••••22" }),
    account("b3", { label: "", phone: "09••••••33", device: 1 }),
  ],
});
const BINH = customer("a2", {
  name: "Chị Bình",
  accounts: [account("b4", { label: "", phone: null })],
});
/** A customer whose accounts no machine has. */
const FREE = customer("a3", {
  name: "Anh Cường",
  accounts: [account("b5", { label: "", phone: "09••••••55" })],
});

/** The first machine's part of the Setup, its account read. */
async function openMachine(customers: Customer[], extra: Record<string, Reply> = {}) {
  const app = renderApp(paths.overview, {
    "GET /api/status": reply(overview()),
    "GET /api/settings": reply(settings()),
    "GET /api/runs": reply([]),
    "GET /api/customers": reply(customers),
    ...extra,
  });
  const machine = within(await screen.findByRole("region", { name: "Máy 1" }));
  const button = await machine.findByRole("button", { name: /^Tài khoản/ });
  return { ...app, machine, button };
}

/** The accounts listed, the one in use in brackets. */
function listed(list: HTMLElement) {
  return within(list)
    .getAllByRole<HTMLButtonElement>("button")
    .map((item) => {
      const text = `${item.textContent}${item.disabled ? " (off)" : ""}`;
      return item.getAttribute("aria-pressed") === "true" ? `[${text}]` : text;
    });
}

describe("AccountPicker", () => {
  it("shows the account in use, and every account once pressed", async () => {
    const { machine, button } = await openMachine([AN, BINH, customer("a4", { name: "Chưa có" })]);
    expect(button).toHaveTextContent("Anh An09••••••11 · Căn A");
    expect(button).toHaveAttribute("aria-expanded", "false");
    expect(machine.queryByRole("group", { name: "Tài khoản" })).not.toBeInTheDocument();

    fireEvent.click(button);

    expect(button).toHaveAttribute("aria-expanded", "true");
    const list = machine.getByRole("group", { name: "Tài khoản" });
    expect(listed(list)).toEqual([
      "[09••••••11Căn A]",
      "09••••••22Căn B",
      "09••••••33Máy 2 đang dùng",
      "mất mật khẩu, bấm sửa để nhập lại (off)",
      "Không chọnDùng tài khoản đang đăng nhập trên MuMu",
    ]);
    // By customer, those without accounts left out.
    expect(within(list).getByRole("group", { name: "Chị Bình" })).toBeVisible();
    expect(within(list).queryByText("Chưa có")).not.toBeInTheDocument();
    expect(within(list).getByRole("link", { name: "Thêm tài khoản" })).toHaveAttribute(
      "href",
      paths.management,
    );
  });

  it("books with the account pressed, and shuts", async () => {
    const { machine, button, fetch } = await openMachine([AN, FREE], {
      "PUT /api/machines/0/account": reply(FREE),
    });
    fireEvent.click(button);
    fireEvent.click(machine.getByRole("button", { name: /^09••••••55/ }));

    await waitFor(() => expect(button).toHaveAttribute("aria-expanded", "false"));
    expect(requestsTo(fetch, "PUT /api/machines/0/account")).toBe(1);
    expect(requestsTo(fetch, "GET /api/customers")).toBe(2);
    expect(button).toHaveFocus();
  });

  it("asks before it takes the account of another machine", async () => {
    const { machine, button, fetch } = await openMachine([AN], {
      "PUT /api/machines/0/account": reply(AN),
    });
    fireEvent.click(button);
    fireEvent.click(machine.getByRole("button", { name: /^09••••••33/ }));
    expect(machine.getByText("Máy 2 đang dùng tài khoản này. Chuyển sang Máy 1?")).toBeVisible();
    expect(requestsTo(fetch, "PUT /api/machines/0/account")).toBe(0);

    fireEvent.click(machine.getByRole("button", { name: "Thôi" }));
    expect(machine.queryByText(/Chuyển sang Máy 1/)).not.toBeInTheDocument();

    fireEvent.click(machine.getByRole("button", { name: /^09••••••33/ }));
    fireEvent.click(machine.getByRole("button", { name: "Chuyển" }));
    await waitFor(() => expect(requestsTo(fetch, "PUT /api/machines/0/account")).toBe(1));
  });

  it("books with none", async () => {
    const { machine, button, fetch } = await openMachine([AN], {
      "DELETE /api/machines/0/account": reply(null, 204),
    });
    fireEvent.click(button);
    fireEvent.click(machine.getByRole("button", { name: /^Không chọn/ }));
    await waitFor(() => expect(requestsTo(fetch, "DELETE /api/machines/0/account")).toBe(1));
  });

  it("sends nothing for the choice there is", async () => {
    const { machine, button, fetch } = await openMachine([AN]);
    fireEvent.click(button);
    fireEvent.click(machine.getByRole("button", { name: /^09••••••11/ }));
    expect(button).toHaveAttribute("aria-expanded", "false");
    expect(fetch.mock.calls.every(([request]) => request.method === "GET")).toBe(true);
  });

  it("shuts on Escape", async () => {
    const { machine, button } = await openMachine([AN]);
    fireEvent.click(button);
    fireEvent.keyDown(machine.getByRole("button", { name: /^09••••••22/ }), { key: "Escape" });
    expect(button).toHaveAttribute("aria-expanded", "false");
    expect(button).toHaveFocus();
  });

  it("says what a machine without an account books with", async () => {
    const { button } = await openMachine([FREE]);
    expect(button).toHaveTextContent("Chưa chọn tài khoảnDùng tài khoản đang đăng nhập trên MuMu");
  });

  it("says why an account was not taken, and keeps the list open", async () => {
    const { machine, button } = await openMachine([AN], {
      "PUT /api/machines/0/account": reply({ error: "lock_held", detail: "running" }, 409),
    });
    fireEvent.click(button);
    fireEvent.click(machine.getByRole("button", { name: /^09••••••22/ }));
    expect(await machine.findByRole("alert")).toHaveTextContent(
      "Đang có một lần chạy khác. Hãy chờ nó xong rồi thử lại.",
    );
    expect(button).toHaveAttribute("aria-expanded", "true");
    expect(button).toHaveTextContent("09••••••11"); // as it is
  });

  it("leads to the customers while there are none", async () => {
    const { machine, button } = await openMachine([]);
    fireEvent.click(button);
    expect(machine.getByRole("link", { name: "Thêm tài khoản" })).toBeVisible();
  });
});
