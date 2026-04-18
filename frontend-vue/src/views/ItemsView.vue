<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import dayjs from 'dayjs'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getMe, logout } from '../services/auth'
import { cloneItem, createItem, deleteItem, getItems, getMeta, inlineUpdateItem, updateItem } from '../services/items'
import { useRouter } from 'vue-router'

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

const dialogVisible = ref(false)
const editingId = ref(null)
const editRowStatus = ref('')
const form = reactive({
  name: '',
  category: '其他',
  steamdt_id: '',
  image_url: '',
  buy_price: '',
  buy_time: '',
  sold_time: '',
  note: '',
})

const isEditing = computed(() => editingId.value !== null)
const dialogTitle = computed(() => (isEditing.value ? '编辑饰品' : '新增饰品'))
const summary = computed(() => {
  const total = items.value.length
  const inStock = items.value.filter((x) => x.status_label === '在库' || x.status_label === '冷却中').length
  const sold = items.value.filter((x) => x.status_label === '已售').length
  const cooling = items.value.filter((x) => x.status_label === '冷却中').length
  const totalProfit = items.value.reduce((acc, item) => acc + Number(item.profit || 0), 0)
  return { total, inStock, sold, cooling, totalProfit }
})

function resetForm() {
  Object.assign(form, {
    name: '',
    category: '其他',
    steamdt_id: '',
    image_url: '',
    buy_price: '',
    buy_time: dayjs().format('YYYY-MM-DD HH:mm:ss'),
    sold_time: '',
    note: '',
  })
}

function onMonthChange(value) {
  if (!value) {
    filters.start_date = ''
    filters.end_date = ''
    fetchItems()
    return
  }
  const month = dayjs(value)
  filters.start_date = month.startOf('month').format('YYYY-MM-DD')
  filters.end_date = month.endOf('month').format('YYYY-MM-DD')
  fetchItems()
}

function onSoldMonthChange(value) {
  if (!value) {
    filters.sold_start_date = ''
    filters.sold_end_date = ''
    fetchItems()
    return
  }
  const month = dayjs(value)
  filters.sold_start_date = month.startOf('month').format('YYYY-MM-DD')
  filters.sold_end_date = month.endOf('month').format('YYYY-MM-DD')
  fetchItems()
}

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
    ElMessage.error('加载饰品列表失败')
  } finally {
    loading.value = false
  }
}

async function initialize() {
  try {
    const me = await getMe()
    username.value = me.username
    const metaData = await getMeta()
    meta.status_options = metaData.status_options
    meta.category_options = metaData.category_options
    await fetchItems()
  } catch {
    router.push('/login')
  }
}

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
  resetForm()
  dialogVisible.value = true
}

function openEditDialog(row) {
  editingId.value = row.id
  editRowStatus.value = row.status
  Object.assign(form, {
    name: row.name,
    category: row.category,
    steamdt_id: row.steamdt_id || '',
    image_url: row.image_url || '',
    buy_price: row.buy_price,
    buy_time: row.buy_time_display || dayjs().format('YYYY-MM-DD HH:mm:ss'),
    sold_time: row.sold_time_form || '',
    note: row.note || '',
  })
  dialogVisible.value = true
}

async function onSubmitForm() {
  if (isEditing.value && form.sold_time && editRowStatus.value !== 'sold') {
    ElMessage.warning('未出售的饰品不能编辑出售时间')
    return
  }
  try {
    if (isEditing.value) {
      await updateItem(editingId.value, form)
      ElMessage.success('饰品已更新')
    } else {
      await createItem(form)
      ElMessage.success('饰品已新增')
    }
    dialogVisible.value = false
    await fetchItems()
  } catch {
    ElMessage.error('保存失败，请检查输入')
  }
}

async function onDelete(row) {
  await ElMessageBox.confirm(`确定删除 ${row.name} ?`, '提示', { type: 'warning' })
  await deleteItem(row.id)
  ElMessage.success('饰品已删除')
  await fetchItems()
}

async function onClone(row) {
  await cloneItem(row.id)
  ElMessage.success('饰品已克隆')
  await fetchItems()
}

async function onInlineEdit(row, field, value) {
  try {
    await inlineUpdateItem(row.id, { field, value: String(value ?? '') })
    ElMessage.success('已更新')
    await fetchItems()
  } catch {
    ElMessage.error('更新失败')
  }
}

function statusTagType(row) {
  if (row.status_label === '冷却中') return 'warning'
  if (row.status_label === '在库') return 'success'
  if (row.status_label === '已售') return 'info'
  if (row.status_label === '撤回') return 'danger'
  return ''
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
          <h2 class="title">CS 饰品管理（Vue + Element Plus）</h2>
          <p class="sub">当前用户：{{ username }}</p>
        </div>
        <div class="toolbar-actions">
          <el-button type="primary" @click="openCreateDialog">新增饰品</el-button>
          <el-button @click="onLogout">退出登录</el-button>
        </div>
      </div>

      <div class="stats-grid">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-label">饰品总数</div>
          <div class="stat-value">{{ summary.total }}</div>
        </el-card>
        <el-card shadow="hover" class="stat-card">
          <div class="stat-label">在库数量</div>
          <div class="stat-value">{{ summary.inStock }}</div>
        </el-card>
        <el-card shadow="hover" class="stat-card">
          <div class="stat-label">冷却中</div>
          <div class="stat-value">{{ summary.cooling }}</div>
        </el-card>
        <el-card shadow="hover" class="stat-card">
          <div class="stat-label">已售数量</div>
          <div class="stat-value">{{ summary.sold }}</div>
        </el-card>
        <el-card shadow="hover" class="stat-card">
          <div class="stat-label">总利润</div>
          <div class="stat-value" :class="{ 'profit-up': summary.totalProfit >= 0, 'profit-down': summary.totalProfit < 0 }">
            {{ summary.totalProfit.toFixed(2) }}
          </div>
        </el-card>
      </div>

      <div class="filters">
        <div class="filter-item search">
          <label>名称搜索</label>
          <el-input v-model="filters.search" placeholder="例如：加利尔AR | 凤凰冥灯" clearable @clear="fetchItems" @keyup.enter="fetchItems" />
        </div>

        <div class="filter-item">
          <label>状态</label>
          <el-select v-model="filters.status" placeholder="全部" clearable @change="fetchItems">
            <el-option v-for="option in meta.status_options" :key="option.value || 'all'" :label="option.label" :value="option.value" />
          </el-select>
        </div>

        <div class="filter-item">
          <label>类型</label>
          <el-select v-model="filters.category" placeholder="全部" clearable @change="fetchItems">
            <el-option v-for="option in meta.category_options" :key="option" :label="option" :value="option" />
          </el-select>
        </div>

        <div class="filter-item date">
          <label>购买时间筛选（MonthPicker）</label>
          <el-date-picker
            v-model="filters.month"
            type="month"
            placeholder="选择月份"
            value-format="YYYY-MM"
            @change="onMonthChange"
          />
          <div class="range">
            <el-date-picker v-model="filters.start_date" type="date" value-format="YYYY-MM-DD" placeholder="开始时间" />
            <span>至</span>
            <el-date-picker v-model="filters.end_date" type="date" value-format="YYYY-MM-DD" placeholder="结束时间" />
          </div>
        </div>

        <div class="filter-item date">
          <label>卖出时间筛选（MonthPicker）</label>
          <el-date-picker
            v-model="filters.sold_month"
            type="month"
            placeholder="选择月份"
            value-format="YYYY-MM"
            @change="onSoldMonthChange"
          />
          <div class="range">
            <el-date-picker v-model="filters.sold_start_date" type="date" value-format="YYYY-MM-DD" placeholder="卖出开始时间" />
            <span>至</span>
            <el-date-picker v-model="filters.sold_end_date" type="date" value-format="YYYY-MM-DD" placeholder="卖出结束时间" />
          </div>
        </div>

        <div class="filter-actions">
          <el-button type="primary" @click="fetchItems">筛选</el-button>
          <el-button @click="resetFilters">重置</el-button>
        </div>
      </div>

      <el-table
        :data="items"
        :loading="loading"
        border
        stripe
        class="table inventory-table"
        :header-cell-style="{ textAlign: 'center' }"
        empty-text="暂无饰品数据，点击右上角新增饰品开始管理"
      >
        <el-table-column label="图片" width="94">
          <template #default="{ row }">
            <img :src="row.image_url" :alt="row.name" class="thumb" referrerpolicy="no-referrer" @error="fallbackImage" />
          </template>
        </el-table-column>
        <el-table-column label="名称" min-width="180">
          <template #default="{ row }">
            <div class="item-name">{{ row.name }}</div>
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
            <el-input-number
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
        <el-table-column prop="current_price" label="当前价" width="100" align="center" header-align="center">
          <template #default="{ row }">
            {{ Number(row.current_price || 0).toFixed(2) }}
          </template>
        </el-table-column>
        <el-table-column label="卖出价" width="135">
          <template #default="{ row }">
            <el-input-number
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
        <el-table-column prop="profit" label="利润" width="90" align="center" header-align="center">
          <template #default="{ row }">
            <span :class="{ 'profit-up': Number(row.profit || 0) >= 0, 'profit-down': Number(row.profit || 0) < 0 }">
              {{ Number(row.profit || 0).toFixed(2) }}
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="profit_percent" label="利润率%" width="90" align="center" header-align="center">
          <template #default="{ row }">
            <span :class="{ 'profit-up': Number(row.profit_percent || 0) >= 0, 'profit-down': Number(row.profit_percent || 0) < 0 }">
              {{ Number(row.profit_percent || 0).toFixed(2) }}%
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="sold_time_display" label="出售时间" width="160" />
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
        <el-table-column label="操作" width="180" fixed="right">
          <template #default="{ row }">
            <el-space>
              <el-button size="small" @click="openEditDialog(row)">编辑</el-button>
              <el-button size="small" @click="onClone(row)">复制</el-button>
              <el-button size="small" type="danger" @click="onDelete(row)">删除</el-button>
            </el-space>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="680px" destroy-on-close>
      <el-form label-position="top">
        <el-row :gutter="12">
          <el-col :span="12"><el-form-item label="名称"><el-input v-model="form.name" /></el-form-item></el-col>
          <el-col :span="12"><el-form-item label="类型"><el-select v-model="form.category"><el-option v-for="c in meta.category_options" :key="c" :label="c" :value="c" /></el-select></el-form-item></el-col>
          <el-col :span="12"><el-form-item label="SteamDT ID"><el-input v-model="form.steamdt_id" /></el-form-item></el-col>
          <el-col :span="24"><el-form-item label="图片 URL"><el-input v-model="form.image_url" /></el-form-item></el-col>
          <el-col :span="12"><el-form-item label="买入价"><el-input-number v-model="form.buy_price" :min="0" :step="1" :controls="false" controls-position="right" /></el-form-item></el-col>
          <el-col :span="12"><el-form-item label="购买时间"><el-date-picker v-model="form.buy_time" type="datetime" value-format="YYYY-MM-DD HH:mm:ss" /></el-form-item></el-col>
          <el-col v-if="isEditing" :span="12">
            <el-form-item label="出售时间">
              <el-date-picker
                v-model="form.sold_time"
                type="datetime"
                value-format="YYYY-MM-DD HH:mm:ss"
                :disabled="editRowStatus !== 'sold'"
                :placeholder="editRowStatus === 'sold' ? '未出售可留空' : '仅已售饰品可编辑'"
              />
            </el-form-item>
          </el-col>
          <el-col :span="24"><el-form-item label="备注"><el-input v-model="form.note" type="textarea" :rows="3" /></el-form-item></el-col>
        </el-row>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="onSubmitForm">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>
