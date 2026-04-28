import assert from "node:assert/strict";
import { afterEach, beforeEach, describe, it, mock } from "node:test";
import type { RouteLocationNormalizedLoaded, Router } from "vue-router";
import { handleAdminUnauthorizedRedirect } from "./handleAdminUnauthorized";

function mockRouter(partial: Partial<Router>): Router {
  return partial as unknown as Router;
}

function stubLoaded(partial: Partial<RouteLocationNormalizedLoaded>): RouteLocationNormalizedLoaded {
  return partial as RouteLocationNormalizedLoaded;
}

describe("handleAdminUnauthorizedRedirect", () => {
  let warnFn: ReturnType<typeof mock.fn>;
  beforeEach(() => {
    warnFn = mock.fn();
    mock.method(console, "warn", warnFn);
  });
  afterEach(() => {
    mock.restoreAll();
  });

  it("clearSession + replace when not on login", async () => {
    const clearSession = mock.fn();
    const replace = mock.fn(async () => {});
    const router = mockRouter({
      currentRoute: { value: stubLoaded({ name: "videos", fullPath: "/videos" }) },
      replace,
    });
    await handleAdminUnauthorizedRedirect({
      clearSession,
      getRouter: () => router,
      isDev: true,
    });
    assert.equal(clearSession.mock.calls.length, 1);
    assert.deepEqual(replace.mock.calls[0]?.arguments?.[0], {
      name: "login",
      query: { redirect: "/videos" },
    });
  });

  it("clearSession but no replace on login route", async () => {
    const clearSession = mock.fn();
    const replace = mock.fn();
    const router = mockRouter({
      currentRoute: { value: stubLoaded({ name: "login", fullPath: "/login" }) },
      replace,
    });
    await handleAdminUnauthorizedRedirect({
      clearSession,
      getRouter: () => router,
      isDev: true,
    });
    assert.equal(clearSession.mock.calls.length, 1);
    assert.equal(replace.mock.calls.length, 0);
  });

  it("warn when router missing", async () => {
    const clearSession = mock.fn();
    await handleAdminUnauthorizedRedirect({
      clearSession,
      getRouter: () => null,
      isDev: true,
    });
    assert.equal(clearSession.mock.calls.length, 1);
    assert.ok(warnFn.mock.calls.length >= 1);
  });
});
