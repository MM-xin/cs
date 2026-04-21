<script setup>
import { onMounted, onUnmounted, ref, nextTick, watch } from 'vue'
import * as echarts from 'echarts/core'
import { BarChart, LineChart } from 'echarts/charts'
import {
  GridComponent,
  LegendComponent,
  TitleComponent,
  TooltipComponent,
} from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getDashboard, recalculateAll } from '../services/items'
import { getMe, logout } from '../services/auth'

echarts.use([BarChart, LineChart, GridComponent, LegendComponent, TitleComponent, TooltipComponent, CanvasRenderer])

const router = useRouter()
const username = ref('')
const loading = ref(false)
const data = ref(null)
const trendRef = ref(null)
let trendChart = null

function formatMoney(value) {
  return Number(value || 0).toFixed(2)
}

function renderTrendChart() {
  if (!trendRef.value || !data.value) return
  if (!trendChart) trendChart = echarts.init(trendRef.value)
  const trend = data.value.monthly_trend || []
  const option = {
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'cross' },
    },
    legend: { data: ['利润', '营收', '出货数'] },
    grid: { left: 60, right: 60, top: 50, bottom: 40 },
    xAxis: {
      type: 'category',
      data: trend.map((t) => t.month),
      boundaryGap: true,
    },
    yAxis: [
      { type: 'value', name: '金额', axisLabel: { formatter: (v) => Number(v).toFixed(0) } },
      { type: 'value', name: '数量', position: 'right' },
    ],
    series: [
      {
        name: '利润',
        type: 'bar',
        data: trend.map((t) => t.profit),
        itemStyle: {
          color: (p) => (p.data >= 0 ? '#e02828' : '#13a34b'),
        },
      },
      {
        name: '营收',
        type: 'line',
        smooth: true,
        data: trend.map((t) => t.revenue),
        lineStyle: { color: '#3b82f6' },
        itemStyle: { color: '#3b82f6' },
      },
      {
        name: '出货数',
        type: 'line',
        yAxisIndex: 1,
        smooth: true,
        data: trend.map((t) => t.count),
        lineStyle: { color: '#f59e0b' },
        itemStyle: { color: '#f59e0b' },
      },
    ],
  }
  trendChart.setOption(option)
}

function handleResize() {
  trendChart?.resize()
}

async function loadData() {
  loading.value = true
  try {
    await getMe()
    const me = await getMe()
    username.value = me.username
    data.value = await getDashboard()
    await nextTick()
    renderTrendChart()
  } catch {
    router.push('/login')
  } finally {
    loading.value = false
  }
}

async function onRecalculate() {
  await ElMessageBox.confirm('将基于当前买入/卖出价重算全部饰品的利润与手续费，确定继续？', '提示', {
    type: 'warning',
  })
  const result = await recalculateAll()
  ElMessage.success(`已重算 ${result.updated} 条饰品`)
  await loadData()
}

async function onLogout() {
  await logout()
  router.push('/login')
}

watch(data, () => renderTrendChart())

onMounted(() => {
  loadData()
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  trendChart?.dispose()
})
</script>

<template>
  <div class="page">
    <el-card shadow="never" v-loading="loading">
      <div class="toolbar">
        <div>
          <h2 class="title">数据仪表盘</h2>
          <p class="sub">当前用户：{{ username }}</p>
        </div>
        <div class="toolbar-actions">
          <el-button @click="router.push('/items')">饰品列表</el-button>
          <el-button :loading="loading" @click="loadData">刷新</el-button>
          <el-button type="primary" @click="onRecalculate">重算利润</el-button>
          <el-button @click="onLogout">退出登录</el-button>
        </div>
      </div>

      <template v-if="data">
        <div class="dashboard-grid">
          <el-card shadow="hover" class="dash-card">
            <div class="stat-label">在库数量 / 冷却</div>
            <div class="stat-value">
              {{ data.counts.in_stock }}
              <small>（冷却 {{ data.counts.cooling }}）</small>
            </div>
          </el-card>
          <el-card shadow="hover" class="dash-card">
            <div class="stat-label">已售 / 撤回</div>
            <div class="stat-value">
              {{ data.counts.sold }}
              <small>（撤回 {{ data.counts.withdrawn }}）</small>
            </div>
          </el-card>
          <el-card shadow="hover" class="dash-card">
            <div class="stat-label">在库成本</div>
            <div class="stat-value">{{ formatMoney(data.inventory.cost) }}</div>
            <div class="stat-sub">冷却占用 {{ formatMoney(data.inventory.cooling_cost) }}（{{ (data.inventory.cooling_ratio * 100).toFixed(1) }}%）</div>
          </el-card>
          <el-card shadow="hover" class="dash-card">
            <div class="stat-label">在库市值</div>
            <div class="stat-value">{{ formatMoney(data.inventory.market_value) }}</div>
            <div
              class="stat-sub"
              :class="{ 'profit-up': data.inventory.floating_pnl >= 0, 'profit-down': data.inventory.floating_pnl < 0 }"
            >
              浮动盈亏 {{ formatMoney(data.inventory.floating_pnl) }}
            </div>
          </el-card>
          <el-card shadow="hover" class="dash-card">
            <div class="stat-label">累计已实现利润</div>
            <div
              class="stat-value"
              :class="{ 'profit-up': data.realized.profit >= 0, 'profit-down': data.realized.profit < 0 }"
            >
              {{ formatMoney(data.realized.profit) }}
            </div>
            <div class="stat-sub">营收 {{ formatMoney(data.realized.revenue) }} / 手续费 {{ formatMoney(data.realized.fee) }}</div>
          </el-card>
          <el-card shadow="hover" class="dash-card">
            <div class="stat-label">近 30 天</div>
            <div
              class="stat-value"
              :class="{ 'profit-up': data.recent_30d.profit >= 0, 'profit-down': data.recent_30d.profit < 0 }"
            >
              {{ formatMoney(data.recent_30d.profit) }}
            </div>
            <div class="stat-sub">出货 {{ data.recent_30d.count }} 件 / 营收 {{ formatMoney(data.recent_30d.revenue) }}</div>
          </el-card>
        </div>

        <el-card shadow="hover" class="chart-card">
          <div class="chart-title">近 12 个月利润 / 营收趋势</div>
          <div ref="trendRef" class="chart-container" />
        </el-card>

        <div class="rank-grid">
          <el-card shadow="hover" class="rank-card">
            <div class="chart-title">利润 Top 5</div>
            <el-table :data="data.top_profit" size="small" empty-text="暂无数据">
              <el-table-column prop="name" label="名称" min-width="160" show-overflow-tooltip />
              <el-table-column label="买入" width="80" align="center">
                <template #default="{ row }">{{ formatMoney(row.buy_price) }}</template>
              </el-table-column>
              <el-table-column label="卖出" width="80" align="center">
                <template #default="{ row }">{{ formatMoney(row.sell_price) }}</template>
              </el-table-column>
              <el-table-column label="利润" width="90" align="center">
                <template #default="{ row }">
                  <span class="profit-up">{{ formatMoney(row.profit) }}</span>
                </template>
              </el-table-column>
              <el-table-column prop="sold_time_display" label="时间" min-width="140" />
            </el-table>
          </el-card>
          <el-card shadow="hover" class="rank-card">
            <div class="chart-title">亏损 Top 5</div>
            <el-table :data="data.top_loss" size="small" empty-text="暂无数据">
              <el-table-column prop="name" label="名称" min-width="160" show-overflow-tooltip />
              <el-table-column label="买入" width="80" align="center">
                <template #default="{ row }">{{ formatMoney(row.buy_price) }}</template>
              </el-table-column>
              <el-table-column label="卖出" width="80" align="center">
                <template #default="{ row }">{{ formatMoney(row.sell_price) }}</template>
              </el-table-column>
              <el-table-column label="利润" width="90" align="center">
                <template #default="{ row }">
                  <span class="profit-down">{{ formatMoney(row.profit) }}</span>
                </template>
              </el-table-column>
              <el-table-column prop="sold_time_display" label="时间" min-width="140" />
            </el-table>
          </el-card>
        </div>
      </template>
    </el-card>
  </div>
</template>

<style scoped>
.dashboard-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
  gap: 16px;
  margin-bottom: 18px;
}
.dash-card .stat-label {
  color: #667085;
  font-size: 13px;
}
.dash-card .stat-value {
  font-size: 24px;
  font-weight: 600;
  color: #1f2d3d;
  margin-top: 6px;
}
.dash-card .stat-value small {
  font-size: 13px;
  color: #667085;
  font-weight: 400;
}
.dash-card .stat-sub {
  margin-top: 4px;
  font-size: 12px;
  color: #667085;
}
.chart-card {
  margin-bottom: 18px;
}
.chart-title {
  font-size: 14px;
  font-weight: 600;
  color: #1f2d3d;
  margin-bottom: 10px;
}
.chart-container {
  width: 100%;
  height: 340px;
}
.rank-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(360px, 1fr));
  gap: 16px;
}
.profit-up {
  color: #e02828;
  font-weight: 500;
}
.profit-down {
  color: #13a34b;
  font-weight: 500;
}
.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 18px;
}
.toolbar .title {
  margin: 0;
  font-size: 20px;
  color: #1f2d3d;
}
.toolbar .sub {
  margin: 4px 0 0;
  font-size: 13px;
  color: #667085;
}
</style>
