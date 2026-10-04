import { expect, test, type Page } from '@playwright/test'
import { deleteE2eUsers } from './backend'

const SHOTS = process.env.E2E_SHOTS ?? 'test-results/shots'
const shot = (page: Page, name: string) => page.screenshot({ path: `${SHOTS}/${name}.png`, fullPage: true })

async function loginAs(page: Page, accountLabel: RegExp) {
  await page.goto('/login')
  await page.getByRole('button', { name: accountLabel }).click()
  await page.getByRole('button', { name: 'Iniciar sesión' }).click()
  // Wait for the login to finish: navigating away earlier would cancel the request.
  await expect(page.getByText(/Sesión iniciada/)).toBeVisible()
}

test.afterAll(() => deleteE2eUsers())

test.describe('protected routes', () => {
  test('an anonymous visitor to /profile is sent to the login', async ({ page }) => {
    await page.goto('/profile')
    await expect(page).toHaveURL(/\/login$/)
    await expect(page.getByRole('heading', { name: 'Inicia sesión' })).toBeVisible()
  })

  test('after logging in it returns to the page the user wanted', async ({ page }) => {
    await page.goto('/profile')
    await page.getByRole('button', { name: /Cliente gratuito/ }).click()
    await page.getByRole('button', { name: 'Iniciar sesión' }).click()
    await expect(page).toHaveURL(/\/profile$/)
    await expect(page.getByRole('heading', { name: 'Mi perfil' })).toBeVisible()
  })
})

test.describe('login', () => {
  test('renders the login screen', async ({ page }) => {
    await page.goto('/login')
    await expect(page.getByRole('heading', { name: 'Inicia sesión' })).toBeVisible()
    await shot(page, '01-login')
  })

  test('empty submit shows field messages', async ({ page }) => {
    await page.goto('/login')
    await page.getByRole('button', { name: 'Iniciar sesión' }).click()
    await expect(page.getByText('Ingresa tu correo electrónico.')).toBeVisible()
    await expect(page.getByText('Ingresa tu contraseña.')).toBeVisible()
    await shot(page, '02-login-validacion')
  })

  test('wrong password shows a clear message and keeps the user out', async ({ page }) => {
    await page.goto('/login')
    await page.getByLabel('Correo electrónico').fill('vip@rere.test')
    await page.getByLabel('Contraseña', { exact: true }).fill('ClaveIncorrecta1')
    await page.getByRole('button', { name: 'Iniciar sesión' }).click()
    await expect(page.getByRole('alert')).toContainText('Correo o contraseña incorrectos.')
    await expect(page).toHaveURL(/\/login$/)
    await shot(page, '03-login-error')
  })

  test('the password can be shown and hidden', async ({ page }) => {
    await page.goto('/login')
    const password = page.getByLabel('Contraseña', { exact: true })
    await expect(password).toHaveAttribute('type', 'password')
    await page.getByRole('button', { name: 'Mostrar contraseña' }).click()
    await expect(password).toHaveAttribute('type', 'text')
  })
})

test.describe('session', () => {
  test('VIP: login, profile, reload keeps the session, logout closes it', async ({ page }) => {
    await loginAs(page, /Cliente VIP/)
    await expect(page.getByText('Sesión iniciada · vip@rere.test (VIP)')).toBeVisible()
    await expect(page.getByText('Sesión:')).toContainText('vip@rere.test')

    await page.goto('/profile')
    await expect(page.getByRole('heading', { name: 'Mi perfil' })).toBeVisible()
    await expect(page.getByText('VIP', { exact: true })).toBeVisible()
    await expect(page.getByText(/quedan \d+ días/)).toBeVisible()
    await shot(page, '05-perfil-vip')

    // The access token only lives in memory: a reload must recover the session from the cookie.
    await page.reload()
    await expect(page.getByRole('heading', { name: 'Mi perfil' })).toBeVisible()
    await expect(page.getByText('vip@rere.test').first()).toBeVisible()

    await page.getByRole('button', { name: 'Cerrar sesión' }).click()
    await expect(page).toHaveURL(/\/login$/)
    await page.goto('/profile')
    await expect(page).toHaveURL(/\/login$/)
  })

  test('the refresh token is not readable from JavaScript', async ({ page, context }) => {
    await loginAs(page, /Cliente VIP/)
    await expect(page.getByText('Sesión:')).toBeVisible()

    expect(await page.evaluate(() => document.cookie)).not.toContain('refresh_token')
    const cookie = (await context.cookies()).find((c) => c.name === 'refresh_token')
    expect(cookie).toMatchObject({ httpOnly: true, path: '/api/auth/', sameSite: 'Lax' })
    expect(await page.evaluate(() => JSON.stringify({ ...localStorage, ...sessionStorage }))).not.toMatch(/eyJ/)
  })

  test('free user profile', async ({ page }) => {
    await loginAs(page, /Cliente gratuito/)
    await page.goto('/profile')
    await expect(page.getByText('Gratuita')).toBeVisible()
    await expect(page.getByText('Cliente', { exact: true })).toBeVisible()
    await shot(page, '06-perfil-gratuito')
  })

  test('expired VIP is shown as free, with the expiry notice', async ({ page }) => {
    await loginAs(page, /VIP vencido/)
    await page.goto('/profile')
    await expect(page.getByText('Gratuita')).toBeVisible()
    await expect(page.getByText(/Tu membresía VIP venció el/)).toBeVisible()
    await shot(page, '07-perfil-vip-vencido')
  })

  test('admin profile', async ({ page }) => {
    await loginAs(page, /Administrador/)
    await page.goto('/profile')
    await expect(page.getByText('Administrador', { exact: true })).toBeVisible()
    await shot(page, '08-perfil-admin')
  })
})

test.describe('register', () => {
  test('password requirements update as the user types', async ({ page }) => {
    await page.goto('/register')
    await expect(page.getByRole('heading', { name: 'Crea tu cuenta' })).toBeVisible()
    const rules = page.getByRole('list', { name: 'Requisitos de la contraseña' })
    const password = page.getByLabel('Contraseña', { exact: true })

    await password.fill('hola')
    await expect(rules.getByText('(cumplido)')).toHaveCount(1) // only "una letra"
    await password.fill('holaholaa1')
    await expect(rules.getByText('(cumplido)')).toHaveCount(3)
    await shot(page, '04-registro-requisitos')
  })

  test('a duplicated email is reported under the email field', async ({ page }) => {
    await page.goto('/register')
    await page.getByLabel('Correo electrónico').fill('cliente@rere.test')
    await page.getByLabel('Contraseña', { exact: true }).fill('Tr3sPatos88x')
    await page.getByRole('button', { name: 'Crear cuenta' }).click()
    await expect(page.getByText('Ya existe una cuenta con este correo electrónico.')).toBeVisible()
    await expect(page).toHaveURL(/\/register$/)
    await shot(page, '09-registro-correo-duplicado')
  })

  test('creating an account signs the user in as Free', async ({ page }) => {
    const email = `e2e-${Date.now()}@rere.test`
    await page.goto('/register')
    await page.getByLabel(/Nombre/).fill('Prueba')
    await page.getByLabel('Correo electrónico').fill(email)
    await page.getByLabel('Contraseña', { exact: true }).fill('Tr3sPatos88x')
    await page.getByRole('button', { name: 'Crear cuenta' }).click()

    await expect(page.getByText('Cuenta creada. ¡Bienvenido a Re & Re!')).toBeVisible()
    await expect(page.getByText('Sesión:')).toContainText(email)

    await page.goto('/profile')
    await expect(page.getByText('Prueba', { exact: true })).toBeVisible()
    await expect(page.getByText('Gratuita')).toBeVisible()
  })
})
