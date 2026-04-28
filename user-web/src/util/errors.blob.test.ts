import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { tryReadApiErrorMessageFromBlob } from "./errors";
import { decodeAliyunVodB64Json } from "./decodeAliyunVodB64Json";

describe("tryReadApiErrorMessageFromBlob", () => {
  it("parses FastAPI-style JSON error", async () => {
    const body = JSON.stringify({ detail: "磁盘已满", code: "DISK_FULL" });
    const blob = new Blob([body], { type: "application/json" });
    const msg = await tryReadApiErrorMessageFromBlob(blob);
    assert.ok(msg?.includes("磁盘已满"));
    assert.ok(msg?.includes("DISK_FULL"));
  });

  it("returns null for non-JSON blob", async () => {
    const blob = new Blob([new Uint8Array([0xff, 0xd8, 0xff])], { type: "application/octet-stream" });
    assert.equal(await tryReadApiErrorMessageFromBlob(blob), null);
  });
});

describe("decodeAliyunVodB64Json", () => {
  it("rejects invalid base64", () => {
    assert.throws(() => decodeAliyunVodB64Json("###"), /Base64/);
  });

  it("decodes minimal JSON object", () => {
    const raw = btoa(JSON.stringify({ Endpoint: "https://oss-cn-test.aliyuncs.com", Bucket: "b", FileName: "o" }));
    const o = decodeAliyunVodB64Json(raw);
    assert.equal(String(o.Endpoint), "https://oss-cn-test.aliyuncs.com");
  });
});
