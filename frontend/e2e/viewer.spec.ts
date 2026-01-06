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

test.describe('View Mode Toggle', () => {
  test.beforeEach(async ({ page }) => {
    const errors: string[] = [];
    page.on('pageerror', (error) => errors.push(error.message));
    page.on('console', (msg) => {
      if (msg.type() === 'error') errors.push(msg.text());
    });
    await page.goto('/');
    // @ts-expect-error - custom property
    page.consoleErrors = errors;
  });

  test('displays view mode toggle buttons', async ({ page }) => {
    // Check that view mode toggle exists
    const toggle = page.locator('.view-mode-toggle');
    await expect(toggle).toBeVisible();

    // Should have Attitude and Orbit buttons
    await expect(page.locator('button:has-text("Attitude")')).toBeVisible();
    await expect(page.locator('button:has-text("Orbit")')).toBeVisible();
  });

  test('defaults to Attitude view', async ({ page }) => {
    // Attitude button should be active by default
    const attitudeBtn = page.locator('button:has-text("Attitude")');
    await expect(attitudeBtn).toHaveClass(/active/);

    // SatelliteView should be visible
    await expect(page.locator('.satellite-view')).toBeVisible();
  });

  test('switches to Orbit view without errors', async ({ page }) => {
    // Click Orbit button
    await page.locator('button:has-text("Orbit")').click();

    // Wait for view switch
    await page.waitForTimeout(500);

    // Orbit button should now be active
    const orbitBtn = page.locator('button:has-text("Orbit")');
    await expect(orbitBtn).toHaveClass(/active/);

    // GlobeView should be visible with canvas
    await expect(page.locator('.globe-view')).toBeVisible();
    await expect(page.locator('.globe-view canvas')).toBeVisible();

    // Check no JS errors
    // @ts-expect-error - custom property
    const errors = page.consoleErrors as string[];
    expect(errors.filter(e => !e.includes('Warning'))).toHaveLength(0);
  });

  test('can switch back to Attitude view', async ({ page }) => {
    // Switch to Orbit
    await page.locator('button:has-text("Orbit")').click();
    await page.waitForTimeout(300);

    // Switch back to Attitude
    await page.locator('button:has-text("Attitude")').click();
    await page.waitForTimeout(300);

    // Attitude view should be visible again
    await expect(page.locator('.satellite-view')).toBeVisible();
    await expect(page.locator('.attitude-overlay')).toBeVisible();
  });
});

test.describe('Globe View', () => {
  test.beforeEach(async ({ page }) => {
    const errors: string[] = [];
    page.on('pageerror', (error) => errors.push(error.message));
    page.on('console', (msg) => {
      if (msg.type() === 'error') errors.push(msg.text());
    });
    await page.goto('/');
    // @ts-expect-error - custom property
    page.consoleErrors = errors;

    // Navigate to Orbit view
    await page.locator('button:has-text("Orbit")').click();
    await page.waitForTimeout(500);
  });

  test('renders Earth globe with proper dimensions', async ({ page }) => {
    const canvas = page.locator('.globe-view canvas');
    await expect(canvas).toBeVisible();

    const box = await canvas.boundingBox();
    expect(box).toBeTruthy();
    expect(box!.width).toBeGreaterThan(100);
    expect(box!.height).toBeGreaterThan(100);
  });

  test('displays orbit info overlay', async ({ page }) => {
    const overlay = page.locator('.orbit-overlay');
    await expect(overlay).toBeVisible();

    // Should show position info or "No telemetry" if orbit data not available
    const text = await overlay.textContent();
    expect(text).toBeTruthy();
    // Accept either orbit data or no telemetry message
    const hasOrbitData = text?.includes('Alt') || text?.includes('No telemetry');
    expect(hasOrbitData).toBe(true);
  });

  test('renders without WebGL/WebGPU errors', async ({ page }) => {
    // Wait for rendering
    await page.waitForTimeout(1000);

    // @ts-expect-error - custom property
    const errors = page.consoleErrors as string[];

    // Filter out warnings, check for WebGL/WebGPU errors
    const criticalErrors = errors.filter(e =>
      !e.includes('Warning') &&
      (e.includes('WebGL') || e.includes('WebGPU') || e.includes('GPUShaderStage'))
    );
    expect(criticalErrors).toHaveLength(0);
  });
});
