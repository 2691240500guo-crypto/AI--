<!-- hq新增内容 - 人才档案批次1 [detail.vue]
     通过静态路由 /talent/detail/:id 访问，列表页 `router.push` 跳过来。
     后端：GET /api/v1/talent/{id}

     hq+  批次2.3c：末尾追加 AI 档案问答输入框 -->
<script setup>
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { askTalentQA, getTalent } from '@/api/talent'

const route = useRoute()
const router = useRouter()
const loading = ref(false)
const data = ref(null)
const activeCollapse = ref(['summary'])  // 默认展开「个人简介」

// hq+  AI 问答
const qaQuestion = ref('')
const qaHistory = ref([])  // [{q, a}]
const qaBusy = ref(false)

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
}

async function askQuestion() {
  const q = qaQuestion.value.trim()
  if (!q) return
  qaBusy.value = true
  try {
    const res = await askTalentQA(Number(route.params.id), q)
    qaHistory.value.unshift({ q, a: res.data?.answer || '(LLM 无回答)' })
    qaQuestion.value = ''
  } catch (e) {
    ElMessage.error('AI 问答失败：' + (e.message || '未知错误'))
  } finally {
    qaBusy.value = false
  }
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
        <el-page-header @back="router.push('/talent/list')" :title="'返回列表'">
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

      <!-- hq+  批次2.3c：AI 档案问答 -->
      <el-divider content-position="left">AI 档案问答</el-divider>
      <div class="qa" v-loading="qaBusy">
        <div class="qa-input">
          <el-input
            v-model="qaQuestion"
            type="textarea"
            :rows="2"
            placeholder="例如：这位候选人的核心优势是什么？适合做数据中台负责人吗？"
            @keydown.ctrl.enter.prevent="askQuestion"
          />
          <div class="qa-tips">提示：Ctrl + Enter 提交，问题会基于本人才档案 + AI 报告做 RAG 回答。</div>
        </div>
        <el-button type="primary" :loading="qaBusy" :disabled="!qaQuestion.trim()" @click="askQuestion">
          提问
        </el-button>
        <div v-if="qaHistory.length" class="qa-list">
          <div v-for="(item, i) in qaHistory" :key="i" class="qa-item">
            <div class="qa-q"><b>Q：</b>{{ item.q }}</div>
            <div class="qa-a" v-if="item.a"><b>A：</b>{{ item.a }}</div>
          </div>
        </div>
        <el-empty v-else description="还没有问答记录" :image-size="60" />
      </div>
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

/* hq+  AI 问答区 */
.qa { background: #f9fafb; border: 1px solid #eef1f5; border-radius: 6px; padding: 14px 16px; margin-top: 8px; }
.qa-input { margin-bottom: 10px; }
.qa-tips { font-size: 12px; color: #9ca3af; margin-top: 4px; }
.qa-list { margin-top: 14px; display: flex; flex-direction: column; gap: 10px; }
.qa-item { padding: 10px 12px; border: 1px solid #e5e7eb; border-radius: 6px; background: #fff; }
.qa-q { color: #1d4ed8; font-size: 13px; margin-bottom: 6px; }
.qa-a { color: #374151; font-size: 13px; white-space: pre-wrap; word-break: break-word; }
</style>
