<script setup>
import { computed } from 'vue'
import dayjs from 'dayjs'

const props = defineProps({
  modelValue: { type: Object, required: true },
  meta: { type: Object, required: true },
  showActionButton: { type: Boolean, default: true },
})

const emit = defineEmits(['update:modelValue', 'filter', 'reset', 'export'])

const filters = computed({
  get: () => props.modelValue,
  set: (value) => emit('update:modelValue', value),
})

function onMonthChange(value) {
  if (!value) {
    filters.value.start_date = ''
    filters.value.end_date = ''
  } else {
    const month = dayjs(value)
    filters.value.start_date = month.startOf('month').format('YYYY-MM-DD')
    filters.value.end_date = month.endOf('month').format('YYYY-MM-DD')
  }
  emit('filter')
}

function onSoldMonthChange(value) {
  if (!value) {
    filters.value.sold_start_date = ''
    filters.value.sold_end_date = ''
  } else {
    const month = dayjs(value)
    filters.value.sold_start_date = month.startOf('month').format('YYYY-MM-DD')
    filters.value.sold_end_date = month.endOf('month').format('YYYY-MM-DD')
  }
  emit('filter')
}
</script>

<template>
  <div class="filters">
    <div class="filter-item date">
      <label>购买时间筛选</label>
      <el-date-picker
        v-model="filters.month"
        type="month"
        placeholder="选择月份"
        value-format="YYYY-MM"
        @change="onMonthChange"
      />
      <div class="range">
        <el-date-picker v-model="filters.start_date" type="date" value-format="YYYY-MM-DD" placeholder="开始时间" @change="emit('filter')" />
        <span>至</span>
        <el-date-picker v-model="filters.end_date" type="date" value-format="YYYY-MM-DD" placeholder="结束时间" @change="emit('filter')" />
      </div>
    </div>

    <div class="filter-item date">
      <label>卖出时间筛选</label>
      <el-date-picker
        v-model="filters.sold_month"
        type="month"
        placeholder="选择月份"
        value-format="YYYY-MM"
        @change="onSoldMonthChange"
      />
      <div class="range">
        <el-date-picker v-model="filters.sold_start_date" type="date" value-format="YYYY-MM-DD" placeholder="卖出开始时间" @change="emit('filter')" />
        <span>至</span>
        <el-date-picker v-model="filters.sold_end_date" type="date" value-format="YYYY-MM-DD" placeholder="卖出结束时间" @change="emit('filter')" />
      </div>
    </div>

    <div class="filter-break"></div>

    <div class="filter-item search">
      <label>名称搜索</label>
      <el-input v-model="filters.search" placeholder="例如：加利尔AR | 凤凰冥灯" clearable @clear="emit('filter')" @keyup.enter="emit('filter')" />
    </div>

    <div class="filter-item">
      <label>状态</label>
      <el-select v-model="filters.status" placeholder="全部" clearable @change="emit('filter')">
        <el-option v-for="option in meta.status_options" :key="option.value || 'all'" :label="option.label" :value="option.value" />
      </el-select>
    </div>

    <div class="filter-item">
      <label>类型</label>
      <el-select v-model="filters.category" placeholder="全部" clearable @change="emit('filter')">
        <el-option v-for="option in meta.category_options" :key="option" :label="option" :value="option" />
      </el-select>
    </div>

    <div v-if="showActionButton" class="filter-actions">
      <el-button type="primary" @click="emit('filter')">筛选</el-button>
      <el-button @click="emit('reset')">重置</el-button>
      <el-button plain @click="emit('export')">导出 CSV</el-button>
    </div>
  </div>
</template>
