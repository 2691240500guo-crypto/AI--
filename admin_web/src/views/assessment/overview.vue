<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { Collection, DataAnalysis, Document, Promotion } from '@element-plus/icons-vue'
import { useRouter } from 'vue-router'
import { getStatistics } from '@/api/assessment'
import { useUserStore } from '@/stores/user'

const router = useRouter()
const user = useUserStore()
const loading = ref(false)
const errorMessage = ref('')
const stats = reactive({ total_results: 0, completed_results: 0, average_score: 0, pass_rate: 0 })
const actions = computed(() => [
  { title: '题库与题目', description: '维护题库、题目与批量导入', path: '/assessment/question-bank', perm: 'assessment:manage', icon: Collection },
  { title: '组卷管理', description: '手动、随机或按能力模型组卷', path: '/assessment/paper', perm: 'assessment:paper', icon: Document },
  { title: '发起测评', description: '选择试卷、人员与测评时段', path: '/assessment/launch', perm: 'assessment:launch', icon: Promotion },
  { title: '成绩统计', description: '查看成绩、报告与培训联动', path: '/assessment/results', perm: 'assessment:stat', icon: DataAnalysis },
].filter((action) => user.hasPerm(action.perm)))

async function load() {
  loading.value = true
  errorMessage.value = ''
  try {
    Object.assign(stats, (await getStatistics({})).data || {})
  } catch (error) {
    errorMessage.value = error?.message || '测评概览加载失败，请重试'
  } finally { loading.value = false }
}

onMounted(load)
</script>

<template>
  <div v-loading="loading" class="overview-page">
    <div v-if="errorMessage" class="error-state">
      <el-alert :title="errorMessage" type="error" show-icon :closable="false" />
      <el-button type="primary" plain :loading="loading" @click="load">重试</el-button>
    </div>
    <el-row :gutter="16">
      <el-col :xs="12" :sm="6"><el-card shadow="never"><el-statistic title="测评总数" :value="stats.total_results" suffix="场" /></el-card></el-col>
      <el-col :xs="12" :sm="6"><el-card shadow="never"><el-statistic title="已完成" :value="stats.completed_results" suffix="场" /></el-card></el-col>
      <el-col :xs="12" :sm="6"><el-card shadow="never"><el-statistic title="平均分" :value="Number(stats.average_score || 0)" :precision="2" suffix="分" /></el-card></el-col>
      <el-col :xs="12" :sm="6"><el-card shadow="never"><el-statistic title="合格率" :value="Number(stats.pass_rate || 0) * 100" :precision="1" suffix="%" /></el-card></el-col>
    </el-row>
    <section class="quick-section" aria-labelledby="quick-title">
      <div class="section-heading">
        <h2 id="quick-title">快速操作</h2>
        <span>常用管理入口</span>
      </div>
      <div class="quick-grid">
        <button v-for="action in actions" :key="action.path" type="button" class="quick-action" @click="router.push(action.path)">
          <span class="action-icon"><el-icon :size="28"><component :is="action.icon" /></el-icon></span>
          <span class="action-copy"><strong>{{ action.title }}</strong><small>{{ action.description }}</small></span>
          <span class="action-arrow" aria-hidden="true">›</span>
        </button>
      </div>
    </section>
    <el-card shadow="never" class="guide-card">
      <template #header>C 智能测评管理闭环</template>
      <p>管理端负责题库、组卷、发起、统计、能力报告和培训联动，在线作答由用户端承载。</p>
      <p>管理流程：维护题库与题目 → 创建试卷 → 发起测评 → 用户端完成作答 → 查看成绩与报告。</p>
      <el-alert title="报告通过 LangGraph 调用硅基流动，失败时自动使用本地确定性算法；培训计划或消息投递失败时保留可重试联动记录。" type="info" :closable="false" />
    </el-card>
  </div>
</template>

<style scoped>
.overview-page { min-height: 100%; }
.error-state { display: flex; align-items: center; gap: 12px; margin-bottom: 16px; }
.error-state :deep(.el-alert) { flex: 1; }
.quick-section { margin-top: 16px; padding: 20px; background: #fff; border: 1px solid #e4e7ed; border-radius: 6px; }
.section-heading { display: flex; align-items: baseline; justify-content: space-between; gap: 12px; margin-bottom: 16px; }
.section-heading h2 { margin: 0; color: #172033; font-size: 18px; font-weight: 600; }
.section-heading span { color: #9098a8; font-size: 13px; }
.quick-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; }
.quick-action { min-width: 0; min-height: 104px; display: grid; grid-template-columns: 42px minmax(0, 1fr) 18px; align-items: center; gap: 12px; padding: 18px; border: 1px solid #dfe4ec; border-radius: 6px; background: #fff; color: #172033; cursor: pointer; text-align: left; transition: border-color .2s, box-shadow .2s, transform .2s; }
.quick-action:hover, .quick-action:focus-visible { border-color: #409eff; box-shadow: 0 6px 18px rgba(31, 41, 55, .08); outline: none; transform: translateY(-1px); }
.action-icon { width: 42px; height: 42px; display: inline-flex; align-items: center; justify-content: center; border-radius: 6px; background: #ecf5ff; color: #337ecc; }
.action-copy { min-width: 0; display: flex; flex-direction: column; gap: 7px; }
.action-copy strong { font-size: 15px; font-weight: 600; }
.action-copy small { color: #7d8799; font-size: 12px; line-height: 1.5; white-space: normal; }
.action-arrow { color: #a4adba; font-size: 24px; line-height: 1; }
.guide-card { margin-top: 16px; }
.guide-card p { color: #5d6678; line-height: 1.8; }
@media (max-width: 1100px) { .quick-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
@media (max-width: 560px) { .error-state { align-items: stretch; flex-direction: column; }.quick-section { padding: 16px; }.quick-grid { grid-template-columns: 1fr; }.quick-action { min-height: 88px; } }
</style>
