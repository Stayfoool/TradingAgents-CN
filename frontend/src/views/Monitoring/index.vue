<template>
  <div class="monitoring-page">
    <div class="page-header">
      <div>
        <h1 class="page-title">
          <el-icon><Monitor /></el-icon>
          自动监控
        </h1>
        <p class="page-description">维护关注列表和持仓，手动触发 Watchlist 扫描，查看机会和风险报告。</p>
      </div>
      <div class="header-actions">
        <el-button @click="refreshAll" :loading="loading">
          <el-icon><Refresh /></el-icon>
          刷新
        </el-button>
        <el-button type="primary" @click="runMonitoring" :loading="running">
          <el-icon><VideoPlay /></el-icon>
          立即扫描
        </el-button>
      </div>
    </div>

    <el-row :gutter="16" class="summary-row">
      <el-col :xs="24" :sm="8">
        <div class="metric-panel">
          <span class="metric-label">关注股票</span>
          <strong>{{ watchlist.length }}</strong>
        </div>
      </el-col>
      <el-col :xs="24" :sm="8">
        <div class="metric-panel">
          <span class="metric-label">持仓标的</span>
          <strong>{{ positions.length }}</strong>
        </div>
      </el-col>
      <el-col :xs="24" :sm="8">
        <div class="metric-panel">
          <span class="metric-label">最近扫描</span>
          <strong>{{ latestScannedCount }}</strong>
        </div>
      </el-col>
    </el-row>

    <el-card v-if="lastRun" shadow="never" class="section-card">
      <template #header>
        <div class="section-header">
          <span>最近一次扫描</span>
          <span class="muted">{{ formatTime(lastRun.completed_at || lastRun.created_at) }}</span>
        </div>
      </template>

      <el-row :gutter="12" class="run-summary">
        <el-col :xs="12" :sm="6">
          <div class="run-stat">
            <span>扫描标的</span>
            <strong>{{ latestScannedCount }}</strong>
          </div>
        </el-col>
        <el-col :xs="12" :sm="6">
          <div class="run-stat">
            <span>触发信号</span>
            <strong>{{ lastRunTriggeredCount }}</strong>
          </div>
        </el-col>
        <el-col :xs="12" :sm="6">
          <div class="run-stat">
            <span>无信号</span>
            <strong>{{ lastRunNoSignalCount }}</strong>
          </div>
        </el-col>
        <el-col :xs="12" :sm="6">
          <div class="run-stat">
            <span>错误</span>
            <strong>{{ lastRun.error_count ?? 0 }}</strong>
          </div>
        </el-col>
      </el-row>

      <el-table v-if="lastRun.scanned_items?.length" :data="lastRun.scanned_items" size="small" class="scan-table">
        <el-table-column prop="symbol" label="股票" min-width="130">
          <template #default="{ row }">
            <div class="symbol-cell">
              <strong>{{ row.symbol }}</strong>
              <span>{{ row.stock_name || marketLabel(row.market) }}</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="110">
          <template #default="{ row }">
            <el-tag :type="scanStatusTagType(row.status)" effect="plain">
              {{ scanStatusLabel(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="signal_type" label="信号" width="120">
          <template #default="{ row }">{{ signalLabel(row.signal_type) }}</template>
        </el-table-column>
        <el-table-column prop="change_percent" label="涨跌幅" width="100">
          <template #default="{ row }">{{ formatPercent(row.change_percent) }}</template>
        </el-table-column>
        <el-table-column label="说明" min-width="240" show-overflow-tooltip>
          <template #default="{ row }">
            {{ scanItemDescription(row) }}
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-tabs v-model="activeTab" class="monitoring-tabs">
      <el-tab-pane label="监控报告" name="reports">
        <el-card shadow="never" class="section-card">
          <template #header>
            <div class="section-header">
              <span>最新信号</span>
              <el-button text type="primary" @click="loadReports">重新加载</el-button>
            </div>
          </template>

          <el-table :data="reports" v-loading="reportsLoading" style="width: 100%">
            <el-table-column prop="symbol" label="股票" min-width="130">
              <template #default="{ row }">
                <div class="symbol-cell">
                  <strong>{{ row.symbol }}</strong>
                  <span>{{ row.stock_name || row.market }}</span>
                </div>
              </template>
            </el-table-column>
            <el-table-column prop="signal_type" label="信号" width="130">
              <template #default="{ row }">
                <el-tag :type="signalTagType(row.signal_type)" effect="plain">
                  {{ signalLabel(row.signal_type) }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="score" label="分数" width="90">
              <template #default="{ row }">{{ formatNumber(row.score) }}</template>
            </el-table-column>
            <el-table-column prop="recommendation" label="建议" min-width="220" show-overflow-tooltip />
            <el-table-column prop="created_at" label="时间" width="170">
              <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
            </el-table-column>
            <el-table-column label="详情" width="90" fixed="right">
              <template #default="{ row }">
                <el-button text type="primary" @click="openReport(row)">
                  <el-icon><View /></el-icon>
                </el-button>
              </template>
            </el-table-column>
          </el-table>

          <el-empty v-if="!reportsLoading && reports.length === 0" description="暂无监控报告" />
        </el-card>
      </el-tab-pane>

      <el-tab-pane label="关注列表" name="watchlist">
        <el-card shadow="never" class="section-card">
          <template #header>
            <div class="section-header">
              <span>Watchlist</span>
              <el-button type="primary" @click="openWatchDialog()">
                <el-icon><Plus /></el-icon>
                添加股票
              </el-button>
            </div>
          </template>

          <el-table :data="watchlist" v-loading="watchlistLoading" style="width: 100%">
            <el-table-column prop="symbol" label="代码" width="120" />
            <el-table-column prop="stock_name" label="名称" min-width="140" />
            <el-table-column prop="market" label="市场" width="90">
              <template #default="{ row }">{{ marketLabel(row.market) }}</template>
            </el-table-column>
            <el-table-column prop="tags" label="标签" min-width="150">
              <template #default="{ row }">
                <el-tag v-for="tag in row.tags || []" :key="tag" size="small" effect="plain">{{ tag }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="notes" label="备注" min-width="180" show-overflow-tooltip />
            <el-table-column label="操作" width="130" fixed="right">
              <template #default="{ row }">
                <el-button text type="primary" @click="openWatchDialog(row)">编辑</el-button>
                <el-button text type="danger" @click="deleteWatch(row)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
          <el-empty v-if="!watchlistLoading && watchlist.length === 0" description="暂无关注股票" />
        </el-card>
      </el-tab-pane>

      <el-tab-pane label="持仓" name="positions">
        <el-card shadow="never" class="section-card">
          <template #header>
            <div class="section-header">
              <span>Portfolio</span>
              <el-button type="primary" @click="openPositionDialog()">
                <el-icon><Plus /></el-icon>
                添加持仓
              </el-button>
            </div>
          </template>

          <el-table :data="positions" v-loading="positionsLoading" style="width: 100%">
            <el-table-column prop="symbol" label="代码" width="120" />
            <el-table-column prop="stock_name" label="名称" min-width="140" />
            <el-table-column prop="market" label="市场" width="90">
              <template #default="{ row }">{{ marketLabel(row.market) }}</template>
            </el-table-column>
            <el-table-column prop="quantity" label="数量" width="110" />
            <el-table-column prop="cost_basis" label="成本" width="110" />
            <el-table-column prop="target_price" label="目标价" width="110" />
            <el-table-column prop="stop_loss" label="止损价" width="110" />
            <el-table-column label="操作" width="130" fixed="right">
              <template #default="{ row }">
                <el-button text type="primary" @click="openPositionDialog(row)">编辑</el-button>
                <el-button text type="danger" @click="deletePosition(row)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
          <el-empty v-if="!positionsLoading && positions.length === 0" description="暂无持仓" />
        </el-card>
      </el-tab-pane>
    </el-tabs>

    <el-dialog v-model="watchDialogVisible" :title="editingWatch?.id ? '编辑关注股票' : '添加关注股票'" width="520px">
      <el-form :model="watchForm" label-width="88px">
        <el-form-item label="市场">
          <el-segmented v-model="watchForm.market" :options="marketOptions" />
        </el-form-item>
        <el-form-item label="代码">
          <el-input v-model.trim="watchForm.symbol" placeholder="例如 SNOW / 000001 / 09988" />
        </el-form-item>
        <el-form-item label="名称">
          <el-input v-model.trim="watchForm.stock_name" placeholder="可选" />
        </el-form-item>
        <el-form-item label="标签">
          <el-input v-model.trim="watchTagsText" placeholder="用逗号分隔" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="watchForm.notes" type="textarea" :rows="3" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="watchDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="saveWatch" :loading="saving">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="positionDialogVisible" :title="editingPosition?.id ? '编辑持仓' : '添加持仓'" width="560px">
      <el-form :model="positionForm" label-width="88px">
        <el-form-item label="市场">
          <el-segmented v-model="positionForm.market" :options="marketOptions" />
        </el-form-item>
        <el-form-item label="代码">
          <el-input v-model.trim="positionForm.symbol" placeholder="例如 SNOW / 000001 / 09988" />
        </el-form-item>
        <el-form-item label="名称">
          <el-input v-model.trim="positionForm.stock_name" placeholder="可选" />
        </el-form-item>
        <el-row :gutter="12">
          <el-col :span="12">
            <el-form-item label="数量">
              <el-input-number v-model="positionForm.quantity" :min="0" :precision="2" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="成本">
              <el-input-number v-model="positionForm.cost_basis" :min="0" :precision="3" style="width: 100%" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="12">
          <el-col :span="12">
            <el-form-item label="目标价">
              <el-input-number v-model="positionForm.target_price" :min="0" :precision="3" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="止损价">
              <el-input-number v-model="positionForm.stop_loss" :min="0" :precision="3" style="width: 100%" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="标签">
          <el-input v-model.trim="positionTagsText" placeholder="用逗号分隔" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="positionForm.notes" type="textarea" :rows="3" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="positionDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="savePosition" :loading="saving">保存</el-button>
      </template>
    </el-dialog>

    <el-drawer v-model="reportDrawerVisible" size="620px" title="监控报告">
      <div v-if="selectedReport" class="report-detail">
        <div class="report-head">
          <div>
            <h2>{{ selectedReport.symbol }} {{ selectedReport.stock_name || '' }}</h2>
            <p>{{ marketLabel(selectedReport.market) }} · {{ formatTime(selectedReport.created_at) }}</p>
          </div>
          <el-tag :type="signalTagType(selectedReport.signal_type)">
            {{ signalLabel(selectedReport.signal_type) }}
          </el-tag>
        </div>

        <el-alert
          v-if="selectedReport.recommendation"
          :title="selectedReport.recommendation"
          type="info"
          :closable="false"
          show-icon
        />

        <h3>触发原因</h3>
        <ul>
          <li v-for="reason in selectedReport.reasons || []" :key="reason">{{ reason }}</li>
        </ul>

        <h3>权威证据</h3>
        <div v-if="selectedReport.evidence?.length" class="evidence-list">
          <div v-for="item in selectedReport.evidence" :key="item.url || item.title || item.reason" class="evidence-item">
            <div class="evidence-title">
              <span>{{ item.source || item.type }}</span>
              <el-tag v-if="item.confidence !== undefined" size="small" effect="plain">
                {{ formatNumber(item.confidence) }}
              </el-tag>
            </div>
            <a v-if="item.url" :href="item.url" target="_blank" rel="noreferrer">{{ item.title || item.url }}</a>
            <p v-else>{{ item.title || item.reason || '未找到权威媒体证据' }}</p>
            <small v-if="item.published_at">{{ item.published_at }}</small>
          </div>
        </div>
        <el-empty v-else description="暂无证据" />

        <template v-if="selectedReport.data_gaps?.length">
          <h3>数据缺口</h3>
          <el-alert
            v-for="gap in selectedReport.data_gaps"
            :key="gap"
            :title="gap"
            type="warning"
            :closable="false"
            class="gap-alert"
          />
        </template>
      </div>
    </el-drawer>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Monitor,
  Plus,
  Refresh,
  VideoPlay,
  View
} from '@element-plus/icons-vue'
import {
  type MonitoringReport,
  type MonitoringRunSummary,
  type PositionItem,
  type PositionPayload,
  type WatchMarket,
  type WatchlistItem,
  type WatchlistPayload,
  watchlistApi
} from '@/api/watchlist'

const activeTab = ref('reports')
const loading = ref(false)
const running = ref(false)
const saving = ref(false)
const watchlistLoading = ref(false)
const positionsLoading = ref(false)
const reportsLoading = ref(false)

const watchlist = ref<WatchlistItem[]>([])
const positions = ref<PositionItem[]>([])
const reports = ref<MonitoringReport[]>([])
const lastRun = ref<MonitoringRunSummary | null>(null)

const watchDialogVisible = ref(false)
const positionDialogVisible = ref(false)
const reportDrawerVisible = ref(false)
const editingWatch = ref<WatchlistItem | null>(null)
const editingPosition = ref<PositionItem | null>(null)
const selectedReport = ref<MonitoringReport | null>(null)
const watchTagsText = ref('')
const positionTagsText = ref('')

const marketOptions = [
  { label: '美股', value: 'US' },
  { label: 'A股', value: 'CN' },
  { label: '港股', value: 'HK' }
]

const watchForm = reactive<WatchlistPayload>({
  symbol: '',
  stock_name: '',
  market: 'US',
  tags: [],
  notes: '',
  enabled: true
})

const positionForm = reactive<PositionPayload>({
  symbol: '',
  stock_name: '',
  market: 'US',
  quantity: undefined,
  cost_basis: undefined,
  target_price: undefined,
  stop_loss: undefined,
  tags: [],
  notes: '',
  enabled: true
})

const hasTargets = computed(() => watchlist.value.length > 0 || positions.value.length > 0)
const latestScannedCount = computed(() => {
  if (!lastRun.value) return '-'
  return lastRun.value.scanned_count ?? lastRun.value.target_count ?? 0
})
const lastRunNoSignalCount = computed(() => {
  if (!lastRun.value) return 0
  if (typeof lastRun.value.no_signal_count === 'number') return lastRun.value.no_signal_count
  const scanned = lastRun.value.scanned_items || []
  if (scanned.length) return scanned.filter(item => item.status === 'no_signal').length
  return Math.max((lastRun.value.target_count || 0) - (lastRun.value.report_count || 0) - (lastRun.value.error_count || 0), 0)
})
const lastRunTriggeredCount = computed(() => {
  if (!lastRun.value) return 0
  if (typeof lastRun.value.triggered_count === 'number') return lastRun.value.triggered_count
  const scanned = lastRun.value.scanned_items || []
  if (scanned.length) return scanned.filter(item => item.status === 'triggered').length
  return lastRun.value.report_count || 0
})

onMounted(() => {
  refreshAll()
})

async function refreshAll() {
  loading.value = true
  try {
    await Promise.all([loadWatchlist(), loadPositions(), loadReports(), loadRuns()])
  } finally {
    loading.value = false
  }
}

async function loadWatchlist() {
  watchlistLoading.value = true
  try {
    const res = await watchlistApi.listWatchlist()
    watchlist.value = res.data.items || []
  } finally {
    watchlistLoading.value = false
  }
}

async function loadPositions() {
  positionsLoading.value = true
  try {
    const res = await watchlistApi.listPositions()
    positions.value = res.data.items || []
  } finally {
    positionsLoading.value = false
  }
}

async function loadReports() {
  reportsLoading.value = true
  try {
    const res = await watchlistApi.listReports(50, 0)
    reports.value = res.data.items || []
  } finally {
    reportsLoading.value = false
  }
}

async function loadRuns() {
  const res = await watchlistApi.listRuns(1, 0)
  lastRun.value = res.data.items?.[0] || null
}

function resetWatchForm() {
  Object.assign(watchForm, {
    symbol: '',
    stock_name: '',
    market: 'US',
    tags: [],
    notes: '',
    enabled: true
  })
  watchTagsText.value = ''
}

function resetPositionForm() {
  Object.assign(positionForm, {
    symbol: '',
    stock_name: '',
    market: 'US',
    quantity: undefined,
    cost_basis: undefined,
    target_price: undefined,
    stop_loss: undefined,
    tags: [],
    notes: '',
    enabled: true
  })
  positionTagsText.value = ''
}

function openWatchDialog(item?: WatchlistItem) {
  editingWatch.value = item || null
  if (item) {
    Object.assign(watchForm, {
      symbol: item.symbol,
      stock_name: item.stock_name || '',
      market: item.market,
      tags: item.tags || [],
      notes: item.notes || '',
      enabled: item.enabled
    })
    watchTagsText.value = (item.tags || []).join(', ')
  } else {
    resetWatchForm()
  }
  watchDialogVisible.value = true
}

function openPositionDialog(item?: PositionItem) {
  editingPosition.value = item || null
  if (item) {
    Object.assign(positionForm, {
      symbol: item.symbol,
      stock_name: item.stock_name || '',
      market: item.market,
      quantity: item.quantity,
      cost_basis: item.cost_basis,
      target_price: item.target_price,
      stop_loss: item.stop_loss,
      tags: item.tags || [],
      notes: item.notes || '',
      enabled: item.enabled
    })
    positionTagsText.value = (item.tags || []).join(', ')
  } else {
    resetPositionForm()
  }
  positionDialogVisible.value = true
}

async function saveWatch() {
  if (!watchForm.symbol.trim()) {
    ElMessage.warning('请输入股票代码')
    return
  }
  saving.value = true
  try {
    const payload = {
      ...watchForm,
      symbol: watchForm.symbol.trim().toUpperCase(),
      tags: splitTags(watchTagsText.value)
    }
    if (editingWatch.value?.id) {
      await watchlistApi.updateWatchlistItem(editingWatch.value.id, payload)
    } else {
      await watchlistApi.addWatchlistItem(payload)
    }
    ElMessage.success('已保存关注股票')
    watchDialogVisible.value = false
    await loadWatchlist()
  } finally {
    saving.value = false
  }
}

async function savePosition() {
  if (!positionForm.symbol.trim()) {
    ElMessage.warning('请输入股票代码')
    return
  }
  saving.value = true
  try {
    const payload = {
      ...positionForm,
      symbol: positionForm.symbol.trim().toUpperCase(),
      tags: splitTags(positionTagsText.value)
    }
    if (editingPosition.value?.id) {
      await watchlistApi.updatePosition(editingPosition.value.id, payload)
    } else {
      await watchlistApi.addPosition(payload)
    }
    ElMessage.success('已保存持仓')
    positionDialogVisible.value = false
    await loadPositions()
  } finally {
    saving.value = false
  }
}

async function deleteWatch(row: WatchlistItem) {
  await ElMessageBox.confirm(`删除 ${row.symbol}？`, '确认删除', { type: 'warning' })
  await watchlistApi.deleteWatchlistItem(row.id)
  ElMessage.success('已删除')
  await loadWatchlist()
}

async function deletePosition(row: PositionItem) {
  await ElMessageBox.confirm(`删除 ${row.symbol} 持仓？`, '确认删除', { type: 'warning' })
  await watchlistApi.deletePosition(row.id)
  ElMessage.success('已删除')
  await loadPositions()
}

async function runMonitoring() {
  if (!hasTargets.value) {
    ElMessage.warning('请先添加关注股票或持仓')
    return
  }
  running.value = true
  try {
    const res = await watchlistApi.runMonitoring({
      max_deep_analysis: 10,
      lookback_days: 60,
      news_days: 7,
      force_refresh: false
    })
    lastRun.value = {
      user_id: '',
      status: 'completed',
      target_count: res.data.target_count,
      scanned_count: res.data.scanned_count,
      triggered_count: res.data.triggered_count,
      report_count: res.data.report_count,
      no_signal_count: res.data.no_signal_count,
      error_count: res.data.error_count,
      errors: res.data.errors,
      scanned_items: res.data.scanned_items,
      completed_at: new Date().toISOString()
    }
    ElMessage.success(`扫描完成：扫描 ${res.data.scanned_count} 家，触发 ${res.data.triggered_count} 家，无信号 ${res.data.no_signal_count} 家，错误 ${res.data.error_count} 个`)
    activeTab.value = 'reports'
    await loadReports()
  } finally {
    running.value = false
  }
}

function openReport(row: MonitoringReport) {
  selectedReport.value = row
  reportDrawerVisible.value = true
}

function splitTags(text: string) {
  return text
    .split(/[,，]/)
    .map(tag => tag.trim())
    .filter(Boolean)
}

function marketLabel(market?: WatchMarket) {
  const map: Record<string, string> = { CN: 'A股', US: '美股', HK: '港股' }
  return map[market || ''] || market || '-'
}

function signalLabel(type?: string) {
  const map: Record<string, string> = {
    buy_watch: '买入观察',
    hold_confirm: '持有确认',
    sell_watch: '卖出观察',
    risk_alert: '风险警报',
    no_action: '无动作'
  }
  return map[type || ''] || type || '-'
}

function signalTagType(type?: string) {
  if (type === 'risk_alert' || type === 'sell_watch') return 'danger'
  if (type === 'buy_watch') return 'warning'
  if (type === 'hold_confirm') return 'success'
  return 'info'
}

function scanStatusLabel(status?: string) {
  const map: Record<string, string> = {
    triggered: '已触发',
    no_signal: '无信号',
    error: '错误',
    scanning: '扫描中'
  }
  return map[status || ''] || status || '-'
}

function scanStatusTagType(status?: string) {
  if (status === 'triggered') return 'warning'
  if (status === 'error') return 'danger'
  if (status === 'no_signal') return 'info'
  return 'info'
}

function scanItemDescription(row: any) {
  if (row.error) return row.error
  if (row.report_skipped_reason) return row.report_skipped_reason
  if (row.reasons?.length) return row.reasons[0]
  if (row.data_gaps?.length) return row.data_gaps[0]
  if (row.status === 'no_signal') return '本次扫描未达到价格、趋势或权威证据触发阈值'
  return '-'
}

function formatTime(value?: string) {
  if (!value) return '-'
  try {
    return new Date(value).toLocaleString()
  } catch {
    return value
  }
}

function formatNumber(value?: number) {
  if (value === undefined || value === null) return '-'
  return Number(value).toFixed(2)
}

function formatPercent(value?: number) {
  if (value === undefined || value === null) return '-'
  return `${Number(value).toFixed(2)}%`
}
</script>

<style lang="scss" scoped>
.monitoring-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;

  .page-title {
    display: flex;
    align-items: center;
    gap: 8px;
    margin: 0;
    font-size: 24px;
    color: var(--el-text-color-primary);
  }

  .page-description {
    margin: 8px 0 0;
    color: var(--el-text-color-secondary);
  }
}

.header-actions,
.section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.summary-row {
  row-gap: 12px;
}

.muted {
  color: var(--el-text-color-secondary);
  font-size: 13px;
}

.run-summary {
  row-gap: 12px;
}

.run-stat {
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 8px;
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 4px;

  span {
    color: var(--el-text-color-secondary);
    font-size: 12px;
  }

  strong {
    font-size: 22px;
  }
}

.scan-table {
  margin-top: 14px;
}

.metric-panel {
  min-height: 76px;
  padding: 16px;
  border: 1px solid var(--el-border-color-light);
  border-radius: 8px;
  background: var(--el-bg-color);
  display: flex;
  flex-direction: column;
  justify-content: center;

  .metric-label {
    color: var(--el-text-color-secondary);
    font-size: 13px;
  }

  strong {
    font-size: 28px;
    line-height: 1.2;
    color: var(--el-text-color-primary);
  }
}

.section-card {
  border-radius: 8px;
}

.symbol-cell {
  display: flex;
  flex-direction: column;

  span {
    color: var(--el-text-color-secondary);
    font-size: 12px;
  }
}

.report-detail {
  display: flex;
  flex-direction: column;
  gap: 16px;

  h2,
  h3,
  p {
    margin: 0;
  }

  h3 {
    font-size: 16px;
  }

  ul {
    margin: 0;
    padding-left: 20px;
  }
}

.report-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;

  p {
    margin-top: 4px;
    color: var(--el-text-color-secondary);
  }
}

.evidence-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.evidence-item {
  border: 1px solid var(--el-border-color-light);
  border-radius: 8px;
  padding: 12px;

  a {
    display: block;
    color: var(--el-color-primary);
    margin-top: 6px;
  }

  p {
    margin-top: 6px;
  }

  small {
    display: block;
    margin-top: 6px;
    color: var(--el-text-color-secondary);
  }
}

.evidence-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  color: var(--el-text-color-secondary);
}

.gap-alert {
  margin-top: 8px;
}

@media (max-width: 768px) {
  .page-header {
    flex-direction: column;
  }

  .header-actions {
    width: 100%;
    justify-content: flex-start;
    flex-wrap: wrap;
  }
}
</style>
