<!-- hq新增内容 - 人才档案批次2.2 [edit.vue]
     新增 + 编辑同一个页：
       - /talent/new      → POST /talent
       - /talent/edit/:id → GET /talent/:id + PUT /talent/:id
     标签通过 PUT /talent/:id/tags 单独绑定，便于保留 source 维度。
     后端在 create/update 后会自动跑规则版打标签（auto）。
     真 AI 抽取留批次 2.3c。 -->
<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import {
  bindTalentTags,
  buildProfile,            // hq+ 合并袁文武：生成 AI 数字画像
  createTalent,
  getTalent,
  getTalentReport,        // hq+
  getTalentVectors,       // hq+ 批次B
  listTalentDicts,
  listTalentTags,
  reparseTalent,          // hq+
  updateTalent,
} from '@/api/talent'

const route = useRoute()
const router = useRouter()

// 是否编辑（路由中没有 id 时为新增）
const isEdit = computed(() => route.name === 'talent-edit')
const talentId = computed(() => route.params.id ? Number(route.params.id) : null)

// 表单数据（2026-09-01 合并：字段对齐 tal_talent）
const formRef = ref()
const form = reactive({
  name: '',
  gender: '',
  birth_year: null,
  phone: '',
  email: '',
  current_title: '',
  highest_education: '',
  years_experience: 0,
  current_company: '',
  summary: '',
  resume_text: '',
  resume_source: 'manual',
})
const rules = {
  name: [{ required: true, message: '请输入姓名', trigger: 'blur' }],
  phone: [{ pattern: /^$|^1[3-9]\d{9}$/, message: '手机号格式不正确', trigger: 'blur' }],
  email: [{ type: 'email', message: '邮箱格式不正确', trigger: 'blur' }],
}

// 标签字典 + 已绑定
const allDicts = ref([])
const boundDictIds = ref([])  // 已绑定（手动 + 自动 + AI）
const loadingDicts = ref(false)
// hq+ 2026-09-01：前端展示分类 code 与后端 tal_tag.category 对齐（fit→position, experience→exp）
const TYPES = [
  { code: 'fit',         label: '适配岗位',    map: 'position' },
  { code: 'experience',  label: '项目经验',    map: 'exp' },
  { code: 'quality',     label: '综合素质',    map: 'quality' },
  { code: 'skill',       label: '专业技能',    map: 'skill' },
  { code: 'potential',   label: '潜力评级',    map: 'potential' },
  { code: 'custom',      label: '通用/AI 抽取', map: 'custom' },
]

// 按 type 分组的标签（带 checked 状态）
const groupedTags = computed(() => {
  const grouped = Object.fromEntries(TYPES.map((t) => [t.code, []]))
  allDicts.value.forEach((d) => {
    // hq+ 2026-09-01：tags.vue 回退后，后端 type 改回合并前旧 code；edit.vue 改用 category（袁武原 code）与 TYPES.map 对齐
    const t = TYPES.find((x) => x.map === d.category)
    if (t) grouped[t.code].push(d)
  })
  return TYPES.map((t) => ({
    ...t,
    list: grouped[t.code].map((d) => ({
      ...d,
      checked: boundDictIds.value.includes(d.id),
      bound: true,  // 仅 UI 用：标记已绑定，便于颜色区分
    })),
  }))
})

// 已绑定的来源（用于 chip 展示）
const boundSource = ref({})  // { dict_id: 'manual' | 'auto' | 'ai' }
function sourceType(s) { return { manual: '', auto: 'success', ai: 'warning' }[s] || 'info' }

// hq+  批次B：三维向量画像（技能/经验/素质）
const vectors = ref([])
const vectorsBusy = ref(false)
const profileBusy = ref(false)
async function loadVectors() {
  if (!talentId.value) { vectors.value = []; return }
  vectorsBusy.value = true
  try {
    const res = await getTalentVectors(talentId.value)
    vectors.value = res.data || []
  } catch (_) { vectors.value = [] } finally {
    vectorsBusy.value = false
  }
}
// hq+  合并袁文武：一键生成 AI 数字画像（AI 标签 + 三维向量 + 潜力评级）
async function genProfile() {
  if (!talentId.value) return ElMessage.warning('请先保存档案')
  profileBusy.value = true
  try {
    const res = await buildProfile(talentId.value)
    const p = res.data || {}
    ElMessage.success(`画像已生成：${(p.ai_tags || []).length} 个 AI 标签${p.vectors_built ? '，三维向量已入库' : ''}`)
    loadVectors()
  } catch (e) {
    ElMessage.error('画像生成失败：' + (e.message || ''))
  } finally {
    profileBusy.value = false
  }
}
const DIM_COLOR = { skill: 'success', exp: 'primary', quality: 'warning' }

const submitting = ref(false)

// hq+  批次2.3b：AI 报告
const report = ref(null)
const reparseBusy = ref(false)
async function loadReport() {
  if (!talentId.value) { report.value = null; return }
  try {
    const res = await getTalentReport(talentId.value)
    report.value = res.data
  } catch (_) { report.value = null }
}
async function doReparse() {
  if (!talentId.value) { ElMessage.warning('请先保存档案'); return }
  reparseBusy.value = true
  try {
    const res = await reparseTalent(talentId.value)
    ElMessage.success(`AI 解析完成，本轮命中标签 ${res.data?.new_tag_count ?? 0} 条`)
    await loadReport()
    await refreshBound()
  } catch (e) {
    ElMessage.error('AI 解析失败：' + (e.message || '未知错误'))
  } finally {
    reparseBusy.value = false
  }
}

async function loadDicts() {
  loadingDicts.value = true
  try {
    const res = await listTalentDicts({ only_enabled: true })
    allDicts.value = res.data
  } finally {
    loadingDicts.value = false
  }
}

async function loadTalent() {
  if (!talentId.value) return
  try {
    const res = await getTalent(talentId.value)
    const d = res.data || {}
    // hq+ 2026-09-01 改为显式字段映射（避免 Object.assign + 大对象 的反应式触发不可靠）
    Object.assign(form, {
      name: d.name || '',
      gender: d.gender || '',
      birth_year: d.birth_year || null,
      phone: d.phone || '',
      email: d.email || '',
      current_title: d.current_title || '',
      highest_education: d.highest_education || '',
      years_experience: d.years_experience || 0,
      current_company: d.current_company || '',
      summary: d.summary || '',
      resume_text: d.resume_text || '',
      resume_source: d.resume_source || 'manual',
    })
    await refreshBound()
  } catch (e) {
    ElMessage.error('加载档案失败：' + (e.message || ''))
  }
}

// hq+  检测「字段空白 + 有简历原文」，走 LLM 抽取把简历自动填到表单
async function autoFillFromResume() {
  if (!talentId.value) return
  // 触发条件：核心 8 字段都空 且 raw_text 里有可抽的内容
  const empty = !form.name || form.name.startsWith('未命名-')
    || (!form.phone && !form.email && !form.current_title
        && !form.current_company && !form.summary)
  if (!empty) return                                  // 已有内容，不自动抽
  // 看主档的 raw_text（后端 TalentOut 没暴露 raw_text，改用 /report 接口里
  // parsed_json 里有原文不行；改为让后端在 talent GET 里也带 raw_text——
  // 但 schema 没改，简单做法：走后端 reparse，它会自动用 obj.raw_text 处理）
  reparseBusy.value = true
  try {
    await reparseTalent(talentId.value)
    await loadTalent()
    await loadReport()
    ElMessage.success('已按简历自动填充（可继续修改）')
  } catch (e) {
    ElMessage.warning('自动填充失败：' + (e.message || '请点 AI 解析 按钮重跑'))
  } finally {
    reparseBusy.value = false
  }
}

async function refreshBound() {
  if (!talentId.value) { boundDictIds.value = []; return }
  const res = await listTalentTags(talentId.value)
  boundDictIds.value = res.data.map((t) => t.tag_id ?? t.id)
  boundSource.value = Object.fromEntries(res.data.map((t) => [t.tag_id ?? t.id, t.source]))
}

async function save() {
  await formRef.value.validate()
  submitting.value = true
  try {
    if (isEdit.value) {
      await updateTalent(talentId.value, form)
    } else {
      const res = await createTalent(form)
      // 新建后路由切到 edit 模式，便于后续继续编辑
      const newId = res.data.id
      router.replace({ name: 'talent-edit', params: { id: newId } })
      ElMessage.success('已创建，请继续完善标签')
      return  // 后续等下次点保存
    }

    // 绑定标签
    await bindTalentTags(talentId.value, {
      tag_ids: boundDictIds.value, source: 'manual',
    })
    ElMessage.success('已保存')
    await refreshBound()
  } finally {
    submitting.value = false
  }
}

function back() { router.push('/talent/list') }

// 切标签选中
function toggleTag(t) {
  if (t.checked) {
    boundDictIds.value = boundDictIds.value.filter((i) => i !== t.id)
  } else {
    boundDictIds.value = [...boundDictIds.value, t.id]
  }
}

// 切换到指定类型分组
const activeTab = ref('fit')
watch(activeTab, () => {/* 切分组无副作用，仅 UX */})

onMounted(async () => {
  await loadDicts()
  if (isEdit.value) {
    await loadTalent()
    await loadReport()  // hq+
    await loadVectors() // hq+ 批次B
    // hq+  若字段空（且有简历原文），自动按简历 LLM 抽取填到表单
    await autoFillFromResume()
    await loadVectors() // hq+ 批次B：自动填充后再刷一次向量
  }
})
</script>

<template>
  <el-card>
    <template #header>
      <div class="head">
        <el-page-header @back="back" title="返回列表">
          <template #content>
            <span class="title">
              {{ isEdit ? `编辑人才 #${talentId}` : '新增人才' }}
            </span>
          </template>
        </el-page-header>
      </div>
    </template>

    <el-form ref="formRef" :model="form" :rules="rules" label-width="100px" v-loading="submitting">
      <el-divider content-position="left">基础信息</el-divider>
      <el-row :gutter="20">
        <el-col :span="12"><el-form-item label="姓名" prop="name"><el-input v-model="form.name" /></el-form-item></el-col>
        <el-col :span="12"><el-form-item label="性别">
          <el-radio-group v-model="form.gender">
            <el-radio value="">未知</el-radio>
            <el-radio value="男">男</el-radio>
            <el-radio value="女">女</el-radio>
          </el-radio-group>
        </el-form-item></el-col>
        <el-col :span="12"><el-form-item label="出生年"><el-input-number v-model="form.birth_year" :min="1900" :max="2025" /></el-form-item></el-col>
        <el-col :span="12"><el-form-item label="手机" prop="phone"><el-input v-model="form.phone" /></el-form-item></el-col>
        <el-col :span="12"><el-form-item label="邮箱" prop="email"><el-input v-model="form.email" /></el-form-item></el-col>
        <el-col :span="12"><el-form-item label="学历">
          <el-select v-model="form.highest_education" placeholder="选择学历" clearable style="width:100%">
            <el-option label="本科" value="本科" />
            <el-option label="硕士" value="硕士" />
            <el-option label="博士" value="博士" />
            <el-option label="大专" value="大专" />
            <el-option label="其他" value="其他" />
          </el-select>
        </el-form-item></el-col>
      </el-row>

      <el-divider content-position="left">职业信息</el-divider>
      <el-row :gutter="20">
        <el-col :span="12"><el-form-item label="现职称"><el-input v-model="form.current_title" /></el-form-item></el-col>
        <el-col :span="12"><el-form-item label="当前公司"><el-input v-model="form.current_company" /></el-form-item></el-col>
        <el-col :span="12"><el-form-item label="工作年限（年）"><el-input-number v-model="form.years_experience" :min="0" :max="80" /></el-form-item></el-col>
        <el-col :span="12"><el-form-item label="来源">
          <el-radio-group v-model="form.resume_source">
            <el-radio value="manual">人工</el-radio>
            <el-radio value="import">导入</el-radio>
            <el-radio value="agent_parsed">AI 解析</el-radio>
          </el-radio-group>
        </el-form-item></el-col>
      </el-row>

      <el-divider content-position="left">文本画像</el-divider>
      <el-form-item label="个人简介">
        <el-input v-model="form.summary" type="textarea" :rows="3" placeholder="AI 摘要 / 人工清洗后的简历简介" />
      </el-form-item>
      <el-form-item label="简历原文">
        <el-input v-model="form.resume_text" type="textarea" :rows="5" placeholder="可选，原简历全文 / OCR 文本" />
      </el-form-item>

      <!-- hq+  标签选择区 -->
      <el-divider content-position="left">人才标签（百级标签体系）</el-divider>
      <div class="tag-area" v-loading="loadingDicts">
        <div class="tag-summary">
          <span>当前已绑 <b>{{ boundDictIds.length }}</b> 个标签</span>
          <span class="hint">点击下方 chip 切换选中；已绑的会显示来源色（manual 灰 / auto 绿 / ai 橙）</span>
        </div>
        <el-tabs v-model="activeTab">
          <el-tab-pane v-for="g in groupedTags" :key="g.code" :name="g.code" :label="`${g.label} (${g.list.filter((t) => t.checked).length}/${g.list.length})`">
            <div class="chip-grid">
              <el-check-tag
                v-for="t in g.list" :key="t.id"
                :checked="t.checked"
                :disabled="!t.enabled"
                @change="toggleTag(t)"
              >
                {{ t.name }}
                <span v-if="boundSource[t.id]" class="src" :class="sourceType(boundSource[t.id])">
                  {{ boundSource[t.id] === 'manual' ? '·人' : (boundSource[t.id] === 'auto' ? '·规' : '·AI') }}
                </span>
              </el-check-tag>
              <span v-if="!g.list.length" class="empty">该分类暂无字典条目。请先在「标签管理」页新增。</span>
            </div>
          </el-tab-pane>
        </el-tabs>
      </div>

      <!-- hq+  批次2.3b：AI 评估报告 -->
      <el-divider content-position="left">AI 解析报告</el-divider>
      <el-card shadow="never" class="report" v-loading="reparseBusy">
        <template #header>
          <div class="report-head">
            <span>基于 Ollama qwen2.5 自动抽取 + 评估</span>
            <div>
              <el-button :loading="reparseBusy" :disabled="!isEdit" @click="doReparse">
                {{ report ? '重新解析' : 'AI 解析' }}
              </el-button>
              <el-button v-if="report" size="small" @click="loadReport">刷新</el-button>
            </div>
          </div>
        </template>
        <div v-if="!report" class="report-empty">
          {{ isEdit ? '当前还没有 AI 报告，点击「AI 解析」自动抽取' : '请先保存档案后再触发 AI 解析' }}
        </div>
        <template v-else>
          <el-row :gutter="20">
            <el-col :span="12">
              <div class="report-title">技能关键词（{{ report.skills?.length || 0 }}）</div>
              <div class="chip-grid">
                <el-tag v-for="(s, i) in report.skills" :key="i" type="success" effect="plain" size="small">{{ s }}</el-tag>
                <span v-if="!report.skills?.length" class="empty">—</span>
              </div>
            </el-col>
            <el-col :span="12">
              <div class="report-title">适配岗位（{{ report.fit_positions?.length || 0 }}）</div>
              <div class="chip-grid">
                <el-tag v-for="(s, i) in report.fit_positions" :key="i" type="primary" effect="plain" size="small">{{ s }}</el-tag>
                <span v-if="!report.fit_positions?.length" class="empty">—</span>
              </div>
              <div v-if="report.potential" style="margin-top:8px">
                <span style="color:#6b7280">潜力评级：</span>
                <el-tag type="warning">{{ report.potential }}</el-tag>
              </div>
            </el-col>
            <el-col :span="12" style="margin-top:14px">
              <div class="report-title">亮点</div>
              <ul class="bullet">
                <li v-for="(s, i) in report.highlights" :key="i">{{ s }}</li>
                <li v-if="!report.highlights?.length" class="empty">—</li>
              </ul>
            </el-col>
            <el-col :span="12" style="margin-top:14px">
              <div class="report-title">短板</div>
              <ul class="bullet">
                <li v-for="(s, i) in report.shortcomings" :key="i">{{ s }}</li>
                <li v-if="!report.shortcomings?.length" class="empty">—</li>
              </ul>
            </el-col>
            <el-col :span="24" style="margin-top:14px" v-if="report.summary_report">
              <div class="report-title">评估总结</div>
              <pre class="summary">{{ report.summary_report }}</pre>
            </el-col>
            <el-col :span="24" style="margin-top:6px" v-if="!report.summary_report && report.parsed_json === null">
              <div class="report-empty">本次 AI 解析失败，可点击「重新解析」重试</div>
            </el-col>
          </el-row>
        </template>
      </el-card>

      <!-- hq+  批次B：三维向量画像 -->
      <el-divider content-position="left">三维向量画像（Milvus）</el-divider>
      <el-card shadow="never" class="report" v-loading="vectorsBusy">
        <template #header>
          <div class="report-head">
            <span>技能 / 经验 / 素质 三个维度的全局向量（保存后自动实时更新）</span>
            <div style="display:flex;gap:8px">
              <el-button v-if="isEdit" size="small" type="primary" :loading="profileBusy"
                         @click="genProfile">生成 AI 画像</el-button>
              <el-button v-if="isEdit" size="small" @click="loadVectors">刷新</el-button>
            </div>
          </div>
        </template>
        <div v-if="!vectors.length" class="report-empty">
          {{ isEdit ? '尚未生成向量，保存或触发 AI 解析后自动写入' : '请先保存档案' }}
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

      <div class="footer">
        <el-button @click="back">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="save">保存</el-button>
      </div>
    </el-form>
  </el-card>
</template>

<style scoped>
.head { display: flex; align-items: center; }
.title { font-size: 18px; font-weight: 600; }
.tag-area { background: #f9fafb; border: 1px solid #eef1f5; border-radius: 6px; padding: 12px 14px; }
.tag-summary { display: flex; gap: 12px; align-items: center; margin-bottom: 8px; color: #374151; font-size: 13px; }
.tag-summary .hint { color: #9ca3af; font-size: 12px; }
.chip-grid { display: flex; flex-wrap: wrap; gap: 8px; }
.chip-grid .empty { color: #9ca3af; font-size: 12px; }
.src { font-size: 11px; padding: 0 3px; border-radius: 3px; margin-left: 2px; color: #fff; }
.src.info    { background: #94a3b8; }  /* manual */
.src.success { background: #16a34a; }  /* auto */
.src.warning { background: #f59e0b; }  /* ai */
.footer { margin-top: 20px; text-align: right; }

/* hq+  报告区 */
.report { background: #fcfcfd; }
.report-head { display: flex; align-items: center; justify-content: space-between; }
.report-title { font-weight: 600; color: #374151; margin-bottom: 6px; font-size: 13px; }
.report-empty { color: #9ca3af; font-size: 13px; padding: 8px 0; }
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

/* hq+  三维向量 */
.vec-card { background: #fcfcfd; margin-bottom: 8px; }
.vec-head { display: flex; align-items: center; justify-content: space-between; }
.vec-ok  { color: #16a34a; font-size: 12px; }
.vec-no  { color: #9ca3af; font-size: 12px; }
.vec-text {
  font-size: 12px; color: #4b5563; line-height: 1.7;
  max-height: 130px; overflow: auto;
  word-break: break-word; white-space: pre-wrap;
}
</style>
