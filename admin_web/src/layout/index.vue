<script setup>
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { useUserStore } from '@/stores/user'
import { ElMessageBox } from 'element-plus'

const router = useRouter()
const user = useUserStore()

// 一级菜单 = parent_id==0；二级挂在 children
const menus = computed(() => user.menus.filter(m => m.type !== 3 && m.status !== 0))
const bySort = (a, b) => (a.sort - b.sort) || (a.id - b.id)
const roots = computed(() => menus.value.filter(m => m.parent_id === 0).sort(bySort))
const childrenOf = (pid) => menus.value.filter(m => m.parent_id === pid).sort(bySort)

async function onLogout() {
  await ElMessageBox.confirm('确定退出登录？', '提示', { type: 'warning' })
  user.logout()
}
</script>

<template>
  <el-container class="layout">
    <el-aside width="220px" class="aside">
      <div class="logo">AI 人才平台</div>
      <el-menu :default-active="$route.path" router background-color="#001529" text-color="#a6adb4"
        active-text-color="#fff" class="aside-menu">
        <template v-for="root in roots" :key="root.id">
          <el-sub-menu v-if="childrenOf(root.id).length" :index="String(root.path || root.id)">
            <template #title>{{ root.title }}</template>
            <el-menu-item v-for="child in childrenOf(root.id)" :key="child.id" :index="child.path">
              {{ child.title }}
            </el-menu-item>
          </el-sub-menu>
          <el-menu-item v-else :index="root.path || '/'">{{ root.title }}</el-menu-item>
        </template>
      </el-menu>
    </el-aside>
    <el-container>
      <el-header class="header">
        <div class="title">{{ $route.meta.title || '' }}</div>
        <el-dropdown @command="(c) => (c === 'logout' ? onLogout() : '')">
          <span class="user">{{ user.user?.nickname || user.user?.username || '未登录' }}</span>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item command="logout">退出登录</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </el-header>
      <el-main class="main">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<style>
.layout { height: 100vh; }
.layout > .el-container { min-width: 0; }
.aside { background: #001529; display: flex; flex-direction: column; }
.logo { height: 56px; line-height: 56px; text-align: center; color: #fff; font-weight: 700; flex-shrink: 0; }
/* el-menu 占满侧边栏剩余高度，否则子项可能不可见 */
.aside-menu { flex: 1; overflow-y: auto; border-right: 0 !important; }
.header { background: #fff; border-bottom: 1px solid #eef1f5; display: flex; align-items: center; justify-content: space-between; }
.user { cursor: pointer; color: #1f2937; }
.main { min-width: 0; background: #f5f7fa; }
@media (max-width: 600px) {
  .aside { width: 96px !important; }
  .logo { padding: 0 6px; font-size: 13px; white-space: nowrap; }
  .aside-menu .el-sub-menu__title,
  .aside-menu .el-menu-item { min-width: 96px; height: 48px; padding: 0 12px !important; font-size: 13px; line-height: 48px; }
  .aside-menu .el-sub-menu .el-menu-item { padding-left: 18px !important; }
  .header { height: 50px; padding: 0 12px; gap: 8px; }
  .title { font-size: 15px; }
  .user { font-size: 12px; }
  .main { padding: 12px; }
}
</style>
