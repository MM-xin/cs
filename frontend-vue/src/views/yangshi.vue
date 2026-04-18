<template>
  <div class="table-container">
    <div class="table-header">
      <h3>商品定价管理 (模拟分页数据)</h3>
      <span class="tip">💡 双击售价或库存进行修改</span>
    </div>

    <div class="custom-table">
      <!-- 表头 -->
      <div class="thead">
        <div class="tr">
          <div class="th" style="flex: 2">商品名称</div>
          <div class="th">原价</div>
          <div class="th highlight">当前售价 (可改)</div>
          <div class="th highlight">库存 (可改)</div>
          <div class="th">更新时间</div>
        </div>
      </div>

      <!-- 表体 -->
      <div class="tbody">
        <div v-for="(item, index) in productList" :key="item.id" class="tr">
          <div class="td" style="flex: 2; font-weight: 500;">{{ item.name }}</div>
          <div class="td gray">¥{{ item.originalPrice.toFixed(2) }}</div>

          <!-- 售价修改列 -->
          <div class="td price-cell" @dblclick="setEdit(item.id, 'price')">
            <template v-if="editState.id === item.id && editState.field === 'price'">
              <input
                v-model.number="item.price"
                v-focus
                type="number"
                class="edit-input price-input"
                @blur="saveChange(item)"
                @keyup.enter="saveChange(item)"
              />
            </template>
            <span v-else class="editable-text price">¥{{ item.price.toFixed(2) }}</span>
          </div>

          <!-- 库存修改列 -->
          <div class="td" @dblclick="setEdit(item.id, 'stock')">
            <template v-if="editState.id === item.id && editState.field === 'stock'">
              <input
                v-model.number="item.stock"
                v-focus
                type="number"
                class="edit-input stock-input"
                @blur="saveChange(item)"
                @keyup.enter="saveChange(item)"
              />
            </template>
            <span v-else class="editable-text">{{ item.stock }}</span>
          </div>

          <div class="td gray" style="font-size: 12px;">{{ item.updateTime }}</div>
        </div>
      </div>
    </div>

    <!-- 模拟分页 -->
    <div class="pagination">
      <span>共 5 条数据</span>
      <div class="btns">
        <button disabled>上一页</button>
        <button class="active">1</button>
        <button disabled>下一页</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive } from 'vue'

// 模拟分页接口返回的 5 条数据
const productList = ref([
  { id: 101, name: '极速固态硬盘 1TB', originalPrice: 599, price: 499.00, stock: 120, updateTime: '2024-03-20' },
  { id: 102, name: '机械键盘 (红轴) 87键', originalPrice: 299, price: 258.50, stock: 45, updateTime: '2024-03-21' },
  { id: 103, name: '4K 显示器 27寸', originalPrice: 1899, price: 1699.00, stock: 12, updateTime: '2024-03-18' },
  { id: 104, name: '无线人体工学鼠标', originalPrice: 159, price: 129.00, stock: 300, updateTime: '2024-03-22' },
  { id: 105, name: '氮化镓充电头 65W', originalPrice: 99, price: 79.00, stock: 88, updateTime: '2024-03-15' },
])

// 编辑状态管理
const editState = reactive({
  id: null,
  field: null // 'price' 或 'stock'
})

const setEdit = (id, field) => {
  editState.id = id
  editState.field = field
}

const saveChange = (item) => {
  console.log('正在提交给后端(Python):', { id: item.id, [editState.field]: item[editState.field] })
  editState.id = null
  editState.field = null
}

const vFocus = { mounted: (el) => el.focus() }
</script>

<style scoped>
.table-container { padding: 20px; background: #fff; border-radius: 8px; box-shadow: 0 2px 12px rgba(0,0,0,0.1); max-width: 900px; margin: 20px auto; }
.table-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px; }
.tip { font-size: 13px; color: #909399; }

.custom-table { width: 100%; border: 1px solid #ebeef5; border-radius: 4px; overflow: hidden; }
.tr { display: flex; align-items: center; border-bottom: 1px solid #ebeef5; transition: background 0.2s; }
.tbody .tr:hover { background-color: #f5f7fa; }
.th, .td { padding: 12px 15px; flex: 1; text-align: left; font-size: 14px; color: #606266; }
.thead { background: #f8f9fb; font-weight: bold; color: #333; }
.highlight { color: #409eff; }
.gray { color: #999; }

/* 编辑样式核心 */
.price-cell { position: relative; }
.editable-text { cursor: pointer; padding: 4px 8px; border-radius: 4px; border: 1px solid transparent; }
.editable-text:hover { background: #ecf5ff; border-color: #d9ecff; color: #409eff; }
.price { font-weight: bold; color: #f56c6c; }

.edit-input {
  width: 100%; padding: 4px 8px; border: 1px solid #409eff;
  border-radius: 4px; outline: none; box-shadow: 0 0 5px rgba(64,158,255,0.2);
  font-family: inherit; font-size: 14px;
}
.price-input { color: #f56c6c; font-weight: bold; }

/* 分页 */
.pagination { margin-top: 20px; display: flex; justify-content: space-between; align-items: center; color: #606266; font-size: 14px; }
.btns button { margin-left: 5px; padding: 5px 12px; border: 1px solid #dcdfe6; background: #fff; cursor: pointer; border-radius: 4px; }
.btns button.active { background: #409eff; color: #fff; border-color: #409eff; }
</style>

<style scoped>
.style-saas .tr {
  margin-bottom: 8px;
  border: 1px solid transparent;
  border-radius: 8px;
}
.style-saas .tr:hover {
  background: #fafafa;
  border-color: #e8e8e8;
}
.style-saas .editable-text {
  color: #1890ff; /* 蓝色链接感，暗示可点 */
  text-decoration: underline dashed #adc6ff;
  text-underline-offset: 4px;
}
.style-saas .edit-input {
  border: 2px solid #1890ff;
  border-radius: 6px;
  box-shadow: 0 0 8px rgba(24,144,255,0.2);
}
</style>

