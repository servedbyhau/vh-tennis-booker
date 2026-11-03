import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { reply, stubBackend } from "../test/backend";
import { overview } from "../test/overview";
import { createTestQueryClient, withQueryClient } from "../test/queries";
import { UpdateButton } from "./UpdateButton";

const AFTERNOON = new Date(2026, 10, 3, 16, 0);

/** Stand in for the desktop window's commands; `install` decides how installing ends. */
function desktopWindow(newer: string | null, install = () => Promise.resolve(null)) {
  const invoke = vi.fn((command: string) =>
    command === "update_version" ? Promise.resolve(newer) : install(),
  );
  vi.stubGlobal("__TAURI_INTERNALS__", { invoke });
  return invoke;
}

/** Render the button with the backend telling `status`, at `now`. */
function renderButton(status = overview(), now = AFTERNOON) {
  stubBackend({ "GET /api/status": reply(status) });
  const Wrapper = withQueryClient(createTestQueryClient());
  return render(
    <Wrapper>
      <UpdateButton now={() => now} />
    </Wrapper>,
  );
}

describe("UpdateButton", () => {
  it("stays away in a browser, which cannot update the app", async () => {
    const { container } = renderButton();

    await waitFor(() => expect(container).toBeEmptyDOMElement());
  });

  it("stays away when this version is the newest", async () => {
    const invoke = desktopWindow(null);
    const { container } = renderButton();

    await waitFor(() => expect(invoke).toHaveBeenCalledWith("update_version"));
    expect(container).toBeEmptyDOMElement();
  });

  it("installs the newer version when pressed", async () => {
    const invoke = desktopWindow("1.0.1");
    renderButton();

    fireEvent.click(await screen.findByRole("button", { name: "Cập nhật lên 1.0.1" }));

    await waitFor(() => expect(invoke).toHaveBeenCalledWith("install_update"));
  });

  it("is locked while a run holds the lock", async () => {
    desktopWindow("1.0.1");
    const running = { pid: 7, trigger: "dry_run", since: "2026-11-03T15:59:00", runs: [] };
    renderButton(overview({ running }));

    expect(await screen.findByRole("button", { name: "Cập nhật lên 1.0.1" })).toBeDisabled();
    expect(
      screen.getByText("Cập nhật khi không có lần chạy nào và ngoài 05:50–06:05"),
    ).toBeVisible();
  });

  it("is locked in the quiet time around the booking", async () => {
    desktopWindow("1.0.1");
    renderButton(overview(), new Date(2026, 10, 4, 5, 55));

    expect(await screen.findByRole("button", { name: "Cập nhật lên 1.0.1" })).toBeDisabled();
  });

  it("tells when the update did not go through", async () => {
    desktopWindow("1.0.1", () => Promise.reject(new Error("offline")));
    renderButton();

    fireEvent.click(await screen.findByRole("button", { name: "Cập nhật lên 1.0.1" }));

    expect(await screen.findByText("Chưa cập nhật được, hãy thử lại sau")).toBeVisible();
    expect(screen.getByRole("button", { name: "Cập nhật lên 1.0.1" })).toBeEnabled();
  });
});
