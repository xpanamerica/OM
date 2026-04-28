import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { enqueueUnauthorized401 } from "./unauthorized401Queue";

describe("enqueueUnauthorized401", () => {
  it("serializes concurrent handlers", async () => {
    const order: number[] = [];
    const slow = () =>
      new Promise<void>((resolve) => {
        order.push(1);
        setTimeout(() => {
          order.push(2);
          resolve();
        }, 20);
      });
    const fast = async () => {
      order.push(3);
    };
    await Promise.all([enqueueUnauthorized401(slow), enqueueUnauthorized401(fast)]);
    assert.deepEqual(order, [1, 2, 3]);
  });
});
