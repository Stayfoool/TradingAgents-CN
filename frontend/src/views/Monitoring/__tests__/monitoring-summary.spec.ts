import { mount, flushPromises } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const runMonitoring = vi.fn()

vi.mock('element-plus', () => ({
  ElIcon: { name: 'ElIcon', template: '<span><slot /></span>' },
  ElButton: {
    name: 'ElButton',
    template: '<button class="el-button" :class="{ \'el-button--primary\': type === \'primary\' }"><slot /></button>',
    props: ['type', 'loading']
  },
  ElRow: { name: 'ElRow', template: '<div><slot /></div>' },
  ElCol: { name: 'ElCol', template: '<div><slot /></div>' },
  ElCard: { name: 'ElCard', template: '<section><slot name="header" /><slot /></section>' },
  ElTable: { name: 'ElTable', template: '<div><slot /></div>', props: ['data'] },
  ElTableColumn: { name: 'ElTableColumn', template: '<div />', props: ['prop', 'label'] },
  ElTag: { name: 'ElTag', template: '<span><slot /></span>' },
  ElTabs: { name: 'ElTabs', template: '<div><slot /></div>' },
  ElTabPane: { name: 'ElTabPane', template: '<div><slot /></div>' },
  ElEmpty: { name: 'ElEmpty', template: '<div />' },
  ElDialog: { name: 'ElDialog', template: '<div><slot /><slot name="footer" /></div>' },
  ElForm: { name: 'ElForm', template: '<form><slot /></form>' },
  ElFormItem: { name: 'ElFormItem', template: '<div><slot /></div>' },
  ElSegmented: { name: 'ElSegmented', template: '<div />' },
  ElInput: { name: 'ElInput', template: '<input />' },
  ElInputNumber: { name: 'ElInputNumber', template: '<input />' },
  ElDrawer: { name: 'ElDrawer', template: '<div><slot /></div>' },
  ElAlert: { name: 'ElAlert', template: '<div>{{ title }}</div>', props: ['title'] },
  ElLoadingDirective: {},
  ElMessage: {
    success: vi.fn(),
    warning: vi.fn(),
    error: vi.fn()
  },
  ElMessageBox: {
    confirm: vi.fn()
  }
}))

vi.mock('@/api/watchlist', () => ({
  watchlistApi: {
    listWatchlist: vi.fn().mockResolvedValue({
      data: {
        items: Array.from({ length: 9 }, (_, index) => ({
          id: `w${index + 1}`,
          symbol: `QG${String(index + 1).padStart(3, '0')}`,
          stock_name: `Quality Gate ${index + 1}`,
          market: 'US',
          enabled: true
        })),
        total: 9
      }
    }),
    listPositions: vi.fn().mockResolvedValue({ data: { items: [], total: 0 } }),
    listReports: vi.fn().mockResolvedValue({ data: { items: [], total: 0 } }),
    listRuns: vi.fn().mockResolvedValue({ data: { items: [], total: 0 } }),
    runMonitoring
  }
}))

describe('Monitoring summary', () => {
  beforeEach(() => {
    runMonitoring.mockReset()
    runMonitoring.mockResolvedValue({
      data: {
        run_id: 'quality-run',
        target_count: 9,
        scanned_count: 9,
        triggered_count: 1,
        report_count: 1,
        no_signal_count: 8,
        error_count: 0,
        scanned_items: Array.from({ length: 9 }, (_, index) => ({
          symbol: `QG${String(index + 1).padStart(3, '0')}`,
          stock_name: `Quality Gate ${index + 1}`,
          market: 'US',
          status: index === 0 ? 'triggered' : 'no_signal',
          signal_type: index === 0 ? 'buy_watch' : 'no_action',
          score: index === 0 ? 2 : 0,
          triggered: index === 0,
          reasons: index === 0 ? ['权威媒体/公告证据出现积极事件关键词：收入增长。'] : [],
          data_gaps: []
        })),
        reports: [],
        errors: []
      }
    })
  })

  it('renders full scan coverage after manual monitoring run', async () => {
    const Monitoring = (await import('../index.vue')).default
    const wrapper = mount(Monitoring, {
      global: {
        stubs: {
          teleport: true,
          transition: false
        }
      }
    })

    await flushPromises()
    await wrapper.get('button.el-button--primary').trigger('click')
    await flushPromises()

    expect(runMonitoring).toHaveBeenCalledWith({
      max_deep_analysis: 10,
      lookback_days: 60,
      news_days: 7,
      force_refresh: false
    })
    expect(wrapper.text()).toContain('扫描标的')
    expect(wrapper.text()).toContain('触发信号')
    expect(wrapper.text()).toContain('无信号')
    expect(wrapper.text()).toContain('9')
    expect(wrapper.text()).toContain('1')
    expect(wrapper.text()).toContain('8')
  })
})
