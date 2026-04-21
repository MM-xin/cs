<script setup>
import { computed, reactive, watch } from 'vue'
import dayjs from 'dayjs'
import { ElMessage } from 'element-plus'
import { createItem, updateItem } from '../services/items'
import { searchCatalog } from '../services/catalog'

const props = defineProps({
  modelValue: { type: Boolean, required: true },
  editingId: { type: [Number, String, null], default: null },
  editRowStatus: { type: String, default: '' },
  categoryOptions: { type: Array, default: () => [] },
  initialData: { type: Object, default: () => ({}) },
})

const emit = defineEmits(['update:modelValue', 'saved'])

const visible = computed({
  get: () => props.modelValue,
  set: (value) => emit('update:modelValue', value),
})

const isEditing = computed(() => props.editingId !== null && props.editingId !== undefined)
const title = computed(() => (isEditing.value ? '编辑饰品' : '新增饰品'))

const form = reactive({
  name: '',
  market_hash_name: '',
  wear: '',
  category: '其他',
  steamdt_id: '',
  image_url: '',
  buy_price: '',
  buy_time: '',
  sold_time: '',
  note: '',
})

watch(
  () => [props.modelValue, props.initialData],
  ([open]) => {
    if (!open) return
    const data = props.initialData || {}
    Object.assign(form, {
      name: data.name || '',
      market_hash_name: data.market_hash_name || '',
      wear: data.wear || '',
      category: data.category || '其他',
      steamdt_id: data.steamdt_id || '',
      image_url: data.image_url || '',
      buy_price: data.buy_price ?? '',
      buy_time: data.buy_time || dayjs().format('YYYY-MM-DD HH:mm:ss'),
      sold_time: data.sold_time || '',
      note: data.note || '',
    })
  },
  { immediate: true, deep: true },
)

async function fetchNameSuggestions(query, cb) {
  const keyword = (query || '').trim()
  if (!keyword) {
    cb([])
    return
  }
  try {
    const data = await searchCatalog({ q: keyword, page: 1, size: 20 })
    const items = (data.items || []).map((it) => ({
      value: it.name_cn,
      market_hash_name: it.market_hash_name,
      name_cn: it.name_cn,
      base_name_cn: it.base_name_cn,
      base_name_en: it.base_name_en,
      wear: it.wear,
    }))
    cb(items)
  } catch {
    cb([])
  }
}

function onNameInput(value) {
  if (value !== form.name) {
    form.market_hash_name = ''
    form.wear = ''
  }
}

function onNameSelect(item) {
  if (!item) return
  form.name = item.name_cn || item.value || form.name
  form.market_hash_name = item.market_hash_name || ''
  form.wear = item.wear || ''
}

async function onSubmit() {
  if (isEditing.value && form.sold_time && props.editRowStatus !== 'sold') {
    ElMessage.warning('未出售的饰品不能编辑出售时间')
    return
  }
  try {
    if (isEditing.value) {
      await updateItem(props.editingId, form)
      ElMessage.success('饰品已更新')
    } else {
      await createItem(form)
      ElMessage.success('饰品已新增')
    }
    visible.value = false
    emit('saved')
  } catch {
    /* toast handled by axios interceptor */
  }
}
</script>

<template>
  <el-dialog v-model="visible" :title="title" width="680px" destroy-on-close>
    <el-form label-position="top">
      <el-row :gutter="12">
        <el-col :span="12">
          <el-form-item label="名称">
            <el-autocomplete
              v-model="form.name"
              :fetch-suggestions="fetchNameSuggestions"
              :trigger-on-focus="false"
              :debounce="300"
              placeholder="输入中文/英文，选择饰品即可自动绑定"
              clearable
              value-key="value"
              class="name-autocomplete"
              popper-class="name-autocomplete-pop"
              @select="onNameSelect"
              @input="onNameInput"
            >
              <template #default="{ item }">
                <div class="suggest-row">
                  <div class="suggest-primary">
                    <span class="suggest-name">{{ item.name_cn }}</span>
                    <el-tag v-if="item.wear" size="small" type="info" effect="plain" class="suggest-wear">{{ item.wear }}</el-tag>
                  </div>
                  <div class="suggest-sub">{{ item.market_hash_name }}</div>
                </div>
              </template>
            </el-autocomplete>
            <div v-if="form.market_hash_name" class="form-hint">
              已绑定: <span class="hint-mhn">{{ form.market_hash_name }}</span>
            </div>
          </el-form-item>
        </el-col>
        <el-col :span="12"><el-form-item label="类型"><el-select v-model="form.category"><el-option v-for="c in categoryOptions" :key="c" :label="c" :value="c" /></el-select></el-form-item></el-col>
        <el-col :span="12"><el-form-item label="SteamDT ID"><el-input v-model="form.steamdt_id" /></el-form-item></el-col>
        <el-col :span="24"><el-form-item label="图片 URL"><el-input v-model="form.image_url" /></el-form-item></el-col>
        <el-col :span="12"><el-form-item label="买入价"><el-input-number v-model="form.buy_price" :min="0" :step="1" :controls="false" /></el-form-item></el-col>
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
      <el-button @click="visible = false">取消</el-button>
      <el-button type="primary" @click="onSubmit">保存</el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.name-autocomplete {
  width: 100%;
}
.form-hint {
  margin-top: 4px;
  font-size: 12px;
  color: #909399;
  line-height: 1.4;
}
.hint-mhn {
  color: #3d7df6;
  word-break: break-all;
}
</style>
<style>
.name-autocomplete-pop .suggest-row {
  display: flex;
  flex-direction: column;
  padding: 2px 0;
  line-height: 1.25;
}
.name-autocomplete-pop .suggest-primary {
  display: flex;
  align-items: center;
  gap: 6px;
}
.name-autocomplete-pop .suggest-name {
  color: #1f2937;
  font-weight: 500;
}
.name-autocomplete-pop .suggest-wear {
  flex-shrink: 0;
}
.name-autocomplete-pop .suggest-sub {
  color: #8a94a6;
  font-size: 12px;
  margin-top: 2px;
}
.name-autocomplete-pop .el-autocomplete-suggestion__list li {
  height: auto !important;
  line-height: 1.3 !important;
  padding: 8px 12px !important;
}
</style>
