import { test, expect } from '@playwright/test'

test('app boots without errors', async ({ page }) => {
  const errors: string[] = []
  page.on('pageerror', (e) => errors.push(e.message))
  await page.goto('/')
  await expect(page).toHaveTitle(/./)
  expect(errors).toEqual([])
})
