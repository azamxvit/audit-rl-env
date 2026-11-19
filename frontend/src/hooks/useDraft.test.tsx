import { act, renderHook } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { useDraft } from "./useDraft";

const exponent = (c: string) => ({ USD: 2, JPY: 0 })[c] ?? 2;
const setup = (key = "draft:test") => renderHook(() => useDraft(key, "USD", exponent));

describe("useDraft", () => {
  it("starts empty with the base currency in the form", () => {
    const { result } = setup();
    expect(result.current.findings).toEqual([]);
    expect(result.current.form.currency).toBe("USD");
  });

  it("validates before saving", () => {
    const { result } = setup();
    let err: string | null = null;
    act(() => {
      err = result.current.saveForm();
    });
    expect(err).toMatch(/affected/);
    act(() => result.current.addTo("affected", "INV-1"));
    act(() => result.current.setForm((f) => ({ ...f, amount: "abc" })));
    act(() => {
      err = result.current.saveForm();
    });
    expect(err).toMatch(/Сумма/);
    act(() => result.current.setForm((f) => ({ ...f, amount: "10", currency: "US" })));
    act(() => {
      err = result.current.saveForm();
    });
    expect(err).toMatch(/Валюта/);
  });

  it("saves a finding in minor units and resets the form", () => {
    const { result } = setup();
    act(() => {
      result.current.addTo("affected", "PAY-1");
      result.current.addTo("affected", "INV-1");
      result.current.addTo("evidence", "DOC-1");
      result.current.addTo("evidence", "DOC-1"); // duplicates ignored
    });
    act(() => result.current.setForm((f) => ({ ...f, type: "payment_allocation", amount: "3206.54" })));
    act(() => {
      expect(result.current.saveForm()).toBeNull();
    });
    expect(result.current.findings).toEqual([
      {
        type: "payment_allocation",
        affected_ids: ["PAY-1", "INV-1"],
        claimed_amount_minor: 320654,
        currency: "USD",
        evidence_ids: ["DOC-1"],
        explanation: "",
      },
    ]);
    expect(result.current.form.affected).toEqual([]);
  });

  it("caps id lists at 10 entries", () => {
    const { result } = setup();
    act(() => {
      for (let i = 0; i < 12; i++) result.current.addTo("evidence", `LR-${i}`);
    });
    expect(result.current.form.evidence).toHaveLength(10);
  });

  it("edits and removes findings", () => {
    const { result } = setup();
    act(() => result.current.addTo("affected", "INV-1"));
    act(() => result.current.setForm((f) => ({ ...f, amount: "1.05" })));
    act(() => {
      result.current.saveForm();
    });
    act(() => result.current.edit(0));
    expect(result.current.form).toMatchObject({ editing: 0, amount: "1.05", affected: ["INV-1"] });
    act(() => result.current.setForm((f) => ({ ...f, amount: "2" })));
    act(() => {
      result.current.saveForm();
    });
    expect(result.current.findings).toHaveLength(1);
    expect(result.current.findings[0].claimed_amount_minor).toBe(200);
    act(() => result.current.remove(0));
    expect(result.current.findings).toEqual([]);
  });

  it("persists the draft per storage key", () => {
    const first = setup("draft:a");
    act(() => first.result.current.addTo("affected", "INV-1"));
    act(() => first.result.current.setForm((f) => ({ ...f, amount: "1" })));
    act(() => {
      first.result.current.saveForm();
    });
    first.unmount();
    expect(setup("draft:a").result.current.findings).toHaveLength(1);
    expect(setup("draft:b").result.current.findings).toHaveLength(0);
  });
});
