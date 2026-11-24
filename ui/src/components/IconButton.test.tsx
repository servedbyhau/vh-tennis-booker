import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { IconButton } from "./IconButton";

describe("IconButton", () => {
  it("is named by its label, which is its tooltip too", () => {
    const onClick = vi.fn();
    render(<IconButton icon="edit" label="Sửa" onClick={onClick} />);
    const button = screen.getByRole("button", { name: "Sửa" });
    expect(button).toHaveAttribute("title", "Sửa");
    expect(button).toHaveAttribute("type", "button");
    expect(button).toHaveTextContent("");
    fireEvent.click(button);
    expect(onClick).toHaveBeenCalledOnce();
  });
});
