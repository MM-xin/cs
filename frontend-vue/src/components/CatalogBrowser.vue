<script setup>
import { onMounted, reactive, ref } from 'vue'
import { debounce } from 'lodash-es'
import { ElMessage } from 'element-plus'
import { getCatalogStats, searchCatalog, syncCatalog } from '../services/catalog'

const loading = ref(false)
const syncing = ref(false)
const items = ref([])
const total = ref(0)
const state = reactive({
  q: '',
  page: 1,
  size: 20,
})
const stats = ref({ total: 0, last_sync_at: null })

const pageSizes = [10, 20, 50, 100, 200]

async function fetchList() {
  loading.value = true
  try {
    const data = await searchCatalog({ q: state.q, page: state.page, size: state.size })
    items.value = data.items || []
    total.value = data.total || 0
  } catch {
    /* interceptor */
  } finally {
    loading.value = false
  }
}

async function fetchStats() {
  try {
    stats.value = await getCatalogStats()
  } catch {
    /* interceptor */
  }
}

const debouncedFetch = debounce(() => {
  state.page = 1
  fetchList()
}, 300)

function onSearchInput() {
  debouncedFetch()
}

function onPageChange(page) {
  state.page = page
  fetchList()
}

function onSizeChange(size) {
  state.size = size
  state.page = 1
  fetchList()
}

async function onSync() {
  syncing.value = true
  try {
    const r = await syncCatalog()
    ElMessage.success(`同步完成：新增 ${r.inserted}，更新 ${r.updated}`)
    await Promise.all([fetchStats(), fetchList()])
  } catch {
    /* interceptor */
  } finally {
    syncing.value = false
  }
}

async function copyText(text) {
  try {
    await navigator.clipboard.writeText(text)
    ElMessage.success('已复制')
  } catch {
    ElMessage.warning('复制失败')
  }
}

onMounted(() => {
  fetchStats()
  fetchList()
})
</script>

<template>
  <div class="catalog-browser">
    <div class="catalog-toolbar">
      <el-input
        v-model="state.q"
        placeholder="输入中文 / 英文 / marketHashName 搜索"
        clearable
        size="default"
        class="catalog-search"
        @input="onSearchInput"
        @clear="onSearchInput"
      />
      <div class="catalog-stats">
        <span>总数 {{ stats.total || 0 }}</span>
        <span v-if="stats.last_sync_at" class="muted">上次同步 {{ stats.last_sync_at }}</span>
        <el-button size="small" :loading="syncing" @click="onSync">立即同步</el-button>
      </div>
    </div>

    <el-table
      :data="items"
      v-loading="loading"
      border
      stripe
      class="catalog-table"
      :header-cell-style="{ textAlign: 'center' }"
      empty-text="没有匹配的饰品"
    >
      <el-table-column label="中文名" min-width="260">
        <template #default="{ row }">
          <div class="cell-primary">{{ row.name_cn }}</div>
          <div class="cell-sub">{{ row.base_name_cn }}</div>
        </template>
      </el-table-column>
      <el-table-column label="英文名 (marketHashName)" min-width="320">
        <template #default="{ row }">
          <div class="cell-primary">{{ row.market_hash_name }}</div>
          <div class="cell-sub">{{ row.base_name_en }}</div>
        </template>
      </el-table-column>
      <el-table-column prop="wear" label="磨损" width="110" align="center" header-align="center">
        <template #default="{ row }">
          <el-tag v-if="row.wear" size="small" effect="plain">{{ row.wear }}</el-tag>
          <span v-else class="muted">-</span>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="180" align="center" header-align="center">
        <template #default="{ row }">
          <el-space>
            <el-button size="small" @click="copyText(row.name_cn)">复制中文</el-button>
            <el-button size="small" @click="copyText(row.market_hash_name)">复制英文</el-button>
          </el-space>
        </template>
      </el-table-column>
    </el-table>

    <div class="catalog-pager">
      <el-pagination
        :current-page="state.page"
        :page-size="state.size"
        :page-sizes="pageSizes"
        :total="total"
        layout="total, sizes, prev, pager, next, jumper"
        background
        @current-change="onPageChange"
        @size-change="onSizeChange"
      />
    </div>
  </div>
</template>

<style scoped>
.catalog-browser {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.catalog-toolbar {
  display: flex;
  gap: 16px;
  align-items: center;
  flex-wrap: wrap;
}
.catalog-search {
  flex: 1 1 320px;
  max-width: 520px;
}
.catalog-stats {
  display: flex;
  gap: 12px;
  align-items: center;
  font-size: 13px;
  color: #3d4658;
}
.catalog-stats .muted {
  color: #9099ad;
}
.catalog-table {
  width: 100%;
}
.cell-primary {
  font-weight: 500;
  color: #1f2937;
  word-break: break-word;
}
.cell-sub {
  font-size: 12px;
  color: #8a94a6;
  margin-top: 2px;
}
.muted {
  color: #9099ad;
}
.catalog-pager {
  display: flex;
  justify-content: flex-end;
}
</style>
