import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { describe, expect, it } from "vitest";
import { reply, stubBackend } from "../test/backend";
import { overview } from "../test/overview";
import { createTestQueryClient, withQueryClient } from "../test/queries";
import { SiteHeader } from "./SiteHeader";

function renderHeader() {
  stubBackend({ "GET /api/status": reply(overview({ version: "1.0.1" })) });
  const Wrapper = withQueryClient(createTestQueryClient());
  return render(
    <Wrapper>
      <MemoryRouter>
        <SiteHeader />
      </MemoryRouter>
    </Wrapper>,
  );
}

describe("SiteHeader", () => {
  it("shows the installed version beside the app's name", async () => {
    renderHeader();

    const version = await screen.findByText("v1.0.1");
    expect(version).toHaveAttribute("title", "Phiên bản 1.0.1");
  });
});
