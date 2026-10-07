<!-- hq新增内容 - 人才档案批次1 [detail.vue]
     通过静态路由 /talent/detail/:id 访问，列表页 `router.push` 跳过来。
     后端：GET /api/v1/talent/{id} -->
<script setup>
import { onMounted, ref, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { getTalent, getTalentReport, getTalentVectors, getTalentProfile } from '@/api/talent'
import { getTalentGraph, syncAllKg } from '@/api/kg'
import EChart from '@/components/EChart.vue'

// M1 知识图谱：人才画像关系网（Neo4j 1 跳子图）
const kgData = ref(null)
const kgLoading = ref(false)
const kgSyncing = ref(false)
const kgError = ref('')
const KG_CATS = ['人才', '技能', '画像标签', '项目', '证书']
const KG_COLORS = { '人才': '#f5455c', '技能': '#00b8a9', '画像标签': '#4d7cfe', '项目': '#ff9f43', '证书': '#27ae60' }

const kgEmpty = computed(() =>
  !kgLoading.value && (!kgData.value || !kgData.value.meta?.synced || !(kgData.value.nodes || []).length)
)

const kgOption = computed(() => {
  const g = kgData.value
  if (!g) return {}
  const nodes = (g.nodes || []).map((n) => {
    const idx = KG_CATS.indexOf(n.category)
    return {
      id: n.id,
      name: n.name,
      category: idx >= 0 ? idx : 0,
      categoryName: n.category || '',
      symbolSize: n.nodeType === 'Talent' ? 46 : 22,
      itemStyle: { color: KG_COLORS[n.category] || '#909399' },
    }
  })
  const links = (g.edges || []).map((e) => ({ source: e.source, target: e.target }))
  return {
    tooltip: {
      formatter: (p) => `<b>${p.data?.name || ''}</b><br/>类型：${p.data?.categoryName || ''}`,
    },
    legend: { data: KG_CATS, bottom: 0, textStyle: { fontSize: 11 } },
    series: [{
      type: 'graph',
      layout: 'force',
      roam: true,
      draggable: true,
      data: nodes,
      links,
      categories: KG_CATS.map((c) => ({ name: c })),
      force: { repulsion: 220, edgeLength: [50, 130], gravity: 0.08 },
      label: { show: true, position: 'right', fontSize: 10, color: '#374151' },
      lineStyle: { color: '#c0c4cc', width: 1, curveness: 0.05, opacity: 0.7 },
      emphasis: { focus: 'adjacency', lineStyle: { width: 3 } },
    }],
  }
})

async function loadKg() {
  kgLoading.value = true
  kgError.value = ''
  try {
    const res = await getTalentGraph(route.params.id)
    kgData.value = res.data || null
  } catch (e) {
    kgData.value = null
    kgError.value = (e && e.message) || '图谱加载失败'
  } finally {
    kgLoading.value = false
  }
}

// 「同步图谱」：先全量同步（Neo4j 一键灌入存量人才），再刷新本页关系网
async function syncAndReload() {
  kgSyncing.value = true
  try {
    await syncAllKg()
    ElMessage.success('图谱同步完成')
    await loadKg()
  } catch (e) {
    ElMessage.error('图谱同步失败：' + ((e && e.message) || 'Neo4j 可能未启动'))
  } finally {
    kgSyncing.value = false
  }
}

const route = useRoute()
const router = useRouter()
const loading = ref(false)
const data = ref(null)
const activeCollapse = ref(['summary'])  // 默认展开「个人简介」

// 入口来源：SPA 内优先走浏览器历史回退（确保回退路径已注册过，不会 404），兜底首页。
function goBack() {
  if (typeof window !== 'undefined' && window.history && window.history.length > 1) {
    router.back()
    return
  }
  router.push('/home')
}

// 袁文武 2026-09-02：AI 解析报告 + 四维向量画像（详情页展示）
const report = ref(null)
const reportLoading = ref(false)
const vectors = ref([])
const vectorsLoading = ref(false)

// 袁文武 2026-09-03：AI 数字画像（8 维度标签分组）
const profileData = ref(null)
const profileLoading = ref(false)
// 标签维度映射（与后端 SEED_TAGS 对应）
const TAG_DIM_LABELS = {
  skill: '专业技能', level: '能力层级', exp: '从业经验', quality: '综合素质',
  position: '适配岗位', potential: '潜力评级', specialty: '职业特长', industry: '行业经验',
}
const TAG_DIM_COLORS = {
  skill: 'success', level: 'warning', exp: 'primary', quality: 'info',
  position: 'danger', potential: 'warning', specialty: 'success', industry: 'primary',
}
const hasProfileData = computed(() => {
  const p = profileData.value
  return p && p.tags_by_dim && Object.keys(p.tags_by_dim).length > 0
})
const DIM_COLOR = { skill: 'success', exp: 'primary', quality: 'warning' }

// 袁文武 2026-09-02：综合评分颜色映射
function scoreColor(score) {
  if (score >= 90) return '#16a34a'
  if (score >= 80) return '#22c55e'
  if (score >= 70) return '#f59e0b'
  if (score >= 60) return '#f97316'
  return '#ef4444'
}

async function loadReport() {
  reportLoading.value = true
  try {
    const res = await getTalentReport(route.params.id)
    report.value = res.data
  } catch (_) { report.value = null } finally {
    reportLoading.value = false
  }
}

async function loadVectors() {
  vectorsLoading.value = true
  try {
    const res = await getTalentVectors(route.params.id)
    vectors.value = res.data || []
  } catch (_) { vectors.value = [] } finally {
    vectorsLoading.value = false
  }
}

// 袁文武 2026-09-03：加载画像概览
async function loadProfile() {
  profileLoading.value = true
  try {
    const res = await getTalentProfile(route.params.id)
    profileData.value = res.data
  } catch (_) { profileData.value = null } finally {
    profileLoading.value = false
  }
}

async function load() {
  loading.value = true
  try {
    const res = await getTalent(route.params.id)
    data.value = res.data
  } catch (e) {
    ElMessage.error('人才档案加载失败：' + (e.message || ''))
    router.replace('/talent/list')
  } finally {
    loading.value = false
  }
  // 并行加载画像、AI 报告、向量画像与知识图谱（失败不影响详情页展示）
  loadProfile()
  loadReport()
  loadVectors()
  loadKg()
}

function fmtDate(s) {
  if (!s) return '—'
  const d = new Date(s)
  return isNaN(d.getTime()) ? s : d.toLocaleString('zh-CN', { hour12: false })
}
const genderLabel = (g) => ({ 0: '未知', 1: '男', 2: '女', '男': '男', '女': '女' }[g] || '未知')
const sourceLabel = (s) => ({ manual: '人工录入', import: '批量导入', agent_parsed: 'AI 智能解析', text: '文本解析', excel: 'Excel导入', pdf: 'PDF解析', docx: 'Word解析', image: '图片解析' }[s] || s || '—')

onMounted(load)
</script>

<template>
  <el-card v-loading="loading">
    <template #header>
      <div class="head">
        <el-page-header @back="goBack" :title="'返回列表'">
          <template #content>
            <span class="title">{{ data?.name || '加载中...' }}</span>
            <el-tag v-if="data" :type="data.status === 1 ? 'success' : 'info'" size="small" style="margin-left:8px">
              {{ data.status === 1 ? '在档' : '失效' }}
            </el-tag>
            <el-tag v-if="data" type="primary" size="small" style="margin-left:8px">
              {{ sourceLabel(data.resume_source) }}
            </el-tag>
          </template>
        </el-page-header>
      </div>
    </template>

    <template v-if="data">
      <!-- 基础信息 -->
      <el-descriptions title="基础信息" :column="3" border>
        <el-descriptions-item label="姓名">{{ data.name }}</el-descriptions-item>
        <el-descriptions-item label="性别">{{ genderLabel(data.gender) }}</el-descriptions-item>
        <el-descriptions-item label="出生年">{{ data.birth_year || '—' }}</el-descriptions-item>
        <el-descriptions-item label="手机">{{ data.phone_masked || data.phone || '—' }}</el-descriptions-item>
        <el-descriptions-item label="邮箱">{{ data.email || '—' }}</el-descriptions-item>
        <el-descriptions-item label="学历">{{ data.highest_education || '—' }}</el-descriptions-item>
        <el-descriptions-item label="现职称">{{ data.current_title || '—' }}</el-descriptions-item>
        <el-descriptions-item label="当前公司">{{ data.current_company || '—' }}</el-descriptions-item>
        <el-descriptions-item label="工作年限">{{ data.years_experience ?? '—' }} 年</el-descriptions-item>
      </el-descriptions>

      <!-- 个人简介 -->
      <div class="block">
        <div class="block-title">个人简介</div>
        <div class="block-body" :class="{ empty: !data.summary }">
          {{ data.summary || '（尚未填写简介）' }}
        </div>
      </div>

      <!-- 原始简历（折叠） -->
      <el-collapse v-model="activeCollapse" class="block">
        <el-collapse-item title="原始简历 / 解析前文本" name="raw">
          <pre class="raw">{{ data.resume_text || '（无原文，可能为纯人工录入）' }}</pre>
        </el-collapse-item>
      </el-collapse>

      <!-- 元信息 -->
      <el-descriptions title="元信息" :column="3" border style="margin-top:16px">
        <el-descriptions-item label="档案 ID">#{{ data.id }}</el-descriptions-item>
        <el-descriptions-item label="来源">{{ sourceLabel(data.resume_source) }}</el-descriptions-item>
        <el-descriptions-item label="创建时间">{{ fmtDate(data.created_at) }}</el-descriptions-item>
        <el-descriptions-item label="更新时间" :span="3">{{ fmtDate(data.updated_at) }}</el-descriptions-item>
      </el-descriptions>

      <!-- 袁文武 2026-09-03：AI 数字画像（8 维度百级标签 + 向量画像） -->
      <el-divider content-position="left">AI 数字画像</el-divider>
      <el-card shadow="never" class="profile-card" v-loading="reportLoading">
        <template #header>
          <div class="profile-head">
            <div class="profile-head-left">
              <span class="profile-title">🧬 智能画像</span>
              <el-tag v-if="profileData?.tag_count" type="success" size="small" effect="dark">
                {{ profileData.tag_count }} 个标签
              </el-tag>
              <el-tag v-if="profileData?.generate_mode === 'llm'" type="primary" size="small">
                AI 生成
              </el-tag>
              <el-tag v-else-if="profileData?.generate_mode === 'rule'" type="info" size="small">
                规则推导
              </el-tag>
              <el-tag v-else type="warning" size="small">
                快速画像
              </el-tag>
            </div>
            <div v-if="profileData?.profile_updated_at" class="profile-update">
              更新于 {{ profileData.profile_updated_at }}
            </div>
          </div>
        </template>
        <div v-if="!hasProfileData" class="report-empty">
          暂无画像数据，可在编辑页点击「生成 AI 画像」
        </div>
        <template v-else>
          <!-- 8 维度标签分组 -->
          <div class="tag-dim-grid">
            <div v-for="(dim, dimKey) in TAG_DIM_LABELS" :key="dimKey" class="tag-dim-card">
              <div class="tag-dim-head">
                <el-tag :type="TAG_DIM_COLORS[dimKey] || ''" size="small" effect="dark">
                  {{ dim }}
                </el-tag>
                <span class="tag-dim-count">{{ (profileData.tags_by_dim?.[dimKey] || []).length }}</span>
              </div>
              <div class="tag-dim-body">
                <template v-if="(profileData.tags_by_dim?.[dimKey] || []).length">
                  <el-tag
                    v-for="(tag, i) in profileData.tags_by_dim[dimKey]"
                    :key="i"
                    :type="TAG_DIM_COLORS[dimKey] || 'info'"
                    effect="plain"
                    size="small"
                    class="dim-tag"
                  >
                    {{ tag }}
                  </el-tag>
                </template>
                <span v-else class="empty">—</span>
              </div>
            </div>
          </div>

          <!-- hq+ 2026-09-03：已绑定标签池（8 维度归类是按 tal_tag.category，custom 类不进 8 维度→ 看不到）
               后端 get_profile 路由已返回 ai_tags 字段（含全部 manual/AI 标签），这里完整展示。 -->
          <div v-if="(profileData.ai_tags || []).length" class="bound-tags" style="margin-top:14px">
            <div class="report-title">
              已绑定标签（{{ profileData.ai_tags.length }} 个·含人工/AI 全部打标）
            </div>
            <div class="bound-tags-body">
              <el-tag
                v-for="(tag, i) in profileData.ai_tags"
                :key="i"
                size="small"
                effect="plain"
                class="dim-tag"
              >
                {{ tag }}
              </el-tag>
            </div>
          </div>

          <!-- 画像摘要 -->
          <el-row :gutter="20" style="margin-top:16px" v-if="report">
            <el-col :span="8">
              <div class="report-title">能力等级</div>
              <div v-if="report.ability_level" class="ability-box">
                <el-tag type="warning" size="large" effect="dark">{{ report.ability_level }}</el-tag>
              </div>
              <span v-else class="empty">—</span>
            </el-col>
            <el-col :span="8">
              <div class="report-title">综合评分</div>
              <div v-if="report.composite_score != null" class="score-box">
                <span class="score-num">{{ report.composite_score }}</span>
                <span class="score-max">/100</span>
                <el-progress
                  :percentage="report.composite_score"
                  :show-text="false"
                  :stroke-width="8"
                  :color="scoreColor(report.composite_score)"
                  style="margin-top:6px"
                />
              </div>
              <span v-else class="empty">—</span>
            </el-col>
            <el-col :span="8">
              <div class="report-title">潜力评级</div>
              <div v-if="report.potential || profileData.potential_level" class="ability-box">
                <el-tag type="warning" size="large" effect="dark">
                  {{ report.potential || profileData.potential_level }}
                </el-tag>
              </div>
              <span v-else class="empty">—</span>
            </el-col>
            <el-col :span="12" style="margin-top:14px">
              <div class="report-title">核心优势</div>
              <ul class="bullet">
                <li v-for="(s, i) in report.highlights" :key="i">{{ s }}</li>
                <li v-if="!report.highlights?.length" class="empty">—</li>
              </ul>
            </el-col>
            <el-col :span="12" style="margin-top:14px">
              <div class="report-title">待提升方向</div>
              <ul class="bullet">
                <li v-for="(s, i) in report.shortcomings" :key="i">{{ s }}</li>
                <li v-if="!report.shortcomings?.length" class="empty">—</li>
              </ul>
            </el-col>
            <el-col :span="24" style="margin-top:14px" v-if="report.summary_report">
              <div class="report-title">综合评估</div>
              <pre class="summary">{{ report.summary_report }}</pre>
            </el-col>
          </el-row>
        </template>
      </el-card>

      <!-- 袁文武 2026-09-02：三维向量画像（Milvus） -->
      <el-divider content-position="left">三维向量画像（Milvus）</el-divider>
      <el-card shadow="never" class="report" v-loading="vectorsLoading">
        <template #header>
          <div class="report-head">
            <span>技能 / 经验 / 素质 三个维度的全局向量</span>
            <span style="font-size:12px;color:#9ca3af">画像生成时自动写入 Milvus，支持语义检索</span>
          </div>
        </template>
        <div v-if="!vectors.length" class="report-empty">
          尚未生成向量画像，可在编辑页触发「生成 AI 画像」
        </div>
        <el-row v-else :gutter="20">
          <el-col v-for="v in vectors" :key="v.dim" :span="8">
            <el-card shadow="never" class="vec-card">
              <template #header>
                <div class="vec-head">
                  <el-tag :type="DIM_COLOR[v.dim] || ''" size="small">{{ v.label }}</el-tag>
                  <span :class="v.has_vector ? 'vec-ok' : 'vec-no'">
                    {{ v.has_vector ? '已入库' : '未生成' }}
                  </span>
                </div>
              </template>
              <div class="vec-text">{{ v.text || '—' }}</div>
            </el-card>
          </el-col>
        </el-row>
      </el-card>

      <!-- M1 知识图谱：人才画像关系网（Neo4j 1 跳子图） -->
      <el-divider content-position="left">知识图谱关系网（Neo4j）</el-divider>
      <el-card shadow="never" class="kg-card" v-loading="kgLoading">
        <template #header>
          <div class="report-head">
            <span>人才 ↔ 技能 / 画像标签 / 项目 / 证书</span>
            <el-button size="small" :loading="kgSyncing" @click="syncAndReload">
              {{ kgSyncing ? '同步中...' : '同步图谱' }}
            </el-button>
          </div>
        </template>
        <div v-if="kgEmpty" class="report-empty">
          {{ kgError || '暂无图谱数据：该人才尚未打标/录入项目，或图谱未同步。可先「生成 AI 画像」再点右上角「同步图谱」。' }}
        </div>
        <EChart v-else :option="kgOption" height="440px" />
      </el-card>
    </template>
  </el-card>
</template>

<style scoped>
.head { display: flex; align-items: center; }
.title { font-size: 18px; font-weight: 600; }
.block { margin-top: 18px; }
.block-title { font-weight: 600; color: #374151; margin-bottom: 8px; }
.block-body {
  background: #f9fafb;
  border: 1px solid #eef1f5;
  border-radius: 6px;
  padding: 12px 14px;
  line-height: 1.7;
  white-space: pre-wrap;
  word-break: break-word;
}
.block-body.empty { color: #9ca3af; font-style: italic; }
.raw {
  background: #1f2937;
  color: #e5e7eb;
  padding: 12px 14px;
  border-radius: 6px;
  max-height: 360px;
  overflow: auto;
  white-space: pre-wrap;
  word-break: break-word;
  font-size: 13px;
  line-height: 1.6;
  margin: 0;
}

/* 袁文武 2026-09-02：AI 报告 + 向量画像样式（与编辑页保持一致） */
.report { background: #fcfcfd; margin-top: 8px; }
.kg-card { background: #fcfcfd; margin-top: 8px; }
.report-head { display: flex; align-items: center; justify-content: space-between; }
.report-title { font-weight: 600; color: #374151; margin-bottom: 6px; font-size: 13px; }
.report-empty { color: #9ca3af; font-size: 13px; padding: 8px 0; }

/* 袁文武 2026-09-03：AI 数字画像卡片 */
.profile-card { background: linear-gradient(135deg, #f0fdf4 0%, #ecfeff 100%); margin-top: 8px; border: 1px solid #86efac; }
.profile-head { display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 8px; }
.profile-head-left { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.profile-title { font-size: 15px; font-weight: 600; color: #065f46; }
.profile-update { font-size: 12px; color: #6b7280; }

/* 8 维度标签网格 */
.tag-dim-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; }
@media (max-width: 900px) { .tag-dim-grid { grid-template-columns: repeat(2, 1fr); } }
.tag-dim-card {
  background: rgba(255,255,255,0.85);
  border-radius: 8px;
  padding: 10px 12px;
  border: 1px solid rgba(16,185,129,0.2);
}
.tag-dim-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 8px; }
.tag-dim-count { font-size: 12px; color: #6b7280; font-weight: 500; }
.tag-dim-body { display: flex; flex-wrap: wrap; gap: 4px; min-height: 28px; }
.dim-tag { margin-bottom: 2px; }
.tag-dim-body .empty { color: #9ca3af; font-size: 12px; }

.bullet { padding-left: 18px; margin: 0; color: #4b5563; line-height: 1.7; }
.bullet li.empty { list-style: none; color: #9ca3af; }
.summary {
  background: #fffbe6;
  border: 1px solid #fde58e;
  border-radius: 6px;
  padding: 12px 14px;
  white-space: pre-wrap;
  word-break: break-word;
  font-family: inherit;
  font-size: 13px;
  line-height: 1.7;
  color: #5a4a00;
  margin: 0;
}
.chip-grid { display: flex; flex-wrap: wrap; gap: 6px; }
.chip-grid .empty { color: #9ca3af; font-size: 12px; }
.vec-card { background: #fcfcfd; margin-bottom: 8px; }
.vec-head { display: flex; align-items: center; justify-content: space-between; }
.vec-ok  { color: #16a34a; font-size: 12px; }
.vec-no  { color: #9ca3af; font-size: 12px; }
.vec-text {
  font-size: 12px; color: #4b5563; line-height: 1.7;
  max-height: 120px; overflow: auto;
  word-break: break-word; white-space: pre-wrap;
}
/* 袁文武 2026-09-02：三大板块样式 */
.ability-box { display: flex; align-items: center; }
.score-box { display: flex; flex-direction: column; }
.score-num {
  font-size: 28px; font-weight: 700; color: #111827;
  line-height: 1;
}
.score-max { font-size: 14px; color: #9ca3af; margin-left: 2px; }
.exp-text {
  font-size: 13px; color: #374151; line-height: 1.7;
  max-height: 80px; overflow: auto; word-break: break-word;
}
</style>
