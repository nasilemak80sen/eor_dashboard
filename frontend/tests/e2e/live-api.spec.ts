import { expect, test } from "@playwright/test";

const apiBase = process.env.EOR_API_URL || "http://127.0.0.1:8000";
const oidcBase = process.env.EOR_TEST_OIDC_URL || "http://127.0.0.1:8081";

test("Vue UI uses live FastAPI, enforces bearer auth, and renders real engine responses", async ({ page, request }) => {
  const pageErrors: string[] = [];
  const screeningStatuses: number[] = [];
  const hybridStatuses: number[] = [];
  page.on("pageerror", (error) => pageErrors.push(error.message));
  page.on("response", (response) => {
    if (response.url().endsWith("/api/v1/screening/evaluate")) screeningStatuses.push(response.status());
    if (response.url().endsWith("/api/v1/intelligence/evaluate")) hybridStatuses.push(response.status());
  });

  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Engineering screening" })).toBeVisible();
  await expect(page.locator(".pill")).toContainText("API online");

  // The app must surface a protected-route error if the user has no access token.
  await page.getByRole("button", { name: /Run engineering screening/ }).click();
  await expect(page.getByRole("alert")).toContainText("authentication_required");
  await expect(page.getByRole("alert")).toContainText("HTTP 401");
  expect(screeningStatuses).toContain(401);

  // Tokens come from a per-run local OIDC test fixture. No production credentials are used.
  const tokenResponse = await request.get(oidcBase + "/token");
  expect(tokenResponse.ok()).toBeTruthy();
  const tokenPayload = await tokenResponse.json() as { access_token: string };
  expect(tokenPayload.access_token).toBeTruthy();
  await page.locator("#token").fill(tokenPayload.access_token);
  await page.getByRole("button", { name: "Check connection" }).click();
  await expect(page.locator(".readiness")).toBeVisible();

  await page.getByRole("button", { name: /Run engineering screening/ }).click();
  await expect(page.locator(".summary")).toBeVisible();
  await expect(page.getByRole("heading", { name: "Engineering gate results" })).toBeVisible();
  await expect(page.getByText("Not saved", { exact: true })).toBeVisible();
  expect(screeningStatuses).toContain(200);

  // Switching to hybrid submits through the live CatBoost/hybrid service, not a UI-side calculation.
  await page.getByRole("button", { name: /Hybrid intelligence/ }).click();
  await expect(page.getByRole("heading", { name: "Hybrid intelligence" })).toBeVisible();
  await page.getByRole("button", { name: /Run hybrid evaluation/ }).click();
  await expect(page.locator(".summary")).toBeVisible();
  await expect(page.getByRole("heading", { name: "Engineering gate results" })).toBeVisible();
  await expect(page.getByText("Inspect complete API response")).toBeVisible();
  expect(hybridStatuses).toContain(200);

  // The authenticated server must return safe, structured validation errors and enforce required scope.
  const invalidInputs = await request.post(apiBase + "/api/v1/screening/evaluate", {
    headers: { Authorization: "Bearer " + tokenPayload.access_token },
    data: { formation: "Sandstone", inputs: { depth_ft: 5000 } },
  });
  expect(invalidInputs.status()).toBe(422);
  const invalidBody = await invalidInputs.json();
  expect(invalidBody.error.code).toBe("invalid_request");
  expect(JSON.stringify(invalidBody).toLowerCase()).not.toContain("traceback");
  expect(invalidInputs.headers()["x-correlation-id"]).toBeTruthy();

  const insufficientScopeResponse = await request.get(oidcBase + "/token?scope=not-the-required-scope");
  const insufficientScopeToken = (await insufficientScopeResponse.json() as { access_token: string }).access_token;
  const scopeDenied = await request.get(apiBase + "/api/v1/health/ready", {
    headers: { Authorization: "Bearer " + insufficientScopeToken },
  });
  expect(scopeDenied.status()).toBe(403);
  expect((await scopeDenied.json()).error.code).toBe("insufficient_scope");

  expect(pageErrors, "browser runtime should not emit uncaught page errors").toEqual([]);
});