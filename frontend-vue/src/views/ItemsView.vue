<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import dayjs from 'dayjs'
import { debounce } from 'lodash-es'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getMe, logout } from '../services/auth'
import {
  buildExportUrl,
  cloneItem,
  deleteItem,
  getItemTrades,
  getItems,
  getMeta,
  getPricesConfig,
  inlineUpdateItem,
  refreshPriceForItem,
  refreshPrices,
} from '../services/items'
import { useRouter } from 'vue-router'
import StatsCards from '../components/StatsCards.vue'
import ItemFilters from '../components/ItemFilters.vue'
import ItemFormDialog from '../components/ItemFormDialog.vue'
import BulkCreateDialog from '../components/BulkCreateDialog.vue'
import BulkSellDialog from '../components/BulkSellDialog.vue'
import TradeHistoryDialog from '../components/TradeHistoryDialog.vue'
import CatalogBrowser from '../components/CatalogBrowser.vue'

const router = useRouter()
const username = ref('')
const loading = ref(false)
const items = ref([])
const meta = reactive({
  status_options: [],
  category_options: [],
})
const filters = reactive({
  search: '',
  status: '',
  category: '',
  start_date: '',
  end_date: '',
  month: '',
  sold_start_date: '',
  sold_end_date: '',
  sold_month: '',
})

const formDialogVisible = ref(false)
const editingId = ref(null)
const editRowStatus = ref('')
const formInitial = ref({})

const bulkCreateVisible = ref(false)
const bulkSellVisible = ref(false)
const selectedRows = ref([])
const tableRef = ref(null)

const tradeDialogVisible = ref(false)
const tradeDialogTitle = ref('交易流水')
const tradesLoading = ref(false)
const trades = ref([])

const activeMenu = ref('unsold')
const mergeSameName = ref(true)
const priceRefreshing = ref(false)
const priceRefreshingRows = reactive({})
const priceConfig = ref({ default_platform: 'youpin', refresh_minutes: 15 })
let autoRefreshTimer = null

const menuCounts = computed(() => {
  const unsold = items.value.filter((x) => x.status !== 'sold').length
  const sold = items.value.filter((x) => x.status === 'sold').length
  return { unsold, sold }
})

function parseTime(value) {
  if (!value) return 0
  const ts = dayjs(value).valueOf()
  return Number.isNaN(ts) ? 0 : ts
}

function averageNumber(rows, key) {
  if (!rows.length) return 0
  const nums = rows.map((row) => Number(row[key] ?? 0)).filter((num) => !Number.isNaN(num))
  if (!nums.length) return 0
  return nums.reduce((sum, num) => sum + num, 0) / nums.length
}

const activeItems = computed(() => {
  const base = items.value.filter((item) => {
    if (activeMenu.value === 'sold') return item.status === 'sold'
    return item.status !== 'sold'
  })
  return [...base].sort((a, b) => {
    const aTime = activeMenu.value === 'sold' ? parseTime(a.sold_time) : parseTime(a.buy_time)
    const bTime = activeMenu.value === 'sold' ? parseTime(b.sold_time) : parseTime(b.buy_time)
    if (bTime !== aTime) return bTime - aTime
    return Number(b.id || 0) - Number(a.id || 0)
  })
})

const displayItems = computed(() => {
  if (!mergeSameName.value) return activeItems.value

  const grouped = new Map()
  for (const item of activeItems.value) {
    const key = (item.market_hash_name && String(item.market_hash_name).trim())
      || (item.name && String(item.name).trim())
      || '未命名'
    if (!grouped.has(key)) grouped.set(key, [])
    grouped.get(key).push(item)
  }

  const mergedRows = []
  for (const [, rows] of grouped.entries()) {
    const name = rows[0]?.name || '未命名'
    if (rows.length === 1) {
      mergedRows.push(rows[0])
      continue
    }
    const first = rows[0]
    const avgBuy = averageNumber(rows, 'buy_price')
    const avgCurrent = averageNumber(rows, 'current_price')
    const sellRows = rows.filter((row) => row.sell_price !== null && row.sell_price !== '')
    const avgSell = sellRows.length ? averageNumber(sellRows, 'sell_price') : null
    const avgFee = averageNumber(rows, 'fee_amount')
    const totalProfit = rows.reduce((acc, row) => acc + Number(row.profit || 0), 0)
    const totalBuy = rows.reduce((acc, row) => acc + Number(row.buy_price || 0), 0)
    const avgProfit = totalProfit / rows.length
    const weightedProfitPercent = totalBuy > 0 ? (totalProfit / totalBuy) * 100 : 0
    const latestBuy = [...rows].sort((a, b) => parseTime(b.buy_time) - parseTime(a.buy_time))[0]
    const latestSold = [...rows].sort((a, b) => parseTime(b.sold_time) - parseTime(a.sold_time))[0]
    const rowsWithPrev = rows.filter((row) => {
      const prev = row.previous_price
      const cur = row.current_price
      return (
        prev !== null &&
        prev !== undefined &&
        prev !== '' &&
        cur !== null &&
        cur !== undefined &&
        cur !== ''
      )
    })
    let avgChange = null
    let avgChangePct = null
    let avgPrevPrice = null
    if (rowsWithPrev.length) {
      const prevSum = rowsWithPrev.reduce((acc, row) => acc + Number(row.previous_price || 0), 0)
      const curSum = rowsWithPrev.reduce((acc, row) => acc + Number(row.current_price || 0), 0)
      const prevAvg = prevSum / rowsWithPrev.length
      const curAvg = curSum / rowsWithPrev.length
      avgPrevPrice = prevAvg
      avgChange = curAvg - prevAvg
      avgChangePct = prevAvg > 0 ? (avgChange / prevAvg) * 100 : null
    }
    const latestPriceUpdated = rows
      .map((row) => row.price_updated_at_display)
      .filter(Boolean)
      .sort()
      .slice(-1)[0]
    mergedRows.push({
      ...first,
      id: `merged-${name}`,
      name,
      is_merged: true,
      merge_count: rows.length,
      group_item_ids: rows.map((row) => row.id),
      buy_price: Number(avgBuy.toFixed(2)),
      current_price: Number(avgCurrent.toFixed(2)),
      sell_price: avgSell === null ? null : Number(avgSell.toFixed(2)),
      fee_amount: Number(avgFee.toFixed(2)),
      profit: Number(avgProfit.toFixed(2)),
      profit_percent: Number(weightedProfitPercent.toFixed(2)),
      buy_time: latestBuy?.buy_time || first.buy_time,
      buy_time_display: latestBuy?.buy_time_display || first.buy_time_display,
      sold_time: latestSold?.sold_time || first.sold_time,
      sold_time_display: latestSold?.sold_time_display || first.sold_time_display,
      sold_time_form: latestSold?.sold_time_form || first.sold_time_form,
      is_tradable: rows.every((row) => row.is_tradable),
      price_change: avgChange === null ? null : Number(avgChange.toFixed(2)),
      price_change_percent: avgChangePct === null ? null : Number(avgChangePct.toFixed(2)),
      previous_price: avgPrevPrice === null ? null : Number(avgPrevPrice.toFixed(2)),
      price_updated_at_display: latestPriceUpdated || null,
      price_source: first.price_source || null,
    })
  }

  return mergedRows
})

async function fetchItems() {
  loading.value = true
  try {
    items.value = await getItems({
      search: filters.search,
      status: filters.status,
      category: filters.category,
      start_date: filters.start_date,
      end_date: filters.end_date,
      sold_start_date: filters.sold_start_date,
      sold_end_date: filters.sold_end_date,
    })
  } catch {
    /* handled by interceptor */
  } finally {
    loading.value = false
  }
}

const debouncedFetch = debounce(fetchItems, 300)

watch(
  () => [filters.search],
  () => debouncedFetch(),
)

async function initialize() {
  try {
    const me = await getMe()
    username.value = me.username
    const metaData = await getMeta()
    meta.status_options = metaData.status_options
    meta.category_options = metaData.category_options
    try {
      priceConfig.value = await getPricesConfig()
    } catch {
      /* ignore */
    }
    await fetchItems()
    startAutoRefresh()
  } catch {
    router.push('/login')
  }
}

function startAutoRefresh() {
  const minutes = Number(priceConfig.value?.refresh_minutes || 15)
  const ms = Math.max(1, minutes) * 60 * 1000
  if (autoRefreshTimer) clearInterval(autoRefreshTimer)
  autoRefreshTimer = setInterval(() => {
    if (document.visibilityState === 'visible') {
      fetchItems()
    }
  }, ms)
}

async function onRefreshPrices() {
  priceRefreshing.value = true
  try {
    const r = await refreshPrices()
    if (r.updated) {
      ElMessage.success(`已刷新 ${r.updated} 条价格（跳过 ${r.skipped || 0}）`)
    } else {
      ElMessage.info('没有可刷新的饰品（请确认已绑定 marketHashName）')
    }
    await fetchItems()
  } catch {
    /* interceptor */
  } finally {
    priceRefreshing.value = false
  }
}

async function onRefreshRowPrice(row) {
  const ids = row.is_merged ? row.group_item_ids || [] : [row.id]
  priceRefreshingRows[row.id] = true
  try {
    if (ids.length === 1) {
      await refreshPriceForItem(ids[0])
    } else {
      await refreshPrices(ids)
    }
    ElMessage.success('价格已刷新')
    await fetchItems()
  } catch {
    /* interceptor */
  } finally {
    priceRefreshingRows[row.id] = false
  }
}

onBeforeUnmount(() => {
  if (autoRefreshTimer) clearInterval(autoRefreshTimer)
})

function resetFilters() {
  Object.assign(filters, {
    search: '',
    status: '',
    category: '',
    start_date: '',
    end_date: '',
    month: '',
    sold_start_date: '',
    sold_end_date: '',
    sold_month: '',
  })
  fetchItems()
}

function openCreateDialog() {
  editingId.value = null
  editRowStatus.value = ''
  formInitial.value = {}
  formDialogVisible.value = true
}

function openBulkCreateDialog() {
  bulkCreateVisible.value = true
}

function openBulkSellDialog() {
  if (!selectedRows.value.length) {
    ElMessage.warning('请至少勾选 1 件在库饰品')
    return
  }
  bulkSellVisible.value = true
}

function onSelectionChange(rows) {
  selectedRows.value = rows || []
}

function clearTableSelection() {
  selectedRows.value = []
  tableRef.value?.clearSelection?.()
}

async function onBulkSaved() {
  clearTableSelection()
  await fetchItems()
}

function openEditDialog(row) {
  if (row.is_merged) {
    ElMessage.warning('合并视图下请先关闭"合并同名"再编辑单条')
    return
  }
  editingId.value = row.id
  editRowStatus.value = row.status
  formInitial.value = {
    name: row.name,
    market_hash_name: row.market_hash_name || '',
    wear: row.wear || '',
    category: row.category,
    steamdt_id: row.steamdt_id,
    image_url: row.image_url,
    buy_price: row.buy_price,
    buy_time: row.buy_time_display || dayjs().format('YYYY-MM-DD HH:mm:ss'),
    sold_time: row.sold_time_form || '',
    note: row.note,
  }
  formDialogVisible.value = true
}

async function openTradeDialog(row) {
  if (!row.sold_time_display) return
  const itemIds = row.is_merged ? row.group_item_ids || [] : [row.id]
  tradeDialogTitle.value = row.is_merged
    ? `${row.name} - 交易流水（${row.merge_count}件）`
    : `${row.name} - 交易流水`
  tradeDialogVisible.value = true
  tradesLoading.value = true
  try {
    const responses = await Promise.all(itemIds.map((itemId) => getItemTrades(itemId)))
    trades.value = responses
      .flat()
      .sort((a, b) => parseTime(b.trade_time) - parseTime(a.trade_time))
  } catch {
    trades.value = []
  } finally {
    tradesLoading.value = false
  }
}

async function onDelete(row) {
  if (row.is_merged) {
    ElMessage.warning('合并视图下请先关闭"合并同名"再删除')
    return
  }
  await ElMessageBox.confirm(
    `确定删除 ${row.name} 吗？将同时清除它的流水记录与历史审计，且不可恢复。`,
    '删除确认',
    { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' },
  )
  const resp = await deleteItem(row.id)
  const c = resp?.cascade || {}
  ElMessage.success(
    `已删除 ${row.name}（流水 ${c.trades ?? 0} 条，审计 ${c.audit_logs ?? 0} 条）`,
  )
  await fetchItems()
}

async function onClone(row) {
  if (row.is_merged) {
    ElMessage.warning('合并视图下请先关闭"合并同名"再复制')
    return
  }
  await cloneItem(row.id)
  ElMessage.success('饰品已复制')
  await fetchItems()
}

async function onInlineEdit(row, field, value) {
  if (row.is_merged) {
    ElMessage.warning('合并视图下请先关闭"合并同名"再编辑价格')
    return
  }
  try {
    const response = await inlineUpdateItem(row.id, { field, value: String(value ?? '') })
    const previous = response?.previous ?? null
    ElMessage({
      type: 'success',
      message: `已更新 ${field === 'buy_price' ? '买入价' : '卖出价'}`,
      duration: 4000,
      showClose: true,
      dangerouslyUseHTMLString: true,
      customClass: 'inline-edit-toast',
    })
    await fetchItems()

    ElMessageBox.confirm(
      `已将 ${row.name} 的 ${field === 'buy_price' ? '买入价' : '卖出价'} 从 ${
        previous === null || previous === '' ? '空' : previous
      } 改为 ${value === null || value === '' ? '空' : value}，是否撤销？`,
      '撤销确认',
      {
        confirmButtonText: '撤销',
        cancelButtonText: '保留',
        type: 'info',
        distinguishCancelAndClose: true,
        callback: async (action) => {
          if (action === 'confirm') {
            try {
              await inlineUpdateItem(row.id, {
                field,
                value: previous === null || previous === undefined ? '' : String(previous),
              })
              ElMessage.success('已撤销本次修改')
              await fetchItems()
            } catch {
              /* handled */
            }
          }
        },
      },
    ).catch(() => {})
  } catch {
    /* handled by interceptor */
  }
}

function switchMenu(menu) {
  activeMenu.value = menu
  clearTableSelection()
}

watch(mergeSameName, () => {
  clearTableSelection()
})

function statusTagType(row) {
  if (row.status_label === '冷却中') return 'warning'
  if (row.status_label === '在库') return 'success'
  if (row.status_label === '已售') return 'info'
  if (row.status_label === '撤回') return 'danger'
  return ''
}

function onExport() {
  const url = buildExportUrl({
    search: filters.search,
    status: filters.status,
    category: filters.category,
    start_date: filters.start_date,
    end_date: filters.end_date,
    sold_start_date: filters.sold_start_date,
    sold_end_date: filters.sold_end_date,
  })
  window.open(url, '_blank')
}

async function onLogout() {
  await logout()
  router.push('/login')
}

function fallbackImage(event) {
  event.target.src = 'https://placehold.co/120x90?text=CS2'
}

onMounted(initialize)
</script>

<template>
  <div class="page">
    <el-card shadow="never">
      <div class="toolbar">
        <div>
          <h2 class="title">CS 饰品管理</h2>
          <p class="sub">当前用户：{{ username }}</p>
        </div>
        <div class="toolbar-actions">
          <el-button @click="router.push('/dashboard')">仪表盘</el-button>
          <el-button :loading="priceRefreshing" @click="onRefreshPrices">
            刷新价格
          </el-button>
          <el-button
            v-if="activeMenu === 'unsold'"
            :disabled="!selectedRows.length"
            type="warning"
            @click="openBulkSellDialog"
          >
            批量出售{{ selectedRows.length ? ` (${selectedRows.length})` : '' }}
          </el-button>
          <el-button type="primary" @click="openCreateDialog">新增饰品</el-button>
          <el-button type="primary" plain @click="openBulkCreateDialog">批量新增</el-button>
          <el-button @click="onLogout">退出登录</el-button>
        </div>
      </div>

      <div class="content-layout">
        <aside class="left-menu">
          <button
            type="button"
            class="menu-btn"
            :class="{ active: activeMenu === 'unsold' }"
            @click="switchMenu('unsold')"
          >
            在库饰品
            <span class="menu-count">{{ menuCounts.unsold }}</span>
          </button>
          <button
            type="button"
            class="menu-btn"
            :class="{ active: activeMenu === 'sold' }"
            @click="switchMenu('sold')"
          >
            已售饰品
            <span class="menu-count">{{ menuCounts.sold }}</span>
          </button>
          <button
            type="button"
            class="menu-btn"
            :class="{ active: activeMenu === 'catalog' }"
            @click="switchMenu('catalog')"
          >
            饰品目录
          </button>
          <el-switch
            v-if="activeMenu !== 'catalog'"
            v-model="mergeSameName"
            class="merge-switch"
            active-text="合并同名"
          />
        </aside>

        <div class="content-main">
          <CatalogBrowser v-if="activeMenu === 'catalog'" />
          <template v-else>
          <StatsCards :items="activeItems" />

          <ItemFilters
            v-model="filters"
            :meta="meta"
            @filter="fetchItems"
            @reset="resetFilters"
            @export="onExport"
          />

          <el-table
            ref="tableRef"
            :data="displayItems"
            v-loading="loading"
            border
            stripe
            class="table inventory-table"
            :header-cell-style="{ textAlign: 'center' }"
            empty-text="暂无饰品数据，点击右上角新增饰品开始管理"
            :row-key="(row) => row.id"
            @selection-change="onSelectionChange"
          >
            <el-table-column
              v-if="activeMenu === 'unsold' && !mergeSameName"
              type="selection"
              width="42"
              :selectable="(row) => !row.is_merged && row.status !== 'sold'"
              reserve-selection
            />
            <el-table-column label="图片" width="94">
              <template #default="{ row }">
                <img
                  :src="row.image_url"
                  :alt="row.name"
                  class="thumb"
                  referrerpolicy="no-referrer"
                  @error="fallbackImage"
                />
              </template>
            </el-table-column>
            <el-table-column label="名称" min-width="180">
              <template #default="{ row }">
                <div class="item-name-wrap">
                  <div class="item-name">{{ row.name }}</div>
                  <span v-if="row.is_merged" class="stack-count">
                    <span class="stack-icon" />
                    x{{ row.merge_count }}
                  </span>
                </div>
                <div class="item-buy-time">
                  {{ row.buy_time_display || '-' }}
                </div>
              </template>
            </el-table-column>
            <el-table-column prop="category" label="类型" width="100" align="center" header-align="center">
              <template #default="{ row }">
                <el-tag size="small" effect="plain">{{ row.category }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="买入价" width="135">
              <template #default="{ row }">
                <span v-if="row.is_merged" class="avg-value">{{ Number(row.buy_price || 0).toFixed(2) }}</span>
                <el-input-number
                  v-else
                  :model-value="row.buy_price"
                  :min="0"
                  :precision="2"
                  :controls="false"
                  size="small"
                  class="minimal-input"
                  @change="(v) => onInlineEdit(row, 'buy_price', v)"
                />
              </template>
            </el-table-column>
            <el-table-column label="当前价" width="130" align="center" header-align="center">
              <template #default="{ row }">
                <div class="price-cell">
                  <div
                    v-if="row.price_change !== null && row.price_change !== undefined"
                    class="price-change"
                    :class="{
                      'price-up': Number(row.price_change) > 0,
                      'price-down': Number(row.price_change) < 0,
                      'price-flat': Number(row.price_change) === 0,
                    }"
                  >
                    {{ Number(row.price_change) > 0 ? '+' : '' }}{{ Number(row.price_change).toFixed(2) }}
                    <span
                      v-if="row.price_change_percent !== null && row.price_change_percent !== undefined"
                      class="price-change-pct"
                    >
                      ({{ Number(row.price_change_percent) > 0 ? '+' : '' }}{{ Number(row.price_change_percent).toFixed(2) }}%)
                    </span>
                  </div>
                  <div v-else class="price-change price-flat">—</div>
                  <div class="price-current">
                    <el-tooltip
                      v-if="row.price_updated_at_display || row.previous_price"
                      placement="top"
                    >
                      <template #content>
                        <div class="price-tip">
                          <div v-if="row.price_source || row.price_updated_at_display">
                            {{ row.price_source || '' }}{{ row.price_source && row.price_updated_at_display ? ' · ' : '' }}{{ row.price_updated_at_display || '' }}
                          </div>
                          <div v-if="row.previous_price !== null && row.previous_price !== undefined && row.previous_price !== ''">
                            上次价格: ¥ {{ Number(row.previous_price).toFixed(2) }}
                          </div>
                        </div>
                      </template>
                      <span>¥ {{ Number(row.current_price || 0).toFixed(2) }}</span>
                    </el-tooltip>
                    <span v-else>¥ {{ Number(row.current_price || 0).toFixed(2) }}</span>
                  </div>
                </div>
              </template>
            </el-table-column>
            <el-table-column label="卖出价" width="135">
              <template #default="{ row }">
                <span v-if="row.is_merged">
                  {{ row.sell_price === null || row.sell_price === '' ? '-' : Number(row.sell_price).toFixed(2) }}
                </span>
                <el-input-number
                  v-else
                  :disabled="!row.is_tradable && row.status !== 'sold'"
                  :model-value="row.sell_price"
                  :min="0"
                  :step="1"
                  :controls="false"
                  size="small"
                  :class="['minimal-input', { 'no-edit-border': row.sell_price === null || row.sell_price === '' }]"
                  @change="(v) => onInlineEdit(row, 'sell_price', v)"
                />
              </template>
            </el-table-column>
            <el-table-column prop="profit" label="利润 (利润率)" width="150" align="center" header-align="center">
              <template #default="{ row }">
                <span
                  :class="{
                    'profit-up': Number(row.profit || 0) >= 0,
                    'profit-down': Number(row.profit || 0) < 0,
                  }"
                >
                  {{ Number(row.profit || 0).toFixed(2) }}
                  <span class="profit-pct">({{ Number(row.profit_percent || 0).toFixed(2) }}%)</span>
                </span>
              </template>
            </el-table-column>
            <el-table-column label="出售时间" width="160">
              <template #default="{ row }">
                <span v-if="row.sold_time_display" class="sold-time-link" @click="openTradeDialog(row)">
                  {{ row.sold_time_display }}
                </span>
                <span v-else>-</span>
              </template>
            </el-table-column>
            <el-table-column label="状态" width="80" align="center" header-align="center">
              <template #default="{ row }">
                <el-tag :type="statusTagType(row)">{{ row.status_label }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="remaining_time_display" label="剩余时间" width="120" />
            <el-table-column prop="fee_amount" label="手续费" width="70" align="center" header-align="center">
              <template #default="{ row }">
                {{ Number(row.fee_amount || 0).toFixed(2) }}
              </template>
            </el-table-column>
            <el-table-column label="操作" width="260" fixed="right">
              <template #default="{ row }">
                <el-space>
                  <el-button
                    size="small"
                    :loading="!!priceRefreshingRows[row.id]"
                    @click="onRefreshRowPrice(row)"
                  >
                    刷价
                  </el-button>
                  <el-button v-if="row.is_merged" size="small" @click="mergeSameName = false">关闭合并后编辑</el-button>
                  <template v-else>
                    <el-button size="small" @click="openEditDialog(row)">编辑</el-button>
                    <el-button size="small" @click="onClone(row)">复制</el-button>
                    <el-button size="small" type="danger" @click="onDelete(row)">删除</el-button>
                  </template>
                </el-space>
              </template>
            </el-table-column>
          </el-table>
          </template>
        </div>
      </div>
    </el-card>

    <ItemFormDialog
      v-model="formDialogVisible"
      :editing-id="editingId"
      :edit-row-status="editRowStatus"
      :category-options="meta.category_options"
      :initial-data="formInitial"
      @saved="fetchItems"
    />

    <BulkCreateDialog
      v-model="bulkCreateVisible"
      :category-options="meta.category_options"
      @saved="onBulkSaved"
    />

    <BulkSellDialog
      v-model="bulkSellVisible"
      :selected-items="selectedRows"
      @saved="onBulkSaved"
    />

    <TradeHistoryDialog
      v-model="tradeDialogVisible"
      :title="tradeDialogTitle"
      :trades="trades"
      :loading="tradesLoading"
    />
  </div>
</template>

<style scoped>
.sold-time-link {
  color: #1e88ff;
  cursor: pointer;
}
.sold-time-link:hover {
  text-decoration: underline;
}
.price-cell {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  line-height: 1.25;
}
.price-change {
  font-size: 13px;
  font-weight: 600;
}
.price-change-pct {
  font-size: 11px;
  margin-left: 2px;
  font-weight: 500;
}
.price-up {
  color: #e53935;
}
.price-down {
  color: #2e7d32;
}
.price-flat {
  color: #9099ad;
}
.price-current {
  font-size: 12px;
  color: #5a6475;
}
.profit-pct {
  font-size: 11px;
  margin-left: 2px;
  font-weight: 500;
  opacity: 0.85;
}
</style>
