<script setup>
import { reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useUserStore } from '@/stores/user'

const router = useRouter()
const route = useRoute()
const user = useUserStore()
const formRef = ref()
const form = reactive({ username: '', password: '' })
const loading = ref(false)
const rules = {
  username: [{ required: true, message: '请输入账号', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }]
}

// 站内路径才允许登录后回跳（防开放重定向）；默认回首页
function safeRedirect() {
  const r = route.query.redirect
  return typeof r === 'string' && r.startsWith('/') && !r.startsWith('//') ? r : '/'
}

async function onSubmit() {
  await formRef.value.validate()
  loading.value = true
  try {
    await user.login(form)
    ElMessage.success('登录成功')
    router.push(safeRedirect())
  } catch (e) {
    // 任何阶段失败都明确提示，避免"点了没反应"（之前 try 无 catch，错误被吞）
    console.error('[login] failed:', e)
    ElMessage.error(e?.message || '登录失败，请稍后重试')
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="login-wrap">
    <el-card class="login-card">
      <h2 class="title">AI 人才平台 · 管理端</h2>
      <el-form ref="formRef" :model="form" :rules="rules" label-position="top">
        <el-form-item label="账号" prop="username">
          <el-input v-model="form.username" placeholder="admin" size="large" />
        </el-form-item>
        <el-form-item label="密码" prop="password">
          <el-input v-model="form.password" type="password" show-password placeholder="密码" size="large" @keyup.enter="onSubmit" />
        </el-form-item>
        <el-button type="primary" size="large" style="width:100%" :loading="loading" @click="onSubmit">登 录</el-button>
      </el-form>
      <p class="tip">默认账号 admin / admin123</p>
    </el-card>
  </div>
</template>

<style scoped>
.login-wrap { min-height: 100vh; display: flex; align-items: center; justify-content: center;
  background: linear-gradient(135deg, #1e3a8a, #2563eb); padding: 16px; }
.login-card { width: 380px; border-radius: 14px; padding: 8px 6px; }
.title { text-align: center; margin: 0 0 20px; color: #1f2937; }
.tip { text-align: center; color: #9ca3af; font-size: 12px; margin-top: 14px; }
</style>