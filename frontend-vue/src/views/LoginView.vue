<script setup>
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { login } from '../services/auth'

const router = useRouter()
const loading = ref(false)
const form = reactive({
  username: 'user',
  password: '123456',
})

async function onSubmit() {
  loading.value = true
  try {
    await login(form)
    ElMessage.success('登录成功')
    router.push('/items')
  } catch (error) {
    ElMessage.error(error?.response?.data?.detail || '登录失败')
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="login-page">
    <el-card class="login-card">
      <template #header>
        <div class="login-title">CS 饰品管理工具（Vue 版）</div>
        <div class="login-sub">输入账号后进入库存管理页面</div>
      </template>
      <el-form label-position="top" @submit.prevent="onSubmit">
        <el-form-item label="用户名">
          <el-input v-model="form.username" autocomplete="username" />
        </el-form-item>
        <el-form-item label="密码">
          <el-input v-model="form.password" type="password" show-password autocomplete="current-password" />
        </el-form-item>
        <el-button :loading="loading" type="primary" class="full" @click="onSubmit">登录</el-button>
      </el-form>
    </el-card>
  </div>
</template>
