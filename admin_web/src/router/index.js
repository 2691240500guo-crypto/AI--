import { createRouter, createWebHistory } from 'vue-router'
import { useUserStore } from '@/stores/user'

// ===== 静态基础路由（登录、主布局、看板）=====
const routes = [
  { path: '/login', name: 'login', component: () => import('@/views/login/index.vue') },
  {
    path: '/',
    name: 'root',   // 必须有 name，addRoute('root', child) 才能注册到根布局下
    component: () => import('@/layout/index.vue'),
    redirect: '/dashboard',
    children: [
      { path: 'dashboard', name: 'dashboard', component: () => import('@/views/dashboard.vue'), meta: { title: '数据看板' } },
      // 岗位匹配域（M 域）静态路由：sys_menu 未种子 matching 菜单项前，用静态路由保证页面可直接访问
      // meta.static=true 保护：registerDynamicRoutes 清理旧动态路由时跳过，避免登录后被 removeRoute 导致 404
      { path: 'matching/position', name: 'matching-position', component: () => import('@/views/matching/Position.vue'), meta: { title: '岗位管理', static: true } },
      { path: 'matching/result', name: 'matching-result', component: () => import('@/views/matching/Result.vue'), meta: { title: '匹配结果', static: true } },
      // 智能测评-在线答题（A 域独立答题页，不在菜单里，静态注册保证可直接访问）
      { path: 'assessment/answer/:id', name: 'assessment-answer', component: () => import('@/views/assessment/answer.vue'), meta: { title: '在线答题', static: true } },
      // 人才档案域（T 域，hy 分支合并）：详情/新增/编辑/简历解析/治理/RAG 静态路由
      { path: 'talent/detail/:id', name: 'talent-detail', component: () => import('@/views/talent/detail.vue'), meta: { title: '人才档案详情', static: true } },
      { path: 'talent/new', name: 'talent-new', component: () => import('@/views/talent/edit.vue'), meta: { title: '新增人才档案', static: true } },
      { path: 'talent/edit/:id', name: 'talent-edit', component: () => import('@/views/talent/edit.vue'), meta: { title: '编辑人才档案', static: true } },
      { path: 'talent/upload', name: 'talent-upload', component: () => import('@/views/talent/ResumeImport.vue'), meta: { title: '简历智能解析', static: true } },
      { path: 'talent/governance', name: 'talent-governance', component: () => import('@/views/talent/Governance.vue'), meta: { title: '数据治理', static: true } },
      { path: 'talent/rag', name: 'talent-rag', component: () => import('@/views/talent/RagQA.vue'), meta: { title: 'RAG 研判', static: true } },
      // 在线学习（hy 分支合并）：视频/课程/进度
      { path: 'course/videos', name: 'course-videos', component: () => import('@/views/course/VideoManage.vue'), meta: { title: '视频管理', static: true } },
      { path: 'course/list', name: 'course-list', component: () => import('@/views/course/CourseList.vue'), meta: { title: '课程列表', static: true } },
      { path: 'course/progress', name: 'course-progress', component: () => import('@/views/course/CourseProgress.vue'), meta: { title: '学习进度', static: true } }
    ]
  },
  // 兜底 404（放最后）
  { path: '/:pathMatch(.*)*', name: 'not-found', component: () => import('@/views/not-found.vue') }
]

const router = createRouter({ history: createWebHistory(), routes })

// ===== 动态路由：按 /menus/mine 下发的菜单注册 =====
// 菜单表 component 字段约定：相对 src/views 的路径，如 system/User -> views/system/User.vue
// 使用 src 绝对路径可确保 Vite 在开发和生产构建中生成同一份模块索引。
const viewModules = import.meta.glob('/src/views/**/*.vue')

function resolveComponent(component) {
  if (!component) return null
  // 菜单 component 可能带 views/、src/ 或 .vue 后缀，统一后再匹配文件索引。
  const norm = component
    .replace(/^@?\/?src\/views\//i, '')
    .replace(/^views\//i, '')
    .replace(/^\/+/, '')
    .replace(/\.vue$/, '')
    .toLowerCase()
  const hit = Object.keys(viewModules).find((key) => {
    const normalizedKey = key.replace(/\\/g, '/').toLowerCase()
    return normalizedKey.endsWith(`/views/${norm}.vue`)
  })
  // 命中返回懒加载组件；未命中返回 null（页面缺失时渲染空，避免构建期动态 import 报错）
  return hit ? viewModules[hit] : null
}

export function registerDynamicRoutes(menus) {
  const parent = router.options.routes.find((r) => r.path === '/')
  // 清理旧动态路由时跳过 meta.static=true 的静态路由（如岗位匹配域页面），避免登录后被误删
  const children = (parent?.children || []).filter((c) => c.name !== 'dashboard' && !c.meta?.static)
  // 清理旧动态路由（登录态切换时避免重复注册）
  for (const c of children) {
    if (router.hasRoute(c.name)) router.removeRoute(c.name)
  }
  const leaf = menus.filter((m) => m.type === 2 && m.path && m.status !== 0).sort((a, b) => (a.sort - b.sort) || (a.id - b.id))
  const folders = menus.filter((m) => m.type === 1)           // 目录
  for (const m of leaf) {
    const fullPath = m.path.startsWith('/') ? m.path : `/${m.path}`
    const child = {
      path: fullPath.replace(/^\//, ''),
      name: `dynamic-${m.id}`,
      component: resolveComponent(m.component) || (() => import('@/views/not-found.vue')),
      meta: { title: m.title }
    }
    if (router.hasRoute(child.name)) router.removeRoute(child.name)
    // 用根路由的 name（'root'）作为父路由名；component 为 null 会导致后续跳转崩，兜底为 404 组件
    router.addRoute('root', child)
  }
  return folders.length > 0
}

// 异步守卫：刷新时动态路由尚未注册，必须先恢复菜单（注册 addRoute）再放行，
// 否则 URL 停留在动态页面（如 /system/user）会匹配到 404 兜底路由
router.beforeEach(async (to) => {
  const user = useUserStore()
  // 硬刷新后从 sessionStorage 同步 token，避免被误判为"未登录"跳 /login
  const storedToken = sessionStorage.getItem('token')
  if (storedToken && !user.token) {
    user.token = storedToken
  }
  if (to.path !== '/login' && !user.token) return '/login'
  if (to.path === '/login' && user.token) return '/'
  // 关键：token 在但 menus 为空（刷新后）→ 先恢复菜单+动态路由，避免刷新到动态页 404
  if (user.token && user.menus.length === 0) {
    try {
      await user.restore()
    } catch (e) {
      console.warn('[router] restore failed:', e?.message)
      if (to.name === 'not-found') return to.fullPath
    }
  }
  if (to.meta.title) document.title = `${to.meta.title} · AI 人才平台`
  return true
})

export default router
