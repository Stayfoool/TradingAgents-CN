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
  timestamp: new Date('2026-05-31T16:30:00+08:00').toISOString()
})

const validAccessToken = 'eyJhbGciOiJub25lIn0.eyJzdWIiOiJhZG1pbiIsImV4cCI6OTk5OTk5OTk5OX0.sig'
const validRefreshToken = 'eyJhbGciOiJub25lIn0.eyJzdWIiOiJhZG1pbiIsInR5cGUiOiJyZWZyZXNoIiwiZXhwIjo5OTk5OTk5OTk5fQ.sig'

test.beforeEach(async ({ page }) => {
  await page.context().clearCookies()
  await page.addInitScript(([accessToken, refreshToken]) => {
    window.localStorage.clear()
    window.sessionStorage.clear()
    window.localStorage.setItem('auth-token', accessToken)
    window.localStorage.setItem('refresh-token', refreshToken)
    window.localStorage.setItem('user-info', JSON.stringify({
      id: 'quality-user',
      username: 'admin',
      email: 'admin@example.com',
      is_active: true,
      is_verified: true,
      is_admin: true
    }))
  }, [validAccessToken, validRefreshToken])

  await page.route('**/api/**', async route => {
    const url = new URL(route.request().url())
    const path = url.pathname
    if (!path.startsWith('/api/')) {
      await route.continue()
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
          preferences: { default_market: 'A股', language: 'zh-CN' }
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
        preferences: { default_market: 'A股', language: 'zh-CN' }
      })))
      return
    }

    if (path === '/api/system/config/validate') {
      await route.fulfill(json(api({ success: true, missing_required: [] })))
      return
    }

    if (path === '/api/sync/multi-source/sources/current') {
      await route.fulfill(json(api({ name: 'AKShare', priority: 1, description: 'quality gate' })))
      return
    }

    if (path === '/api/screening/fields') {
      await route.fulfill(json(api({ fields: {}, categories: {} })))
      return
    }

    if (path === '/api/screening/industries') {
      await route.fulfill(json(api({ industries: [{ label: '半导体', value: '半导体', count: 3 }], total: 1 })))
      return
    }

    if (path === '/api/favorites') {
      await route.fulfill(json(api([])))
      return
    }

    if (path === '/api/screening/smart/run-natural-language') {
      await route.fulfill(json(api({
        total: 1,
        items: [
          {
            symbol: '688001',
            name: '样例半导体A',
            market: 'CN',
            industry: '半导体',
            score: 7.2,
            matched_conditions: ['conditions[0]', 'conditions[1]'],
            reasons: ['return_5d 命中条件，当前值 18.4', '命中文本事件：券商研报称订单与营收增长超预期'],
            evidence: [
              {
                evidence_type: 'text_event',
                source: 'research_report',
                field: 'stock_text_events',
                value: 'earnings_beat',
                condition: 'conditions[6]',
                title: '券商研报称订单与营收增长超预期',
                event_date: '2026-05-27',
                summary: '公司新签订单改善，营收增长和利润弹性高于市场预期。'
              }
            ],
            data: {
              return_5d: 18.4,
              volume_ratio: 1.8,
              turnover_rate: 6.3,
              close: 29.2,
              ma5: 27.1,
              ma10: 25.6
            }
          }
        ],
        dsl: {
          version: '1.0',
          market: 'CN',
          as_of: '2026-05-31',
          universe: { universe_type: 'industry', values: ['半导体'] }
        },
        plan: {
          required_execution_modes: ['historical_factor', 'dynamic_price_calc', 'text_event_search'],
          steps: [{ step_id: 'step_1', execution_mode: 'historical_factor' }]
        },
        audit: { passed: true, checked_candidates: 1, checked_evidence: 1 },
        data_gaps: [],
        deep_analysis_tasks: [],
        synthesis: {
          summary: '本次智能选股返回 1 只候选股，前 1 只具备可追溯证据。',
          top_symbols: ['688001'],
          key_reasons: ['命中文本事件：券商研报称订单与营收增长超预期'],
          risks: []
        }
      }, '智能选股执行成功')))
      return
    }

    await route.fulfill(json(api({})))
  })
})

test('run smart screening and display candidates evidence and DSL', async ({ page }) => {
  await page.goto('/screening')
  await expect(page.getByText('智能选股')).toBeVisible()
  await page.getByRole('button', { name: /智能筛选/ }).click()

  await expect(page.getByText('智能筛选完成，找到 1 只候选股')).toBeVisible()
  await expect(page.getByText('本次智能选股返回 1 只候选股，前 1 只具备可追溯证据。')).toBeVisible()
  await expect(page.getByText('688001').first()).toBeVisible()
  await expect(page.getByText('样例半导体A')).toBeVisible()
  await expect(page.getByText('券商研报称订单与营收增长超预期').first()).toBeVisible()

  await page.getByRole('tab', { name: 'DSL' }).click()
  await expect(page.getByText('"universe_type": "industry"')).toBeVisible()

  await page.getByRole('tab', { name: '执行计划' }).click()
  await expect(page.getByText('historical_factor')).toBeVisible()
})
