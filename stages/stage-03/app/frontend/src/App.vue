<script setup lang="ts">
import * as echarts from 'echarts'
import { computed, nextTick, onMounted, reactive, watch } from 'vue'

type Page = 'dashboard' | 'device' | 'system'
type Device = {
  id: string
  name: string
  state: string
  power_w: number | null
  power_share?: number
  updated_at?: string | null
}
type EventItem = {
  id: string
  device_id: string
  device_name: string
  type: string
  timestamp: string | null
  source: string
}
type Dashboard = {
  data_status: string
  updated_at: string | null
  total_power_w: number | null
  today_energy_kwh: number | null
  running_devices: Device[]
  top_devices: Device[]
  recent_events: EventItem[]
  advice: { title: string; message: string }
}
type SystemStatus = {
  service: { status: string; stage02_base_url: string; last_heartbeat_at: string | null; error_message: string | null }
  model: {
    version: string | null
    interface_version: string | null
    appliances: string[]
    sample_period_s: number | null
    window_size: number | null
  }
  data_source: { mode: string; running: boolean; sent_rows: number; speed: number | null; latest_data_at: string | null }
}
type DeviceDetail = {
  device: Device
  today_stats: { energy_kwh: number | null; runtime_minutes: number | null; event_count: number }
  series: { range: string; points: Array<{ timestamp: string; power_w: number }> }
  events: EventItem[]
}

const bffBase = new URLSearchParams(location.search).get('api') || 'http://127.0.0.1:18081'
const labels: Record<string, string> = {
  normal: '数据正常',
  delayed: '数据延迟',
  disconnected: '服务断开',
  empty: '暂无数据',
  insufficient: '数据不足',
  running: '运行中',
  off: '关闭',
  unknown: '未知',
  on: '开启',
}
const nav = [
  { id: 'dashboard' as const, label: '总览' },
  { id: 'device' as const, label: '设备' },
  { id: 'system' as const, label: '系统' },
]

const state = reactive<{
  page: Page
  selectedDeviceId: string
  deviceModalOpen: boolean
  loading: boolean
  error: string
  dashboard: Dashboard | null
  system: SystemStatus | null
  device: DeviceDetail | null
  chart: echarts.ECharts | null
}>({
  page: 'dashboard',
  selectedDeviceId: 'kettle',
  deviceModalOpen: false,
  loading: false,
  error: '',
  dashboard: null,
  system: null,
  device: null,
  chart: null,
})

const dataStatus = computed(() => state.dashboard?.data_status || state.system?.service?.status || 'insufficient')
const systemSummary = computed(() => {
  if (!state.system) return { title: '正在检查系统', detail: '等待 BFF 返回系统状态。', status: 'insufficient' }
  if (state.system.service.status === 'disconnected') {
    return { title: '底层服务未连接', detail: 'Stage-03 已启动，但暂时无法访问 Stage-02。', status: 'disconnected' }
  }
  if (!state.system.data_source.latest_data_at) {
    return { title: '服务正常，等待数据', detail: '模型服务已连接，当前还没有可展示的实时样本。', status: 'insufficient' }
  }
  return { title: '系统运行正常', detail: 'BFF、模型服务和数据流状态可用。', status: 'normal' }
})
const systemChecks = computed(() => [
  {
    label: 'Stage-02 服务连接',
    ok: state.system?.service?.status === 'normal',
    detail: state.system?.service?.stage02_base_url || '--',
  },
  {
    label: '模型元数据',
    ok: Boolean(state.system?.model?.version),
    detail: state.system?.model?.version || '暂无模型版本',
  },
  {
    label: '设备列表',
    ok: Boolean(state.system?.model?.appliances?.length),
    detail: (state.system?.model?.appliances || []).join(', ') || '暂无设备',
  },
  {
    label: '实时数据',
    ok: Boolean(state.system?.data_source?.latest_data_at),
    detail: state.system?.data_source?.latest_data_at ? fmtTime(state.system.data_source.latest_data_at) : '暂无实时数据',
  },
])
const devices = computed(() => {
  const map = new Map<string, Device>()
  state.dashboard?.running_devices?.forEach((d) => map.set(d.id, d))
  state.dashboard?.top_devices?.forEach((d) => map.set(d.id, d))
  state.system?.model?.appliances?.forEach((id) => {
    if (!map.has(id)) map.set(id, { id, name: id, state: 'unknown', power_w: null })
  })
  return Array.from(map.values())
})

function fmtW(v: number | null | undefined) {
  return v === null || v === undefined || Number.isNaN(Number(v)) ? '-- W' : `${Math.round(Number(v))} W`
}
function fmtKwh(v: number | null | undefined) {
  return v === null || v === undefined || Number.isNaN(Number(v)) ? '-- kWh' : `${Number(v).toFixed(2)} kWh`
}
function fmtNum(v: number | null | undefined) {
  return v === null || v === undefined || Number.isNaN(Number(v)) ? '--' : Number(v).toLocaleString('zh-CN')
}
function fmtTime(iso: string | null | undefined) {
  if (!iso) return '暂无时间'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return String(iso)
  return d.toLocaleString('zh-CN', { hour12: false })
}
function shortTime(iso: string | null | undefined) {
  if (!iso) return '--'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return '--'
  return d.toLocaleTimeString('zh-CN', { hour12: false })
}
async function fetchJson<T>(path: string, options: RequestInit = {}): Promise<T> {
  const resp = await fetch(`${bffBase}${path}`, {
    ...options,
    headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
  })
  if (!resp.ok) throw new Error(await resp.text())
  return resp.json() as Promise<T>
}

async function loadDashboard() {
  state.loading = true
  state.error = ''
  try {
    state.dashboard = await fetchJson<Dashboard>('/api/dashboard')
    await loadSystem(false)
  } catch (err) {
    state.error = err instanceof Error ? err.message : String(err)
  } finally {
    state.loading = false
  }
}
async function loadSystem(markLoading = true) {
  if (markLoading) state.loading = true
  state.error = ''
  try {
    state.system = await fetchJson<SystemStatus>('/api/system/status')
  } catch (err) {
    state.error = err instanceof Error ? err.message : String(err)
  } finally {
    if (markLoading) state.loading = false
  }
}
async function loadDevice(id: string) {
  state.selectedDeviceId = id
  state.loading = true
  state.error = ''
  try {
    state.device = await fetchJson<DeviceDetail>(`/api/devices/${encodeURIComponent(id)}`)
    await nextTick()
    renderDeviceChart()
  } catch (err) {
    state.error = err instanceof Error ? err.message : String(err)
  } finally {
    state.loading = false
  }
}
function setPage(page: Page) {
  state.page = page
  if (page === 'dashboard') void loadDashboard()
  if (page === 'device') void loadDevice(state.selectedDeviceId)
  if (page === 'system') void loadSystem()
}
function openDevice(id: string) {
  state.page = 'device'
  state.deviceModalOpen = true
  void loadDevice(id)
}
function closeDeviceModal() {
  state.deviceModalOpen = false
}
async function startSimulation() {
  state.error = ''
  try {
    await fetchJson('/api/system/simulation/start', { method: 'POST', body: '{}' })
    await loadSystem(false)
    await loadDashboard()
  } catch (err) {
    state.error = err instanceof Error ? err.message : String(err)
  }
}
async function stopSimulation() {
  state.error = ''
  try {
    await fetchJson('/api/system/simulation/stop', { method: 'POST', body: '{}' })
    await loadSystem(false)
  } catch (err) {
    state.error = err instanceof Error ? err.message : String(err)
  }
}
function renderDeviceChart() {
  const el = document.getElementById('deviceChart')
  if (!el) return
  if (!state.chart) state.chart = echarts.init(el)
  const points = state.device?.series?.points || []
  state.chart.setOption(
    {
      animation: false,
      tooltip: { trigger: 'axis' },
      grid: { left: 44, right: 16, top: 24, bottom: 36 },
      xAxis: { type: 'category', data: points.map((p) => shortTime(p.timestamp)), axisLabel: { showMaxLabel: true } },
      yAxis: { type: 'value', name: 'W' },
      series: [
        {
          name: '估计功率',
          type: 'line',
          showSymbol: false,
          data: points.map((p) => p.power_w),
          lineStyle: { color: '#0c6b5a', width: 2 },
        },
      ],
    },
    true,
  )
}

watch(
  () => state.page,
  async () => {
    await nextTick()
    if (state.page === 'device' && state.deviceModalOpen) renderDeviceChart()
  },
)
onMounted(async () => {
  await loadDashboard()
  window.addEventListener('resize', () => state.chart?.resize())
})
</script>

<template>
  <div class="app">
    <aside class="sidebar">
      <div class="brand">家庭用电看板</div>
      <nav class="nav">
        <button v-for="item in nav" :key="item.id" :class="{ active: state.page === item.id }" @click="setPage(item.id)">
          {{ item.label }}
        </button>
      </nav>
      <div class="side-status">
        <div><span class="badge" :class="dataStatus">{{ labels[dataStatus] || dataStatus }}</span></div>
        <div class="side-status-line">BFF: {{ state.system?.service?.status || 'checking' }}</div>
      </div>
    </aside>

    <main class="main">
      <div class="page-header">
        <div>
          <h1 v-if="state.page === 'dashboard'">家庭用电总览</h1>
          <h1 v-else-if="state.page === 'device'">设备总览</h1>
          <h1 v-else>系统状态</h1>
          <div v-if="state.page === 'dashboard'" class="sub">最近更新：{{ fmtTime(state.dashboard?.updated_at) }}</div>
          <div v-else-if="state.page === 'device'" class="sub">点击设备卡片查看功率曲线、事件和今日统计</div>
          <div v-else class="sub">Stage-03 BFF 连接 Stage-02 推理服务</div>
        </div>
        <div class="toolbar">
          <button v-if="state.page === 'dashboard'" @click="loadDashboard">刷新</button>
          <button v-if="state.page === 'device'" @click="loadDashboard">刷新</button>
          <button v-if="state.page === 'system'" @click="loadSystem()">刷新</button>
        </div>
      </div>

      <div v-if="state.error" class="panel error-panel">
        <span class="badge disconnected">服务提示</span>
        <div class="metric-help">{{ state.error }}</div>
      </div>

      <section v-if="state.page === 'dashboard'" class="grid">
        <div class="panel span-6">
          <div class="metric-label">当前估计总功率</div>
          <div class="metric-value">{{ fmtW(state.dashboard?.total_power_w) }}</div>
          <div class="metric-help"><span class="badge" :class="state.dashboard?.data_status">{{ labels[state.dashboard?.data_status || ''] || '数据检查中' }}</span></div>
        </div>
        <div class="panel span-6">
          <div class="metric-label">今日估计用电量</div>
          <div class="metric-value">{{ fmtKwh(state.dashboard?.today_energy_kwh) }}</div>
          <div class="metric-help">当前聚合数据不足时会保留占位，不制造虚假的日统计。</div>
        </div>

        <div class="panel span-6">
          <div class="panel-title">当前运行设备</div>
          <div v-if="state.dashboard?.running_devices?.length" class="list">
            <div v-for="d in state.dashboard.running_devices" :key="d.id" class="row clickable" @click="openDevice(d.id)">
              <div class="row-main">
                <div class="row-title">{{ d.name }}</div>
                <div class="row-sub"><span class="badge" :class="d.state">{{ labels[d.state] }}</span></div>
              </div>
              <div class="row-value">{{ fmtW(d.power_w) }}</div>
            </div>
          </div>
          <div v-else class="empty">暂无设备运行，或当前窗口数据不足。</div>
        </div>

        <div class="panel span-6">
          <div class="panel-title">当前耗电 Top 3</div>
          <div v-if="state.dashboard?.top_devices?.length" class="list">
            <div v-for="(d, i) in state.dashboard.top_devices" :key="d.id" class="row clickable" @click="openDevice(d.id)">
              <div class="row-main">
                <div class="row-title">{{ i + 1 }}. {{ d.name }}</div>
                <div class="row-sub">{{ Math.round((d.power_share || 0) * 100) }}%</div>
              </div>
              <div class="row-value">{{ fmtW(d.power_w) }}</div>
            </div>
          </div>
          <div v-else class="empty">暂无足够的设备功率数据。</div>
        </div>

        <div class="panel span-7">
          <div class="panel-title">最近事件</div>
          <div v-if="state.dashboard?.recent_events?.length" class="list">
            <div v-for="e in state.dashboard.recent_events" :key="e.id" class="row clickable" @click="openDevice(e.device_id)">
              <div class="row-main">
                <div class="row-title">{{ e.device_name }} {{ labels[e.type] || e.type }}</div>
                <div class="row-sub">{{ fmtTime(e.timestamp) }}</div>
              </div>
              <span class="badge">{{ e.source }}</span>
            </div>
          </div>
          <div v-else class="empty">暂无最近事件。</div>
        </div>
        <div class="panel span-5">
          <div class="panel-title">提醒 / 建议</div>
          <div class="row">
            <div class="row-main">
              <div class="row-title">{{ state.dashboard?.advice?.title || '暂无明显异常' }}</div>
              <div class="row-sub">{{ state.dashboard?.advice?.message || '建议功能暂作为占位。' }}</div>
            </div>
          </div>
        </div>
      </section>

      <section v-else-if="state.page === 'device'" class="grid">
        <div class="panel span-12">
          <div class="panel-title">全部设备</div>
          <div v-if="devices.length" class="device-grid">
            <button
              v-for="d in devices"
              :key="d.id"
              class="device-tile"
              type="button"
              @click="openDevice(d.id)"
            >
              <span class="device-tile-top">
                <span class="device-name">{{ d.name || d.id }}</span>
                <span class="badge" :class="d.state">{{ labels[d.state] || '未知' }}</span>
              </span>
              <span class="device-power">{{ fmtW(d.power_w) }}</span>
              <span class="device-meta">最近更新：{{ fmtTime(d.updated_at) }}</span>
            </button>
          </div>
          <div v-else class="empty">暂无设备数据。请先确认系统状态或启动模拟流。</div>
        </div>
        <div class="panel span-6">
          <div class="panel-title">运行设备</div>
          <div v-if="state.dashboard?.running_devices?.length" class="list">
            <div v-for="d in state.dashboard.running_devices" :key="d.id" class="row clickable" @click="openDevice(d.id)">
              <div class="row-title">{{ d.name }}</div>
              <div class="row-value">{{ fmtW(d.power_w) }}</div>
            </div>
          </div>
          <div v-else class="empty">当前没有识别到正在运行的设备。</div>
        </div>
        <div class="panel span-6">
          <div class="panel-title">最近设备事件</div>
          <div v-if="state.dashboard?.recent_events?.length" class="list">
            <div v-for="e in state.dashboard.recent_events" :key="e.id" class="row clickable" @click="openDevice(e.device_id)">
              <div class="row-title">{{ e.device_name }} {{ labels[e.type] || e.type }}</div>
              <div class="row-value">{{ shortTime(e.timestamp) }}</div>
            </div>
          </div>
          <div v-else class="empty">暂无最近事件。</div>
        </div>
      </section>

      <section v-else class="grid">
        <div class="system-hero span-12" :class="systemSummary.status">
          <div>
            <span class="badge" :class="systemSummary.status">{{ labels[systemSummary.status] || systemSummary.status }}</span>
            <h2>{{ systemSummary.title }}</h2>
            <p>{{ systemSummary.detail }}</p>
          </div>
          <div class="system-hero-meta">
            <div class="metric-label">最近心跳</div>
            <strong>{{ fmtTime(state.system?.service?.last_heartbeat_at) }}</strong>
          </div>
        </div>

        <div class="status-card span-4">
          <div class="metric-label">Stage-02 服务</div>
          <div class="status-card-value">{{ labels[state.system?.service?.status || ''] || '--' }}</div>
          <div class="metric-help">{{ state.system?.service?.stage02_base_url || '--' }}</div>
        </div>
        <div class="status-card span-4">
          <div class="metric-label">数据源</div>
          <div class="status-card-value">{{ state.system?.data_source?.running ? '模拟运行中' : '空闲' }}</div>
          <div class="metric-help">最近数据：{{ fmtTime(state.system?.data_source?.latest_data_at) }}</div>
        </div>
        <div class="status-card span-4">
          <div class="metric-label">已发送样本</div>
          <div class="status-card-value">{{ fmtNum(state.system?.data_source?.sent_rows) }}</div>
          <div class="metric-help">回放速度：{{ state.system?.data_source?.speed ?? '--' }}x</div>
        </div>

        <div class="panel span-7">
          <div class="panel-title">模型能力</div>
          <div class="kv-list">
            <div><span>模型版本</span><strong>{{ state.system?.model?.version || '--' }}</strong></div>
            <div><span>接口版本</span><strong>{{ state.system?.model?.interface_version || '--' }}</strong></div>
            <div><span>窗口大小</span><strong>{{ state.system?.model?.window_size || '--' }}</strong></div>
            <div><span>采样周期</span><strong>{{ state.system?.model?.sample_period_s || '--' }}s</strong></div>
            <div><span>支持设备</span><strong>{{ (state.system?.model?.appliances || []).join(', ') || '--' }}</strong></div>
          </div>
        </div>

        <div class="panel span-5">
          <div class="panel-title">演示控制</div>
          <div class="control-box">
            <div>
              <div class="row-title">模拟回放</div>
              <div class="row-sub">用于给用户应用持续喂入推理数据。</div>
            </div>
            <span class="badge" :class="state.system?.data_source?.running ? 'running' : 'off'">
              {{ state.system?.data_source?.running ? '运行中' : '已停止' }}
            </span>
          </div>
          <div class="toolbar control-actions">
            <button class="primary" :disabled="state.system?.data_source?.running || state.system?.service?.status === 'disconnected'" @click="startSimulation">启动模拟</button>
            <button :disabled="!state.system?.data_source?.running" @click="stopSimulation">停止模拟</button>
          </div>
          <div class="metric-help">该区域只服务演示与管理员，不进入普通用户主流程。</div>
        </div>

        <div class="panel span-7">
          <div class="panel-title">运行检查</div>
          <div class="health-list">
            <div v-for="item in systemChecks" :key="item.label" class="health-item">
              <span class="health-dot" :class="{ ok: item.ok }"></span>
              <div>
                <div class="row-title">{{ item.label }}</div>
                <div class="row-sub">{{ item.detail }}</div>
              </div>
            </div>
          </div>
        </div>

        <div class="panel span-5">
          <div class="panel-title">最近错误</div>
          <div v-if="state.system?.service?.error_message" class="empty error-copy">{{ state.system.service.error_message }}</div>
          <div v-else class="empty">暂无错误信息。</div>
        </div>
      </section>
    </main>

    <div v-if="state.deviceModalOpen" class="modal-backdrop" @click.self="closeDeviceModal">
      <section class="modal">
        <header class="modal-header">
          <div>
            <h2>{{ state.device?.device?.name || '设备详情' }}</h2>
            <div class="sub">
              <span class="badge" :class="state.device?.device?.state">{{ labels[state.device?.device?.state || 'unknown'] }}</span>
              当前估计功率：{{ fmtW(state.device?.device?.power_w) }}
            </div>
          </div>
          <div class="toolbar">
            <select v-model="state.selectedDeviceId" @change="loadDevice(state.selectedDeviceId)">
              <option v-for="d in devices" :key="d.id" :value="d.id">{{ d.name || d.id }}</option>
            </select>
            <button @click="loadDevice(state.selectedDeviceId)">刷新</button>
            <button @click="closeDeviceModal">关闭</button>
          </div>
        </header>
        <div class="grid">
          <div class="panel span-4">
            <div class="metric-label">今日估计用电量</div>
            <div class="metric-value">{{ fmtKwh(state.device?.today_stats?.energy_kwh) }}</div>
          </div>
          <div class="panel span-4">
            <div class="metric-label">今日运行时长</div>
            <div class="metric-value">{{ state.device?.today_stats?.runtime_minutes ?? '--' }} 分钟</div>
          </div>
          <div class="panel span-4">
            <div class="metric-label">今日事件次数</div>
            <div class="metric-value">{{ state.device?.today_stats?.event_count ?? 0 }} 次</div>
          </div>
          <div class="panel span-12">
            <div class="panel-title">功率变化</div>
            <div v-if="state.device?.series?.points?.length" id="deviceChart" class="chart"></div>
            <div v-else class="empty">暂无足够数据绘制设备曲线。启动模拟后，窗口积累到模型长度会逐步出现曲线。</div>
          </div>
          <div class="panel span-6">
            <div class="panel-title">最近事件</div>
            <div v-if="state.device?.events?.length" class="list">
              <div v-for="e in state.device.events" :key="e.id" class="row">
                <div class="row-title">{{ labels[e.type] || e.type }}</div>
                <div class="row-value">{{ shortTime(e.timestamp) }}</div>
              </div>
            </div>
            <div v-else class="empty">该设备暂无最近事件。</div>
          </div>
          <div class="panel span-6">
            <div class="panel-title">运行区间</div>
            <div class="empty">运行区间由后端聚合后提供，P0 暂保留占位。</div>
          </div>
        </div>
      </section>
    </div>

    <nav class="bottom-nav">
      <button v-for="item in nav" :key="item.id" :class="{ active: state.page === item.id }" @click="setPage(item.id)">{{ item.label }}</button>
    </nav>
  </div>
</template>
