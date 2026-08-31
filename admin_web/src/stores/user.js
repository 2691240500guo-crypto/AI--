import { defineStore } from 'pinia'
import { login, getMyMenus } from '@/api/auth'
import { registerDynamicRoutes } from '@/router'
import router from '@/router'

export const useUserStore = defineStore('user', {
  state: () => ({
    // 硬刷新后从 sessionStorage 同步恢复 token，避免守卫误判"未登录"
    token: sessionStorage.getItem('token') || '',
    user: null,
    menus: [],
    perms: []
  }),
  actions: {
    async login(form) {
      const res = await login(form)
      this.token = res.data.access_token
      sessionStorage.setItem('token', this.token)
      sessionStorage.setItem('refresh_token', res.data.refresh_token)
      this.user = res.data.user
      await this.loadMenus()
    },
    async loadMenus() {
      const res = await getMyMenus()
      this.menus = res.data.menus
      this.perms = res.data.perms
      // 动态注册路由：菜单里新挂的页面无需改 router 即可访问
      registerDynamicRoutes(res.data.menus)
    },
    hasPerm(perm) {
      if (!perm) return true
      return this.perms.includes(perm)
    },
    async logout() {
      this.token = ''
      this.user = null
      // 只清自己相关的 token，不要 clear() 全清（会清掉无关数据）
      sessionStorage.removeItem('token')
      sessionStorage.removeItem('refresh_token')
      router.push('/login')
    }
  }
})