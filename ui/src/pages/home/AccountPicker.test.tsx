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
    account("b2", { label: "Căn B", phone: "0900000022" }),
    account("b3", { label: "", phone: "0900000033", device: 1 }),
  ],
});
const BINH = customer("a2", {
  name: "Chị Bình",
  accounts: [account("b4", { label: "", phone: null })],
});
/** A customer whose accounts no machine has. */
const FREE = customer("a3", {
  name: "Anh Cường",
  accounts: [account("b5", { label: "", phone: "0900000055" })],
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
  // The line at the top reads the customers too.
  await within(screen.getByRole("banner")).findByText(/●/);
  const machine = within(await screen.findByRole("region", { name: "Máy 1" }));
  const button = await machine.findByRole("button", { name: /^Tài khoản/ });
  return { ...app, machine, button };
}

/** Open the list and press `name`, a customer, to list their accounts. */
function openCustomer(
  machine: Awaited<ReturnType<typeof openMachine>>["machine"],
  button: HTMLElement,
  name: string,
) {
  fireEvent.click(button);
  fireEvent.click(machine.getByRole("button", { name: new RegExp(`^${name}`) }));
}

/** The customers or accounts listed, the one in use in brackets. */
function listed(list: HTMLElement) {
  return within(list)
    .getAllByRole<HTMLButtonElement>("button")
    .map((item) => {
      const text = `${item.textContent}${item.disabled ? " (off)" : ""}`;
      return item.getAttribute("aria-pressed") === "true" ? `[${text}]` : text;
    });
}

describe("AccountPicker", () => {
  it("shows the account in use under its title, and the customers once pressed", async () => {
    const { machine, button } = await openMachine([AN, BINH, customer("a4", { name: "Chưa có" })]);
    expect(button).toHaveTextContent("Tài khoản0900000011 · Căn A");
    expect(button).toHaveAttribute("aria-expanded", "false");
    expect(machine.queryByRole("group", { name: "Tài khoản" })).not.toBeInTheDocument();

    fireEvent.click(button);

    expect(button).toHaveAttribute("aria-expanded", "true");
    const list = machine.getByRole("group", { name: "Tài khoản" });
    expect(listed(list)).toEqual(["[Anh An3 tài khoản]", "Chị Bình1 tài khoản", "Không chọn"]);
    // A customer without accounts is none of them.
    expect(within(list).queryByText("Chưa có")).not.toBeInTheDocument();
    expect(within(list).getByRole("link", { name: "Quản lý khách hàng" })).toHaveAttribute(
      "href",
      paths.customers,
    );
  });

  it("lists a customer's accounts once pressed, and goes back to the customers", async () => {
    const { machine, button } = await openMachine([AN, BINH]);
    openCustomer(machine, button, "Anh An");

    const list = machine.getByRole("group", { name: "Tài khoản" });
    expect(listed(list)).toEqual([
      "Anh AnChọn khách khác",
      "[0900000011Căn A]",
      "0900000022Căn B",
      "0900000033đang ở Máy 2",
    ]);
    expect(within(list).getByRole("button", { name: /^Anh An/ })).toHaveFocus();

    fireEvent.click(within(list).getByRole("button", { name: /^Anh An/ }));
    fireEvent.click(machine.getByRole("button", { name: /^Chị Bình/ }));
    expect(listed(list)).toEqual([
      "Chị BìnhChọn khách khác",
      "mất mật khẩu, bấm sửa để nhập lại (off)",
    ]);
  });

  it("starts from the customers each time it opens", async () => {
    const { machine, button } = await openMachine([AN, BINH]);
    openCustomer(machine, button, "Chị Bình");
    fireEvent.click(button);
    fireEvent.click(button);

    expect(machine.getByRole("button", { name: /^Anh An/ })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
  });

  it("books with the account pressed, and shuts", async () => {
    const { machine, button, fetch } = await openMachine([AN, FREE], {
      "PUT /api/machines/0/account": reply(FREE),
    });
    const read = requestsTo(fetch, "GET /api/customers");
    openCustomer(machine, button, "Anh Cường");
    fireEvent.click(machine.getByRole("button", { name: /0900000055/ }));

    await waitFor(() => expect(button).toHaveAttribute("aria-expanded", "false"));
    expect(requestsTo(fetch, "PUT /api/machines/0/account")).toBe(1);
    expect(requestsTo(fetch, "GET /api/customers")).toBe(read + 1);
    expect(button).toHaveFocus();
  });

  it("asks before it takes the account of another machine", async () => {
    const { machine, button, fetch } = await openMachine([AN], {
      "PUT /api/machines/0/account": reply(AN),
    });
    openCustomer(machine, button, "Anh An");
    fireEvent.click(machine.getByRole("button", { name: /0900000033/ }));
    expect(machine.getByText("Chuyển từ Máy 2 sang Máy 1?")).toBeVisible();
    expect(requestsTo(fetch, "PUT /api/machines/0/account")).toBe(0);

    fireEvent.click(machine.getByRole("button", { name: "Thôi" }));
    expect(machine.queryByText(/sang Máy 1/)).not.toBeInTheDocument();

    fireEvent.click(machine.getByRole("button", { name: /0900000033/ }));
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
    openCustomer(machine, button, "Anh An");
    fireEvent.click(machine.getByRole("button", { name: /^0900000011/ }));
    expect(button).toHaveAttribute("aria-expanded", "false");
    expect(fetch.mock.calls.every(([request]) => request.method === "GET")).toBe(true);
  });

  it("shuts on Escape", async () => {
    const { machine, button } = await openMachine([AN]);
    openCustomer(machine, button, "Anh An");
    fireEvent.keyDown(machine.getByRole("button", { name: /0900000022/ }), { key: "Escape" });
    expect(button).toHaveAttribute("aria-expanded", "false");
    expect(button).toHaveFocus();
  });

  it("says what a machine without an account books with", async () => {
    const { button } = await openMachine([FREE]);
    expect(button).toHaveTextContent("Tài khoảnĐang theo tài khoản có sẵn trong MuMu");
  });

  it("says why an account was not taken, and keeps the list open", async () => {
    const { machine, button } = await openMachine([AN], {
      "PUT /api/machines/0/account": reply({ error: "lock_held", detail: "running" }, 409),
    });
    openCustomer(machine, button, "Anh An");
    fireEvent.click(machine.getByRole("button", { name: /0900000022/ }));
    expect(await machine.findByRole("alert")).toHaveTextContent(
      "Đang có một lần chạy khác. Hãy chờ nó xong rồi thử lại.",
    );
    expect(button).toHaveAttribute("aria-expanded", "true");
    expect(button).toHaveTextContent("0900000011"); // as it is
  });

  it("leads to the customers while there are none", async () => {
    const { machine, button } = await openMachine([]);
    fireEvent.click(button);
    expect(machine.getByRole("link", { name: "Quản lý khách hàng" })).toBeVisible();
  });
});
