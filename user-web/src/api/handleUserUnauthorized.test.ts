import assert from "node:assert/strict";
import { afterEach, beforeEach, describe, it, mock } from "node:test";
import type { RouteLocationMatched, RouteLocationNormalizedLoaded, Router } from "vue-router";
import { handleUserUnauthorizedRedirect, routeMatchedRequiresAuth } from "./handleUserUnauthorized";

function mockRouter(partial: Partial<Router>): Router {
  return partial as unknown as Router;
}

function stubMatched(metas: Record<string, unknown>[]): RouteLocationMatched[] {
  return metas.map((meta) => ({ meta }) as unknown as RouteLocationMatched);
}

function stubLoaded(partial: Partial<RouteLocationNormalizedLoaded>): RouteLocationNormalizedLoaded {
  return partial as RouteLocationNormalizedLoaded;
}

describe("routeMatchedRequiresAuth", () => {
  it("true when any matched route sets requiresAuth", () => {
    const router = mockRouter({
      currentRoute: { value: stubLoaded({ matched: stubMatched([{}, { requiresAuth: true }]) }) },
    });
    assert.equal(routeMatchedRequiresAuth(router), true);
  });

  it("false when no matched route requires auth", () => {
    const router = mockRouter({
      currentRoute: { value: stubLoaded({ matched: stubMatched([{}, { requiresAuth: false }]) }) },
    });
    assert.equal(routeMatchedRequiresAuth(router), false);
  });
});

describe("handleUserUnauthorizedRedirect", () => {
  let warnFn: ReturnType<typeof mock.fn>;
  beforeEach(() => {
    warnFn = mock.fn();
    mock.method(console, "warn", warnFn);
  });
  afterEach(() => {
    mock.restoreAll();
  });

  it("no-op when no token", async () => {
    const logout = mock.fn();
    const replace = mock.fn();
    await handleUserUnauthorizedRedirect({
      hadToken: false,
      logout,
      getRouter: () =>
        mockRouter({
          currentRoute: {
            value: stubLoaded({ matched: stubMatched([{ requiresAuth: true }]), fullPath: "/x" }),
          },
          replace,
        }),
      isDev: true,
    });
    assert.equal(logout.mock.calls.length, 0);
    assert.equal(replace.mock.calls.length, 0);
  });

  it("logout + replace when token existed and route requires auth", async () => {
    const logout = mock.fn();
    const replace = mock.fn(async () => {});
    const router = mockRouter({
      currentRoute: {
        value: stubLoaded({ matched: stubMatched([{ requiresAuth: true }]), fullPath: "/videos" }),
      },
      replace,
    });
    await handleUserUnauthorizedRedirect({
      hadToken: true,
      logout,
      getRouter: () => router,
      isDev: true,
    });
    assert.equal(logout.mock.calls.length, 1);
    assert.deepEqual(replace.mock.calls[0]?.arguments?.[0], {
      name: "auth",
      query: { redirect: "/videos" },
    });
  });

  it("logout but no replace when router missing", async () => {
    const logout = mock.fn();
    await handleUserUnauthorizedRedirect({
      hadToken: true,
      logout,
      getRouter: () => null,
      isDev: true,
    });
    assert.equal(logout.mock.calls.length, 1);
    assert.ok(warnFn.mock.calls.length >= 1);
  });
});
