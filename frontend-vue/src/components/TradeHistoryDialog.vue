<script setup>
import { computed } from 'vue'

const props = defineProps({
  modelValue: { type: Boolean, required: true },
  title: { type: String, default: '交易流水' },
  trades: { type: Array, default: () => [] },
  loading: { type: Boolean, default: false },
})

const emit = defineEmits(['update:modelValue'])

const visible = computed({
  get: () => props.modelValue,
  set: (value) => emit('update:modelValue', value),
})

const totals = computed(() => {
  let buy = 0
  let sell = 0
  let fee = 0
  for (const t of props.trades) {
    if (t.trade_type === 'buy') buy += Number(t.amount || 0)
    if (t.trade_type === 'sell' || t.trade_type === 'withdraw') sell += Number(t.amount || 0)
    fee += Number(t.fee_amount || 0)
  }
  return {
    buy: buy.toFixed(2),
    sell: sell.toFixed(2),
    fee: fee.toFixed(2),
    net: (sell - buy - fee).toFixed(2),
  }
})
</script>

<template>
  <el-dialog v-model="visible" :title="title" width="820px" destroy-on-close>
    <div class="trade-summary">
      <span>买入合计：<b>{{ totals.buy }}</b></span>
      <span>卖出/撤回合计：<b>{{ totals.sell }}</b></span>
      <span>手续费合计：<b>{{ totals.fee }}</b></span>
      <span>
        净收益：
        <b :class="{ 'profit-up': Number(totals.net) >= 0, 'profit-down': Number(totals.net) < 0 }">
          {{ totals.net }}
        </b>
      </span>
    </div>
    <el-table :data="trades" v-loading="loading" size="small" max-height="360" empty-text="暂无交易记录">
      <el-table-column prop="trade_time_display" label="时间" min-width="160" />
      <el-table-column prop="trade_type_label" label="类型" width="90" align="center" />
      <el-table-column prop="amount" label="金额" width="100" align="center">
        <template #default="{ row }">{{ Number(row.amount || 0).toFixed(2) }}</template>
      </el-table-column>
      <el-table-column prop="fee_amount" label="手续费" width="100" align="center">
        <template #default="{ row }">{{ Number(row.fee_amount || 0).toFixed(2) }}</template>
      </el-table-column>
      <el-table-column prop="net_amount" label="净额" width="100" align="center">
        <template #default="{ row }">{{ Number(row.net_amount || 0).toFixed(2) }}</template>
      </el-table-column>
      <el-table-column prop="note" label="备注" min-width="180" show-overflow-tooltip />
    </el-table>
    <template #footer>
      <el-button @click="visible = false">关闭</el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.trade-summary {
  display: flex;
  gap: 20px;
  padding: 8px 12px;
  margin-bottom: 10px;
  background: #f5f8ff;
  border: 1px solid #d9e7ff;
  border-radius: 6px;
  font-size: 13px;
  flex-wrap: wrap;
}
.trade-summary b {
  color: #1f2d3d;
  margin-left: 4px;
}
.profit-up {
  color: #e02828;
}
.profit-down {
  color: #13a34b;
}
</style>
