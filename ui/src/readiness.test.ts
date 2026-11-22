import { describe, expect, it } from "vitest";
import { machinesOf } from "./machines";
import { clashes, withoutAccount } from "./readiness";
import { account, customer } from "./test/customers";
import { settings } from "./test/settings";

/** MuMu instance `index` books `court` at `slots`. */
function instance(index: number, court: string, slots: string[]) {
  return {
    mumu_index: index,
    slots,
    subdivision: "",
    sport: "tennis",
    court,
    venue_keyword: "Origami",
  };
}

const S6 = "S6 - Sân tennis";
const S8 = "S8 - Sân tennis";
const TWO = settings({
  court: S6,
  slots: ["18:00 - 19:00", "19:00 - 20:00"],
  instances: [instance(1, S8, ["18:00 - 19:00"])],
});

describe("withoutAccount", () => {
  const machines = machinesOf(TWO);

  it("names the machines that book without a chosen account", () => {
    const an = customer("a1", { accounts: [account("b1", { device: 0 }), account("b2")] });
    expect(withoutAccount(machines, [an]).map(({ place }) => place)).toEqual([1]);
  });

  it("leaves out a machine switched off", () => {
    const an = customer("a1", {
      accounts: [account("b1", { device: 0 }), account("b2", { device: 1 })],
    });
    expect(withoutAccount(machines, [an])).toEqual([]); // machine 3 is off
  });

  it("asks for none while there is no account to choose", () => {
    expect(withoutAccount(machines, [])).toEqual([]);
    expect(withoutAccount(machines, [customer("a1")])).toEqual([]);
  });

  it("asks for none before the machines are known", () => {
    expect(
      withoutAccount(machinesOf(undefined), [customer("a1", { accounts: [account("b1")] })]),
    ).toEqual([]);
  });
});

describe("clashes", () => {
  it("is empty while every machine has a court or slot of its own", () => {
    expect(clashes(TWO, machinesOf(TWO))).toEqual([]);
  });

  it("names the court and slot that two machines would book", () => {
    const same = settings({
      court: S6,
      slots: ["18:00 - 19:00", "19:00 - 20:00"],
      instances: [instance(1, S8, ["18:00 - 19:00"]), instance(2, S6, ["19:00 - 20:00"])],
    });
    expect(clashes(same, machinesOf(same))).toEqual([
      { court: S6, slot: "19:00 - 20:00", places: [0, 2] },
    ]);
  });

  it("tells one court of two sports apart", () => {
    const sports = settings({
      court: "S9 - Sân tennis",
      slots: ["18:00 - 19:00"],
      instances: [instance(1, "S9 - Sân Pickleball", ["18:00 - 19:00"])],
    });
    expect(clashes(sports, machinesOf(sports))).toEqual([]);
  });
});
