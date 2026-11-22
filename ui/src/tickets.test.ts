import { describe, expect, it } from "vitest";
import { ticket } from "./test/tickets";
import {
  photoFileName,
  photoUrl,
  pickTickets,
  type TicketFilter,
  ticketDays,
  ticketDevices,
} from "./tickets";

const TODAY = "2026-10-15";
const ALL: TicketFilter = { period: "upcoming", device: null, withCancelled: true };

const TICKETS = [
  ticket("5", { play_date: "2026-10-17" }),
  ticket("4", { play_date: "2026-10-16", slot: "19:00 - 20:00", device: 1 }),
  ticket("3", { play_date: "2026-10-16", slot: "19:00 - 20:00", device: 0 }),
  ticket("2", { play_date: "2026-10-16", slot: "08:00 - 09:00", status: "cancelled" }),
  ticket("1", { play_date: TODAY }),
  ticket("0", { play_date: "2026-10-14" }),
];

function codes(filter: Partial<TicketFilter>): string[] {
  return pickTickets(TICKETS, { ...ALL, ...filter }, TODAY).map((item) => item.code);
}

describe("pickTickets", () => {
  it("keeps the tickets still to play, today's too, or those before today", () => {
    expect(codes({})).toEqual(["5", "4", "3", "2", "1"]);
    expect(codes({ period: "past" })).toEqual(["0"]);
  });

  it("keeps the tickets of one machine", () => {
    expect(codes({ device: 1 })).toEqual(["4"]);
  });

  it("leaves out the cancelled tickets unless asked for", () => {
    expect(codes({ withCancelled: false })).toEqual(["5", "4", "3", "1"]);
  });
});

describe("ticketDays", () => {
  it("lists the next day first, by slot and then by machine", () => {
    const days = ticketDays(pickTickets(TICKETS, ALL, TODAY), "upcoming");
    expect(days.map(({ day, tickets }) => [day, tickets.map((item) => item.code)])).toEqual([
      ["2026-10-15", ["1"]],
      ["2026-10-16", ["2", "3", "4"]],
      ["2026-10-17", ["5"]],
    ]);
  });

  it("lists the last day first among those past", () => {
    const past = [
      ticket("8", { play_date: "2026-10-01" }),
      ticket("9", { play_date: "2026-10-09" }),
    ];
    expect(ticketDays(past, "past").map(({ day }) => day)).toEqual(["2026-10-09", "2026-10-01"]);
  });

  it("lists the newer ticket of a slot booked again first", () => {
    const again = [ticket("100", { status: "cancelled" }), ticket("101")];
    expect(ticketDays(again, "upcoming")[0]?.tickets.map((item) => item.code)).toEqual([
      "101",
      "100",
    ]);
  });
});

describe("ticketDevices", () => {
  it("names each machine with tickets once", () => {
    expect(ticketDevices([...TICKETS, ticket("7", { device: 2 })])).toEqual([0, 1, 2]);
  });
});

describe("photoUrl", () => {
  it("changes when a run read the ticket again", () => {
    expect(photoUrl({ code: "1234567", seen_at: "2026-10-15T06:01:12.000" })).toBe(
      "/api/tickets/1234567/photo?seen=2026-10-15T06%3A01%3A12.000",
    );
  });
});

describe("photoFileName", () => {
  it("names the day, slot, court and code", () => {
    expect(photoFileName(ticket("1234567"), "Tennis S6")).toBe(
      "2026-10-16 18h00-19h00 Tennis S6 1234567.png",
    );
  });

  it("leaves out what a Windows file name cannot hold", () => {
    expect(photoFileName(ticket("1"), 'S1/2: "A"?')).toBe("2026-10-16 18h00-19h00 S12 A 1.png");
  });
});
