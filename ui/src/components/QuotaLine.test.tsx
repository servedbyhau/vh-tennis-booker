import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { QuotaReading } from "../api/types";
import { QuotaLine } from "./QuotaLine";

function reading(fields: Partial<QuotaReading> = {}): QuotaReading {
  return {
    utility: "Sân Tennis",
    sport: "tennis",
    month: "2026-11",
    used: 7,
    month_limit: 8,
    read_at: "2026-11-24T05:46:12.000",
    ...fields,
  };
}

describe("QuotaLine", () => {
  it("shows what is left of each sport, and when it was read", () => {
    render(
      <QuotaLine
        quota={[reading(), reading({ utility: "Sân Pickleball", sport: "pickleball", used: 2 })]}
        month="2026-11"
      />,
    );

    const tennis = screen.getByTitle("đã dùng 7/8 của tháng 11/2026, đọc lúc 05:46 24/11");
    expect(tennis).toHaveTextContent(/^Tennis còn 1\/8 \(đã dùng 7\/8/);
    expect(tennis.className).not.toMatch(/none/);
    expect(screen.getByText(/^Pickleball còn 6\/8/)).toBeInTheDocument();
  });

  it("marks a sport with none left", () => {
    render(<QuotaLine quota={[reading({ used: 8 })]} month="2026-11" />);

    expect(screen.getByText(/^Tennis còn 0\/8/).className).toMatch(/none/);
  });

  it("shows nothing for an account never read, or read for another month", () => {
    const { container } = render(<QuotaLine quota={[]} month="2026-11" />);
    expect(container).toBeEmptyDOMElement();

    render(<QuotaLine quota={[reading({ month: "2026-12" })]} month="2026-11" />);
    expect(screen.queryByText(/Tennis/)).not.toBeInTheDocument();

    render(<QuotaLine quota={[reading()]} month={undefined} />);
    expect(screen.queryByText(/Tennis/)).not.toBeInTheDocument();
  });

  it("names a read that did not keep its sport in the app's words", () => {
    render(<QuotaLine quota={[reading({ sport: null })]} month="2026-11" />);

    expect(screen.getByText(/^Sân Tennis còn 1\/8/)).toBeInTheDocument();
  });
});
