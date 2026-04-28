import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { mapWithConcurrency } from "./mapWithConcurrency";

describe("mapWithConcurrency", () => {
  it("preserves result order and caps concurrency", async () => {
    const items = Array.from({ length: 12 }, (_, i) => i);
    let inFlight = 0;
    let maxInFlight = 0;
    const out = await mapWithConcurrency(items, 3, async (x) => {
      inFlight++;
      maxInFlight = Math.max(maxInFlight, inFlight);
      await new Promise((r) => setTimeout(r, 2));
      inFlight--;
      return x * 10;
    });
    assert.deepEqual(out, items.map((x) => x * 10));
    assert.ok(maxInFlight <= 3);
  });
});
