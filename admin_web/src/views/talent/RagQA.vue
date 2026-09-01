<!-- hq新增内容 - 档案 RAG 问答（需求⑤ 档案RAG问答：单档案/批量研判）
     功能：选择范围（单档案/批量）→ 输入自然语言问题 → LLM 基于档案画像生成
           优势/短板/适配岗位/发展潜力 研判小结 -->
<template>
  <div class="page">
    <div class="toolbar">
      <div class="title">档案 RAG 问答</div>
      <div class="sub">基于人才档案画像 + 向量检索，自动生成人才研判小结</div>
    </div>

    <el-row :gutter="16">
      <!-- 左侧：问询配置 -->
      <el-col :span="10">
        <el-card shadow="never">
          <template #header>问询设置</template>
          <el-form label-width="90px">
            <el-form-item label="问答范围">
              <el-radio-group v-model="form.scope">
                <el-radio-button value="single">单档案</el-radio-button>
                <el-radio-button value="batch">批量档案</el-radio-button>
              </el-radio-group>
            </el-form-item>

            <el-form-item v-if="form.scope === 'single'" label="选择人才">
              <el-select v-model="form.talent_id" filterable remote clearable
                         placeholder="输入姓名搜索" :remote-method="searchTalents"
                         :loading="talentLoading" style="width:100%">
                <el-option v-for="t in talentOptions" :key="t.id" :value="t.id"
                           :label="`${t.name}（${t.current_title || '—'}）`" />
              </el-select>
            </el-form-item>

            <el-form-item v-else label="人才 ID 列表">
              <el-input v-model="form.talent_ids" placeholder="逗号分隔，如：5,8,12（留空=全部人才）" />
            </el-form-item>

            <el-form-item label="问题">
              <el-input v-model="form.question" type="textarea" :rows="4"
                        placeholder="例如：这个候选人擅长什么？短板是什么？适合什么岗位？发展潜力如何？" />
            </el-form-item>

            <el-form-item label="召回条数">
              <el-input-number v-model="form.top_k" :min="1" :max="20" />
            </el-form-item>

            <el-form-item>
              <el-button type="primary" :loading="raging" :disabled="!form.question.trim()"
                         @click="onRag">
                <el-icon style="margin-right:4px"><ChatDotRound /></el-icon>生成研判
              </el-button>
              <el-button @click="onClear">清空</el-button>
            </el-form-item>
          </el-form>
        </el-card>
      </el-col>

      <!-- 右侧：研判结果 -->
      <el-col :span="14">
        <el-card shadow="never">
          <template #header>
            <div class="card-head">
              <span>研判结果</span>
              <el-tag v-if="ragMeta" type="success" size="small">{{ ragMeta }}</el-tag>
            </div>
          </template>
          <div v-if="raging" v-loading="true" style="min-height:300px"></div>
          <div v-else-if="ragAnswer" class="answer">
            <pre class="answer-text">{{ ragAnswer }}</pre>
          </div>
          <el-empty v-else description="输入问题后点「生成研判」，AI 将基于档案画像总结优势、短板、适配岗位与潜力" />
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { ChatDotRound } from '@element-plus/icons-vue'
import { ragAsk, listTalents } from '@/api/talent'

const form = reactive({ scope: 'single', talent_id: null, talent_ids: '', question: '', top_k: 5 })
const raging = ref(false)
const ragAnswer = ref('')
const ragMeta = ref('')

// 单档案选择：远程搜索人才
const talentOptions = ref([])
const talentLoading = ref(false)
async function searchTalents(kw) {
  if (!kw) return
  talentLoading.value = true
  try {
    const res = await listTalents({ keyword: kw, page_size: 20 })
    talentOptions.value = res.data.items || []
  } finally { talentLoading.value = false }
}

async function onRag() {
  const q = form.question.trim()
  if (!q) return ElMessage.warning('请输入问题')
  if (form.scope === 'single' && !form.talent_id) return ElMessage.warning('请选择人才')
  raging.value = true
  ragAnswer.value = ''
  ragMeta.value = ''
  try {
    const payload = {
      question: q,
      scope: form.scope,
      top_k: form.top_k,
    }
    if (form.scope === 'single') payload.talent_id = form.talent_id
    else {
      const ids = form.talent_ids
        ? form.talent_ids.split(',').map((s) => parseInt(s.trim())).filter((n) => !isNaN(n))
        : null
      if (ids && ids.length) payload.talent_ids = ids
    }
    const res = await ragAsk(payload)
    ragAnswer.value = res.data.answer || '（无回答）'
    const covered = res.data.talents_covered
    if (covered != null) ragMeta.value = `已覆盖 ${covered} 位人才`
  } catch (e) {
    ElMessage.error('研判失败：' + (e.message || ''))
  } finally {
    raging.value = false
  }
}

function onClear() {
  form.question = ''
  form.talent_id = null
  form.talent_ids = ''
  ragAnswer.value = ''
  ragMeta.value = ''
}
</script>

<style scoped>
.page { padding: 4px 2px; }
.toolbar { margin-bottom: 16px; }
.title { font-size: 16px; font-weight: 600; color: #1f2937; }
.sub { font-size: 12px; color: #9ca3af; margin-top: 4px; }
.card-head { display: flex; align-items: center; gap: 10px; }
.answer { padding: 6px 4px; }
.answer-text {
  white-space: pre-wrap; word-break: break-word;
  font-family: 'PingFang SC', 'Microsoft YaHei', sans-serif;
  font-size: 14px; line-height: 1.8; color: #374151;
  background: #f8fafc; border: 1px solid #eef1f5; border-radius: 8px; padding: 16px;
}
</style>
