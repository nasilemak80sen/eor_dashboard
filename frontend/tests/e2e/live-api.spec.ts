import { existsSync, readFileSync } from "node:fs";
import { expect, test } from "@playwright/test";

const apiBase = process.env.EOR_API_URL || "http://127.0.0.1:8000";
const oidcBase = process.env.EOR_TEST_OIDC_URL || "http://127.0.0.1:8081";
const approvedExpectedPath = process.env.EOR_APPROVED_EXPECTED_PATH || "/tmp/eor-approved-legacy-results.json";

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

  await page.getByRole("button", { name: /Run engineering screening/ }).click();
  await expect(page.getByRole("alert")).toContainText("authentication_required");
  await expect(page.getByRole("alert")).toContainText("HTTP 401");
  expect(screeningStatuses).toContain(401);

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

  await page.getByRole("button", { name: /Hybrid intelligence/ }).click();
  await expect(page.getByRole("heading", { name: "Hybrid intelligence" })).toBeVisible();
  await page.getByRole("button", { name: /Run hybrid evaluation/ }).click();
  await expect(page.locator(".summary")).toBeVisible();
  await expect(page.getByRole("heading", { name: "Engineering gate results" })).toBeVisible();
  await expect(page.getByText("Inspect complete API response")).toBeVisible();
  expect(hybridStatuses).toContain(200);

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

interface ExpectedCase {
  id: string;
  field_id?: string;
  formation: string;
  inputs: Record<string, unknown>;
  screening: { results: Record<string, unknown>[] };
  hybrid: { screening: Record<string, unknown>; hybrid: Record<string, unknown>; model_info: Record<string, unknown> };
}
interface ExpectedBundle { available: boolean; reason?: string; cases?: ExpectedCase[] }

test("approved real-reservoir cases match legacy Streamlit service outputs through the Vue UI/API", async ({ page, request }) => {
  if (!existsSync(approvedExpectedPath)) test.skip(true, "Approved real-reservoir fixture is not present; evidence parity stays blocked.");
  const bundle = JSON.parse(readFileSync(approvedExpectedPath, "utf-8")) as ExpectedBundle;
  if (!bundle.available || !bundle.cases?.length) test.skip(true, bundle.reason || "Approved real-reservoir cases are not available.");
  const cases = bundle.cases!;
  const tokenResponse = await request.get(oidcBase + "/token");
  expect(tokenResponse.ok()).toBeTruthy();
  const token = (await tokenResponse.json() as { access_token: string }).access_token;

  await page.goto("/");
  await page.locator("#token").fill(token);
  await page.getByRole("button", { name: "Check connection" }).click();
  await expect(page.locator(".readiness")).toBeVisible();

  const coreKeys = ["depth_ft", "reservoir_pressure", "temperature_c", "visc_cp", "api", "perm_md", "porosity_frac", "so_pct"];
  const advancedNumericKeys = ["salinity_ppm", "hardness_ppm", "net_pay_m", "ooip_mmstb", "base_rf_pct", "water_cut_pct"];
  const selectKeys = ["rock_type", "heterogeneity", "gas_availability", "oxygen_present", "drive_mechanism", "co2_availability", "mmp_satisfied", "waterflood_history", "field_maturity", "mobility_ratio", "adsorption_risk", "water_handling", "offshore", "water_injection_facilities", "gas_injection_facilities", "wag_ratio", "gas_injectivity", "water_injectivity", "gravity_override_risk", "hc_gas_availability", "produced_gor_category", "gas_reinjectable"];

  for (const approvedCase of cases) {
    const caseInputs = approvedCase.inputs;
    await page.getByRole("button", { name: /Engineering screening/ }).click();
    await page.locator("#fieldid").fill(approvedCase.field_id || approvedCase.id);
    await page.locator("#formation").selectOption(approvedCase.formation);
    for (const key of coreKeys) {
      let value = caseInputs[key];
      if (key === "porosity_frac" && value === undefined && typeof caseInputs.porosity_pct === "number") value = caseInputs.porosity_pct / 100;
      if (value !== undefined && value !== null) await page.locator("#" + key).fill(String(value));
    }
    for (const key of advancedNumericKeys) {
      const value = caseInputs[key];
      if (typeof value === "number") await page.locator("#" + key).fill(String(value));
    }
    for (const key of selectKeys) {
      const value = caseInputs[key];
      if (typeof value === "string") await page.locator("#" + key).selectOption({ label: value });
    }
    const hasSorw = typeof caseInputs.sorw_pct === "number";
    const hasGor = typeof caseInputs.produced_gor_scf_stb === "number";
    await page.locator("#sorw-available").setChecked(hasSorw);
    if (hasSorw) await page.locator("#sorw_pct").fill(String(caseInputs.sorw_pct));
    await page.locator("#gor-available").setChecked(hasGor);
    if (hasGor) await page.locator("#produced_gor_scf_stb").fill(String(caseInputs.produced_gor_scf_stb));

    await page.getByRole("button", { name: /Run engineering screening/ }).click();
    await expect(page.locator(".summary")).toBeVisible();
    await page.locator("details summary").click();
    const screenPayload = JSON.parse((await page.locator("details pre").textContent()) || "{}");
    expect(screenPayload.screening, approvedCase.id + " engineering-screen output").toEqual(approvedCase.screening);

    await page.getByRole("button", { name: /Hybrid intelligence/ }).click();
    await page.getByRole("button", { name: /Run hybrid evaluation/ }).click();
    await expect(page.locator(".summary")).toBeVisible();
    const payloadText = await page.locator("details pre").textContent();
    const hybridPayload = JSON.parse(payloadText || "{}");
    expect(hybridPayload.screening, approvedCase.id + " hybrid-path screening").toEqual(approvedCase.hybrid.screening);
    expect(hybridPayload.hybrid, approvedCase.id + " decision-fusion output").toEqual(approvedCase.hybrid.hybrid);
    expect(hybridPayload.model, approvedCase.id + " model metadata").toEqual(approvedCase.hybrid.model_info);
  }
});
