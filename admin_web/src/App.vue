<template>
  <router-view />
</template>

<script setup>
import { useUserStore } from '@/stores/user'

// 应用启动兜底：路由守卫已负责恢复菜单（async beforeEach + restore），
// 此处仅处理极端时序（守卫未走到恢复逻辑时的二次保险）
const user = useUserStore()
const storedToken = sessionStorage.getItem('token')
if (storedToken && !user.token) {
  user.token = storedToken
}
</script>
