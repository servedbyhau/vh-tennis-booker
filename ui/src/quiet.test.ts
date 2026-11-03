import { describe, expect, it } from "vitest";
import { inQuietTime, quietEnd } from "./quiet";

describe("quiet time", () => {
  it("ends 5 minutes after the start", () => {
    expect(quietEnd("06:00")).toBe("06:05");
  });

  it.each([
    [5, 44, false],
    [5, 45, true],
    [6, 0, true],
    [6, 4, true],
    [6, 5, false],
    [16, 0, false],
  ])("at %i:%i is %s from the wake time 05:45 to 06:05", (hours, minutes, quiet) => {
    expect(inQuietTime(new Date(2026, 10, 4, hours, minutes), "05:45", "06:00")).toBe(quiet);
  });
});
