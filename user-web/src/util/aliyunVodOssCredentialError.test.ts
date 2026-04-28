import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { isLikelyStsOrSignatureError } from "./aliyunVodOssCredentialError";

describe("isLikelyStsOrSignatureError", () => {
  it("matches ali-oss style code", () => {
    assert.equal(isLikelyStsOrSignatureError({ code: "SecurityTokenExpired", message: "x" }), true);
    assert.equal(isLikelyStsOrSignatureError({ code: "InvalidAccessKeyId" }), true);
  });

  it("matches OSS XML snippet in message", () => {
    assert.equal(
      isLikelyStsOrSignatureError({
        message: '<?xml version="1.0"?><Error><Code>SecurityTokenExpired</Code></Error>',
        status: 403,
      }),
      true,
    );
    assert.equal(
      isLikelyStsOrSignatureError({
        message: "<Code>InvalidSecurityToken</Code>",
      }),
      true,
    );
  });

  it("excludes clock skew", () => {
    assert.equal(
      isLikelyStsOrSignatureError({ code: "RequestTimeTooSkewed", message: "skewed", status: 403 }),
      false,
    );
  });

  it("403 expired token text", () => {
    assert.equal(
      isLikelyStsOrSignatureError({ status: 403, message: "The provided token has expired." }),
      true,
    );
  });
});
