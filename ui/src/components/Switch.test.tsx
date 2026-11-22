import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { Switch } from "./Switch";

describe("Switch", () => {
  it("is a named switch that announces its state", () => {
    render(<Switch label="Hẹn giờ mỗi sáng" checked onChange={() => undefined} />);

    expect(screen.getByRole("switch", { name: "Hẹn giờ mỗi sáng" })).toBeChecked();
  });

  it("asks for the other state when clicked", () => {
    const onChange = vi.fn();
    render(<Switch label="Hẹn giờ mỗi sáng" checked={false} onChange={onChange} />);

    const control = screen.getByRole("switch", { name: "Hẹn giờ mỗi sáng" });
    expect(control).not.toBeChecked();
    fireEvent.click(control);

    expect(onChange).toHaveBeenCalledWith(true);
  });

  it("ignores clicks while disabled", () => {
    const onChange = vi.fn();
    render(<Switch label="Hẹn giờ mỗi sáng" checked disabled onChange={onChange} />);

    fireEvent.click(screen.getByRole("switch", { name: "Hẹn giờ mỗi sáng" }));

    expect(onChange).not.toHaveBeenCalled();
  });
});
