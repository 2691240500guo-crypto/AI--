<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { getAssessmentStats, listPapers } from '@/api/assessment'

const router = useRouter()
const loading = ref(false)
const stats = ref(null)
const papers = ref([])
const paperCount = ref(0)

const STATUS_MAP = { 0: '未作答', 1: '答题中', 2: '已交卷', 3: '已出报告' }
const STATUS_TYPE = { 0: 'info', 1: 'warning', 2: 'success', 3: 'success' }

async function load() {
  loading.value = true
  try {
    const [s, p] = await Promise.all([getAssessmentStats(), listPapers({ page_size: 1 })])
    stats.value = s.data
    paperCount.value = p.data.meta.total
  } finally { loading.value = false }
}

// 快捷操作
const actions = [
  { title: '题库与题目', desc: '维护题库与题目', path: '/assessment/question', icon: '📚', color: '#4f46e5' },
  { title: '组卷管理', desc: '手动/智能创建试卷', path: '/assessment/paper', icon: '📄', color: '#f59e0b' },
  { title: '发起测评', desc: '选择试卷和人才', path: '/assessment/launch', icon: '🚀', color: '#1d9e75' },
  { title: '成绩统计', desc: '查看成绩与报告', path: '/assessment/result', icon: '📊', color: '#e24b4a' },
]

onMounted(load)
</script>

<template>
  <div v-loading="loading">
    <!-- 统计卡片 -->
    <el-row :gutter="16" v-if="stats">
      <el-col :span="6"><el-card class="stat" shadow="hover"><div class="label">测评总数</div><div class="value">{{ stats.total }}</div></el-card></el-col>
      <el-col :span="6"><el-card class="stat" shadow="hover"><div class="label">已完成</div><div class="value">{{ stats.submitted }}</div></el-card></el-col>
      <el-col :span="6"><el-card class="stat" shadow="hover"><div class="label">平均分</div><div class="value">{{ stats.avg_score }}</div></el-card></el-col>
      <el-col :span="6"><el-card class="stat" shadow="hover"><div class="label">合格率</div><div class="value">{{ stats.pass_rate }}%</div></el-card></el-col>
    </el-row>

    <!-- 快捷操作 -->
    <el-card style="margin-top:16px" v-if="stats">
      <template #header>快速操作</template>
      <el-row :gutter="16">
        <el-col v-for="a in actions" :key="a.title" :span="6">
          <div class="action" :style="{ '--accent': a.color }" @click="router.push(a.path)">
            <div class="action-icon">{{ a.icon }}</div>
            <div class="action-title">{{ a.title }}</div>
            <div class="action-desc">{{ a.desc }}</div>
          </div>
        </el-col>
      </el-row>
    </el-card>

    <el-row :gutter="16" style="margin-top:16px" v-if="stats">
      <!-- 状态分布 -->
      <el-col :span="10">
        <el-card>
          <template #header>测评状态分布</template>
          <div v-for="(cnt, name) in stats.by_status" :key="name" class="bar-row">
            <span class="bar-name">{{ name }}</span>
            <div class="bar-track">
              <div class="bar-fill" :style="{ width: (cnt / (stats.total || 1) * 100) + '%' }"></div>
            </div>
            <span class="bar-val">{{ cnt }}</span>
          </div>
          <div style="margin-top:14px;color:#888;font-size:13px">
            试卷总数：<b>{{ paperCount }}</b> 张
          </div>
        </el-card>
      </el-col>

      <!-- 最近测评 -->
      <el-col :span="14">
        <el-card>
          <template #header>最近测评</template>
          <el-table :data="stats.recent" size="small" stripe>
            <el-table-column prop="id" label="ID" width="60" />
            <el-table-column prop="talent_id" label="人才ID" width="80" />
            <el-table-column prop="paper_id" label="试卷ID" width="80" />
            <el-table-column label="状态" width="90">
              <template #default="{ row }"><el-tag :type="STATUS_TYPE[row.status]" size="small">{{ STATUS_MAP[row.status] }}</el-tag></template>
            </el-table-column>
            <el-table-column prop="score" label="得分" width="70" />
            <el-table-column label="操作" width="90">
              <template #default="{ row }">
                <el-button link type="primary" size="small" @click="router.push(`/assessment/result`)">查看</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-col>
    </el-row>

    <!-- 闭环说明 -->
    <el-alert v-if="stats" type="info" :closable="false" style="margin-top:16px">
      <template #title>
        <div style="font-size:13px;line-height:1.8">
          管理端已接入 <b>题库 → 组卷 → 发起 → 在线答题 → 自动判分 → 能力报告 → 培训联动</b> 完整闭环。
          建议流程：先维护<b>题库与题目</b> → 在<b>组卷管理</b>创建试卷 → <b>发起测评</b>选择人才 →
          在答题台完成作答 → 到<b>成绩统计</b>查看 AI 能力报告与短板分析，系统会基于短板自动推荐培训课程。
        </div>
      </template>
    </el-alert>
  </div>
</template>

<style scoped>
.stat .label { color: #888; font-size: 13px; }
.stat .value { font-size: 30px; font-weight: 600; margin-top: 8px; color: #1f2937; }

.action { border: 1px solid var(--el-border-color); border-radius: 12px; padding: 18px; text-align: center; cursor: pointer; transition: all .2s; }
.action:hover { border-color: var(--accent); box-shadow: 0 4px 16px rgba(0,0,0,.08); transform: translateY(-2px); }
.action-icon { font-size: 30px; }
.action-title { margin-top: 10px; font-weight: 500; color: #1f2937; }
.action-desc { margin-top: 4px; font-size: 12px; color: #9ca3af; }

.bar-row { display: flex; align-items: center; gap: 10px; margin-bottom: 10px; }
.bar-name { width: 64px; font-size: 13px; color: #555; }
.bar-track { flex: 1; height: 12px; background: #f1f3f6; border-radius: 6px; overflow: hidden; }
.bar-fill { height: 100%; background: #4f46e5; border-radius: 6px; transition: width .4s; }
.bar-val { width: 30px; text-align: right; font-size: 13px; color: #555; }
</style>
