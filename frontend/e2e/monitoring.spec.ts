import { expect, test } from '@playwright/test'

const json = (data: unknown) => ({
  status: 200,
  contentType: 'application/json',
  body: JSON.stringify(data)
})

const api = (data: unknown, message = 'ok') => ({
  success: true,
  data,
  message,
  timestamp: new Date('2026-05-29T09:30:00+08:00').toISOString()
})

const validAccessToken = 'eyJhbGciOiJub25lIn0.eyJzdWIiOiJhZG1pbiIsImV4cCI6OTk5OTk5OTk5OX0.sig'
const validRefreshToken = 'eyJhbGciOiJub25lIn0.eyJzdWIiOiJhZG1pbiIsInR5cGUiOiJyZWZyZXNoIiwiZXhwIjo5OTk5OTk5OTk5fQ.sig'

test.beforeEach(async ({ page }) => {
  const watchlist = Array.from({ length: 9 }, (_, index) => ({
    id: `w${index + 1}`,
    symbol: `QG${String(index + 1).padStart(3, '0')}`,
    stock_name: `Quality Gate ${index + 1}`,
    market: 'US',
    enabled: true,
    tags: [],
    notes: ''
  }))

  await page.route('**/api/**', async route => {
    const url = new URL(route.request().url())
    const path = url.pathname
    if (!path.startsWith('/api/')) {
      await route.continue()
      return
    }

    if (path === '/api/health') {
      await route.fulfill(json(api({ status: 'ok', service: 'TradingAgents-CN API' }, '服务运行正常')))
      return
    }

    if (path === '/api/auth/login') {
      await route.fulfill(json(api({
        access_token: validAccessToken,
        refresh_token: validRefreshToken,
        token_type: 'bearer',
        expires_in: 3600,
        user: {
          id: 'quality-user',
          username: 'admin',
          email: 'admin@example.com',
          is_active: true,
          is_verified: true,
          is_admin: true,
          created_at: '2026-05-29T09:00:00+08:00',
          updated_at: '2026-05-29T09:00:00+08:00',
          preferences: {
            default_market: '美股',
            default_depth: '3',
            ui_theme: 'light',
            language: 'zh-CN',
            notifications_enabled: true,
            email_notifications: false
          },
          daily_quota: 1000,
          concurrent_limit: 3,
          total_analyses: 0,
          successful_analyses: 0,
          failed_analyses: 0
        }
      }, '登录成功')))
      return
    }

    if (path === '/api/auth/me') {
      await route.fulfill(json(api({
        id: 'quality-user',
        username: 'admin',
        email: 'admin@example.com',
        is_active: true,
        is_verified: true,
        is_admin: true,
        created_at: '2026-05-29T09:00:00+08:00',
        updated_at: '2026-05-29T09:00:00+08:00',
        preferences: {
          default_market: '美股',
          default_depth: '3',
          ui_theme: 'light',
          language: 'zh-CN',
          notifications_enabled: true,
          email_notifications: false
        },
        daily_quota: 1000,
        concurrent_limit: 3,
        total_analyses: 0,
        successful_analyses: 0,
        failed_analyses: 0
      })))
      return
    }

    if (path === '/api/system/config/validate') {
      await route.fulfill(json(api({ success: true, missing_required: [] })))
      return
    }

    if (path === '/api/watchlists') {
      await route.fulfill(json(api({ items: watchlist, total: watchlist.length })))
      return
    }

    if (path === '/api/portfolio/positions') {
      await route.fulfill(json(api({ items: [], total: 0 })))
      return
    }

    if (path === '/api/monitoring/reports') {
      await route.fulfill(json(api({ items: [], total: 0 })))
      return
    }

    if (path === '/api/monitoring/runs') {
      await route.fulfill(json(api({ items: [], total: 0 })))
      return
    }

    if (path === '/api/monitoring/watchlist/run') {
      const scannedItems = watchlist.map((item, index) => ({
        ...item,
        status: index === 0 ? 'triggered' : 'no_signal',
        signal_type: index === 0 ? 'buy_watch' : 'no_action',
        score: index === 0 ? 2 : 0,
        triggered: index === 0,
        reasons: index === 0 ? ['权威媒体/公告证据出现积极事件关键词：收入增长。'] : [],
        data_gaps: []
      }))
      await route.fulfill(json(api({
        run_id: 'quality-run',
        target_count: 9,
        scanned_count: 9,
        triggered_count: 1,
        report_count: 1,
        no_signal_count: 8,
        error_count: 0,
        scanned_items: scannedItems,
        reports: [],
        errors: []
      }, 'watchlist monitoring completed')))
      return
    }

    await route.fulfill(json(api({})))
  })
})

test('login, run monitoring, and display 9 scanned / 1 triggered / 8 no-signal', async ({ page }) => {
  await page.goto('/login')
  await page.getByPlaceholder('请输入用户名').fill('admin')
  await page.getByPlaceholder('请输入密码').fill('admin123')
  await page.getByRole('button', { name: '登录' }).click()
  await expect(page.getByText('登录成功')).toBeVisible()

  await page.goto('/monitoring')
  await expect(page.getByText('自动监控').first()).toBeVisible()
  await expect(page.getByText('关注股票').first()).toBeVisible()
  await expect(page.getByText('9').first()).toBeVisible()

  await page.getByRole('button', { name: /立即扫描/ }).click()

  await expect(page.getByText('扫描完成：扫描 9 家，触发 1 家，无信号 8 家，错误 0 个')).toBeVisible()
  await expect(page.getByText('扫描标的')).toBeVisible()
  await expect(page.getByText('触发信号')).toBeVisible()
  await expect(page.getByText('无信号').first()).toBeVisible()
  await expect(page.getByText('QG001').first()).toBeVisible()
  await expect(page.getByText('QG009').first()).toBeVisible()
})
