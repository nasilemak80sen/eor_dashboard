import { expect, test } from "@playwright/test";

test("Vue POC can preview the engineering-screening workflow without an API", async ({ page }) => {
  const backendRequests: string[] = [];
  page.on("request", (request) => {
    if (/127\.0\.0\.1:8000|\/api\/v1\//i.test(request.url())) backendRequests.push(request.url());
  });

  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Engineering screening" })).toBeVisible();
  await expect(page.locator(".topright")).toContainText("LOCAL POC");
  await expect(page.getByText("Illustrative starter profile")).toBeVisible();

  await page.getByRole("button", { name: /Run engineering screening/ }).click();
  await expect(page.getByRole("heading", { name: "Simulated engineering gate" })).toBeVisible();
  await expect(page.getByRole("status")).toContainText("Demonstration output only");
  await expect(page.getByText("MOCK PASS").first()).toBeVisible();
  await expect(page.getByText("Not saved", { exact: true })).toBeVisible();
  expect(backendRequests).toEqual([]);
});

test("Hybrid Intelligence and history are clearly labelled as synthetic", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: /Hybrid intelligence/ }).click();
  await expect(page.getByRole("heading", { name: "Hybrid intelligence" })).toBeVisible();
  await page.getByRole("button", { name: /Run hybrid evaluation/ }).click();
  await expect(page.getByText("ILLUSTRATIVE HYBRID RECOMMENDATION")).toBeVisible();
  await expect(page.getByRole("heading", { name: "Illustrative model details" })).toBeVisible();
  await expect(page.getByText("Demonstration output only")).toBeVisible();

  await page.getByRole("button", { name: /Run history/ }).click();
  await expect(page.getByRole("heading", { name: "Example run history" })).toBeVisible();
  await expect(page.getByText("synthetic fixtures", { exact: false })).toBeVisible();
  await expect(page.getByRole("cell", { name: "POC-1001" })).toBeVisible();
});

test("Advanced reservoir context remains available on narrow screens", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/");
  await page.getByText("Engineering context, recovery and injection conditions").click();
  await expect(page.getByLabel("Salinity (TDS)")).toBeVisible();
  await expect(page.getByRole("button", { name: /Run engineering screening/ })).toBeVisible();
});
