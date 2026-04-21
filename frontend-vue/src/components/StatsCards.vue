<script setup>
import { computed } from 'vue'

const props = defineProps({
  items: { type: Array, required: true },
})

const summary = computed(() => {
  const total = props.items.length
  const inStockItems = props.items.filter(
    (x) => x.status_label === '在库' || x.status_label === '冷却中',
  )
  const soldItems = props.items.filter((x) => x.status_label === '已售')
  const inStock = inStockItems.length
  const sold = soldItems.length
  const cooling = props.items.filter((x) => x.status_label === '冷却中').length
  const inStockProfit = inStockItems.reduce((acc, item) => acc + Number(item.profit || 0), 0)
  const soldProfit = soldItems.reduce((acc, item) => acc + Number(item.profit || 0), 0)
  return { total, inStock, sold, cooling, inStockProfit, soldProfit }
})
</script>

<template>
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
      <div class="stat-label">在库浮盈合计</div>
      <div
        class="stat-value"
        :class="{ 'profit-up': summary.inStockProfit >= 0, 'profit-down': summary.inStockProfit < 0 }"
      >
        {{ summary.inStockProfit.toFixed(2) }}
      </div>
    </el-card>
    <el-card shadow="hover" class="stat-card">
      <div class="stat-label">已售利润合计</div>
      <div
        class="stat-value"
        :class="{ 'profit-up': summary.soldProfit >= 0, 'profit-down': summary.soldProfit < 0 }"
      >
        {{ summary.soldProfit.toFixed(2) }}
      </div>
    </el-card>
  </div>
</template>
