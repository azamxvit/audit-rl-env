import { describe, expect, it } from "vitest";
import { formatDate, formatMinor, formatTimestamp, lookupTarget, parseMajor, periodLabel } from "@/lib";

const EXPS = { USD: 2, JPY: 0, KZT: 2 };

describe("formatMinor", () => {
  it("formats minor units with the currency exponent", () => {
    expect(formatMinor(123456, "USD", EXPS)).toBe("1 234,56 USD".replace(" ", " "));
    expect(formatMinor(5, "USD", EXPS)).toBe("0,05 USD");
    expect(formatMinor(1500, "JPY", EXPS)).toBe("1 500 JPY");
  });
  it("marks negative amounts with a minus sign", () => {
    expect(formatMinor(-250, "USD", EXPS)).toBe("−2,50 USD");
  });
  it("falls back to exponent 2 for unknown currencies", () => {
    expect(formatMinor(100, "XXX", EXPS)).toBe("1,00 XXX");
  });
});

describe("parseMajor", () => {
  it.each([
    ["1234.56", 2, 123456],
    ["1 234,56", 2, 123456],
    ["0.5", 2, 50],
    ["7", 2, 700],
    ["1500", 0, 1500],
  ])("parses %s (exp %i) to %i minor units", (text, exp, minor) => {
    expect(parseMajor(text, exp)).toBe(minor);
  });
  it.each([["-1"], ["abc"], ["1.234"], [""], ["1e3"], ["1.5"]])("rejects %s", (text) => {
    expect(parseMajor(text, text === "1.5" ? 0 : 2)).toBeNull();
  });
});

describe("lookupTarget", () => {
  it("maps ID prefixes to tables or documents", () => {
    expect(lookupTarget("LR-ABC")).toEqual({ kind: "record", table: "ledger" });
    expect(lookupTarget("inv-abc")).toEqual({ kind: "record", table: "invoices" });
    expect(lookupTarget(" PAY-1 ")).toEqual({ kind: "record", table: "payments" });
    expect(lookupTarget("FXR-1")).toEqual({ kind: "record", table: "fx" });
    expect(lookupTarget("DOC-1")).toEqual({ kind: "document" });
    expect(lookupTarget("CUS-1")).toBeNull();
    expect(lookupTarget("whatever")).toBeNull();
  });
});

describe("dates", () => {
  it("formats ISO dates and timestamps for display", () => {
    expect(formatDate("2026-03-31")).toBe("31.03.2026");
    expect(periodLabel("2026-01-01", "2026-03-31")).toBe("01.01.2026 – 31.03.2026");
    expect(formatTimestamp("2026-03-31T23:30:00+05:00")).toBe("31.03.2026 23:30 (+05:00)");
  });
});
