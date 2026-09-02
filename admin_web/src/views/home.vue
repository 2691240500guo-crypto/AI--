<template>
  <div class="home">
    <!-- 欢迎条 -->
    <el-card shadow="never" class="welcome">
      <div class="welcome-row">
        <div>
          <div class="hello">您好，{{ nickname }} 👋</div>
          <div class="sub">{{ today }} · AI 数字化人才平台综合概览</div>
        </div>
        <el-button type="primary" :loading="loading" @click="load">刷新</el-button>
      </div>
    </el-card>

    <!-- 统计卡 -->
    <el-row :gutter="16" class="kpis">
      <el-col v-for="k in kpis" :key="k.key" :span="kpiSpan">
        <el-card shadow="hover">
          <div class="kpi-label">{{ k.label }}</div>
          <div class="kpi-value" :style="{ color: k.color }">{{ k.value }}</div>
          <div class="kpi-sub">{{ k.sub }}</div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 快捷入口（仅显示有权限的入口） -->
    <el-card v-if="visibleEntries.length" shadow="never" class="section">
      <template #header>快捷入口</template>
      <div class="entries">
        <div class="entry" v-for="e in visibleEntries" :key="e.path" @click="$router.push(e.path)">
          <div class="entry-icon">{{ e.icon }}</div>
          <div class="entry-name">{{ e.name }}</div>
        </div>
      </div>
    </el-card>

    <!-- 图表（需 analytics:list） -->
    <el-row v-if="showCharts" :gutter="16" class="charts">
      <el-col :span="12">
        <el-card shadow="never">
          <template #header>学历分布</template>
          <EChart :option="degreeOption" />
        </el-card>
      </el-col>
      <el-col :span="12">
        <el-card shadow="never">
          <template #header>人才趋势</template>
          <EChart :option="trendOption" />
        </el-card>
      </el-col>
    </el-row>

    <!-- 最近动态 -->
    <el-row :gutter="16" class="recent">
      <el-col v-if="showRecentAssess" :span="12">
        <el-card shadow="never">
          <template #header>最近测评</template>
          <el-table :data="recentResults" size="small" v-loading="loading">
            <el-table-column prop="talent_name" label="人才" width="90" />
            <el-table-column prop="paper_title" label="试卷" show-overflow-tooltip />
            <el-table-column prop="score" label="得分" width="70" />
            <el-table-column prop="status" label="状态" width="70">
              <template #default="{ row }">{{ statusText(row.status) }}</template>
            </el-table-column>
          </el-table>
          <el-empty v-if="!recentResults.length" description="暂无测评记录" :image-size="60" />
        </el-card>
      </el-col>
      <el-col :span="showRecentAssess ? 12 : 24">
        <el-card shadow="never">
          <template #header>系统消息</template>
          <div v-for="m in recentMessages" :key="m.id" class="msg-item" @click="$router.push('/message')">
            <div class="msg-title">{{ m.title }}</div>
            <div class="msg-time">{{ (m.created_at || '').slice(0, 16) }}</div>
          </div>
          <el-empty v-if="!recentMessages.length" description="暂无消息" :image-size="60" />
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import { useUserStore } from '@/stores/user'
import EChart from '@/components/EChart.vue'
import http from '@/utils/request'
import { getOverview, getDistribution, getTrend } from '@/api/analytics'
import { listResults } from '@/api/assessment'
import { listPositions } from '@/api/matching'
import { listMyMessages, getUnreadCount } from '@/api/message'

const userStore = useUserStore()
const nickname = computed(() => userStore.user?.nickname || '管理员')
const today = new Date().toLocaleDateString('zh-CN', { year: 'numeric', month: 'long', day: 'numeric', weekday: 'long' })
const loading = ref(false)

const kpis = ref([])
const recentResults = ref([])
const recentMessages = ref([])
const degreeOption = ref({})
const trendOption = ref({})

// 按登录人权限码过滤首页可见内容（无权限码的 KPI/区块不渲染，也不请求接口，避免 403 弹错）
const can = (perm) => userStore.hasPerm(perm)

const showTalentKpi = can('analytics:list')  // 人才总数 + 测评合格率（都来自 overview）
const showAssessKpi = can('assessment:stat') // 测评完成数（statistics）
const showPosKpi = can('matching:*')         // 在招岗位
const showTrainKpi = can('training:list')    // 培训计划
const showMsgKpi = true                      // 未读消息（无权限码限制，所有登录用户可见）
const showCharts = can('analytics:list')     // 学历分布 + 人才趋势图
const showRecentAssess = can('assessment:stat') // 最近测评表

const entries = [
  { name: '人才档案', icon: '👥', path: '/talent', perm: 'talent:query' },
  { name: '智能测评', icon: '📝', path: '/assessment/overview', perm: 'assessment:list' },
  { name: '岗位匹配', icon: '🎯', path: '/matching/agent', perm: 'matching:*' },
  { name: '智能培训', icon: '🎓', path: '/training/plan', perm: 'training:list' },
  { name: '数据决策', icon: '📊', path: '/dashboard', perm: 'analytics:list' },
].filter(e => can(e.perm))
const visibleEntries = entries

// KPI 卡栅格：6 卡每行 6 个（span4），5 卡每行 5（span4 余一行），少卡时自适应铺满
const kpiSpan = computed(() => {
  const n = kpis.value.length
  if (n <= 0) return 4
  if (n >= 6) return 4
  return Math.max(4, Math.floor(24 / n))
})

function statusText(s) {
  return { 0: '未答', 1: '答题中', 2: '已交卷', 3: '已完成' }[s] || s
}

async function load() {
  loading.value = true
  try {
    // ---- 第一批：KPI 卡（按权限码逐项调用，缺权限的跳过不请求）----
    const calls = []
    // 人才总数 + 测评合格率：都来自 /analytics/overview（analytics:list）
    if (showTalentKpi) calls.push(getOverview().then(r => ({ k: 'overview', v: r.data || {} })))
    // 测评完成数：来自 /assessment/results/statistics（assessment:stat）
    if (showAssessKpi) calls.push(http.get('/assessment/results/statistics').then(r => ({ k: 'assess', v: r.data?.completed_results })))
    if (showPosKpi) calls.push(listPositions({ page: 1, page_size: 1 }).then(r => ({ k: 'pos', v: r.data?.total })))
    if (showTrainKpi) calls.push(http.get('/training/effects').then(r => ({ k: 'train', v: r.data?.total_plans })))
    if (showMsgKpi) calls.push(getUnreadCount().then(r => ({ k: 'msg', v: r?.data?.unread ?? r?.unread ?? r })))
    const results = await Promise.all(calls.map(p => p.catch(() => null)))
    const kpiMap = {}
    for (const r of results) if (r) kpiMap[r.k] = r
    const o = kpiMap.overview?.v || {}

    const kpiList = []
    if (showTalentKpi) kpiList.push({ key: 'talent', label: '人才总数', value: o.talent_total ?? '-', sub: '档案库', color: '#2563eb' })
    if (showAssessKpi) {
      kpiList.push({ key: 'assess', label: '测评完成', value: kpiMap.assess?.v ?? '-', sub: '已交卷/报告', color: '#16a34a' })
    }
    // 测评合格率来自 overview（需 analytics:list），与 talent 同源
    if (showTalentKpi) kpiList.push({ key: 'pass', label: '测评合格率', value: `${Math.round((o.assess_pass_rate || 0) * 100)}%`, sub: '≥60% 合格', color: '#f59e0b' })
    if (showPosKpi) kpiList.push({ key: 'pos', label: '在招岗位', value: kpiMap.pos?.v ?? '-', sub: '匹配中', color: '#7c3aed' })
    if (showTrainKpi) kpiList.push({ key: 'train', label: '培训计划', value: kpiMap.train?.v ?? '-', sub: '进行中', color: '#0d9488' })
    if (showMsgKpi) kpiList.push({ key: 'msg', label: '未读消息', value: kpiMap.msg?.v ?? '-', sub: '消息中心', color: '#e5533c' })
    kpis.value = kpiList

    // ---- 第二批：明细/图表（同样按权限码跳过）----
    const calls2 = []
    if (showRecentAssess) calls2.push(listResults({ page: 1, page_size: 5 }).then(r => ({ k: 'results', v: r.data?.items || [] })))
    calls2.push(listMyMessages({ page: 1, page_size: 5 }).then(r => ({ k: 'msgs', v: r.data?.items || r.data || [] })))
    if (showCharts) {
      calls2.push(getDistribution({ dim: 'education' }).then(r => ({ k: 'dist', v: r.data || [] })))
      calls2.push(getTrend().then(r => ({ k: 'trend', v: r.data || [] })))
    }
    const results2 = await Promise.all(calls2.map(p => p.catch(() => null)))
    const map2 = {}
    for (const r of results2) if (r) map2[r.k] = r

    if (showRecentAssess) {
      recentResults.value = (map2.results?.v || []).map(r => ({ ...r, talent_name: r.talent_name || r.talent_id }))
    }
    recentMessages.value = map2.msgs?.v || []

    if (showCharts) {
      const distData = map2.dist?.v || []
      degreeOption.value = {
        tooltip: { trigger: 'item' },
        legend: { bottom: 0, textStyle: { fontSize: 12 } },
        series: [{
          type: 'pie', radius: ['38%', '62%'], center: ['50%', '45%'],
          data: distData.map(i => ({ name: i.name || i.dimension, value: i.count || i.value || 0 })),
          label: { fontSize: 12 },
        }],
      }
      const tData = map2.trend?.v || []
      trendOption.value = {
        tooltip: { trigger: 'axis' },
        grid: { left: 40, right: 20, top: 30, bottom: 30 },
        xAxis: { type: 'category', data: tData.map(i => i.label || i.month || i.date) },
        yAxis: { type: 'value' },
        series: [{ type: 'line', smooth: true, data: tData.map(i => i.value || i.count || 0), areaStyle: { opacity: 0.15 } }],
      }
    }
  } catch (e) {
    /* 首页接口失败不阻塞 */
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.home { padding: 16px; }
.welcome { margin-bottom: 16px; }
.welcome-row { display: flex; justify-content: space-between; align-items: center; }
.hello { font-size: 20px; font-weight: 600; }
.sub { color: #909399; font-size: 13px; margin-top: 4px; }
.kpis { margin-bottom: 16px; }
.kpi-label { color: #909399; font-size: 13px; }
.kpi-value { font-size: 26px; font-weight: 700; margin: 6px 0 2px; }
.kpi-sub { color: #c0c4cc; font-size: 12px; }
.section { margin-bottom: 16px; }
.entries { display: flex; gap: 20px; flex-wrap: wrap; }
.entry { width: 96px; text-align: center; padding: 14px 0; border-radius: 10px; cursor: pointer; background: #f5f7fa; transition: all .2s; }
.entry:hover { background: #eaf0ff; transform: translateY(-2px); }
.entry-icon { font-size: 28px; }
.entry-name { margin-top: 8px; font-size: 14px; }
.charts { margin-bottom: 16px; }
.msg-item { display: flex; justify-content: space-between; padding: 8px 4px; border-bottom: 1px solid #f0f2f5; cursor: pointer; font-size: 14px; }
.msg-time { color: #c0c4cc; font-size: 12px; }
</style>
