import { test, expect } from '@playwright/test';

test.describe('Satellite Viewer', () => {
  test.beforeEach(async ({ page }) => {
    // Collect console errors
    const errors: string[] = [];
    page.on('pageerror', (error) => {
      errors.push(error.message);
    });
    page.on('console', (msg) => {
      if (msg.type() === 'error') {
        errors.push(msg.text());
      }
    });

    // Store errors for later assertion
    await page.goto('/');
    // @ts-expect-error - custom property for test assertions
    page.consoleErrors = errors;
  });

  test('loads without JavaScript errors', async ({ page }) => {
    // Wait for the app to load
    await expect(page.locator('.app-header h1')).toHaveText('CubeSat Simulator');

    // Wait a bit for any async errors
    await page.waitForTimeout(1000);

    // Check no errors occurred
    // @ts-expect-error - custom property
    const errors = page.consoleErrors as string[];
    expect(errors.filter(e => !e.includes('Warning'))).toHaveLength(0);
  });

  test('renders the 3D visualization canvas', async ({ page }) => {
    // Wait for the visualization section
    await expect(page.locator('.visualization')).toBeVisible();

    // Check that a canvas element exists (Three.js creates a canvas)
    const canvas = page.locator('.visualization canvas');
    await expect(canvas).toBeVisible();

    // Canvas should have non-zero dimensions
    const box = await canvas.boundingBox();
    expect(box).toBeTruthy();
    expect(box!.width).toBeGreaterThan(100);
    expect(box!.height).toBeGreaterThan(100);
  });

  test('displays attitude overlay', async ({ page }) => {
    // Wait for the attitude overlay to appear
    const overlay = page.locator('.attitude-overlay');
    await expect(overlay).toBeVisible();

    // Initially shows "No telemetry" or attitude data
    const text = await overlay.textContent();
    expect(text).toBeTruthy();
  });

  test('renders simulation controls', async ({ page }) => {
    // Check that simulation controls are present
    await expect(page.locator('.simulation-controls')).toBeVisible();

    // Check for control buttons
    await expect(page.locator('button:has-text("Start")')).toBeVisible();
    await expect(page.locator('button:has-text("Reset")')).toBeVisible();
  });

  test('shows charts section', async ({ page }) => {
    // Check that charts section exists
    await expect(page.locator('.charts')).toBeVisible();
  });
});
