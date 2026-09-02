<!-- hq新增内容 - 人才档案批次2.2 + 批次A [tags.vue]
     标签字典管理：按 type 分组 + 增/改/删 + 启用/停用切换。
     批次A：7 大类 + 「绑定人才」列（人数 + 悬浮人名）。
     后端：/api/v1/talent-dicts（见 app/routers/talent_dict.py）。 -->
<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  createTalentDict,
  deleteTalentDict,
  listTalentDicts,
  updateTalentDict,
} from '@/api/talent'

const router = useRouter()

// hq+ 批次A：合并前 7 大类（fit=适配岗位 / experience=项目经验 / level=能力层级
// strength=职业特长 / quality=综合素质 / potential=潜力评级 / skill=专业技能）。
// 后端 _with_stats 已把袁武 tal_tag.category 映射回这些旧 code（custom→strength），
// 其他模块不受影响。
const TYPES = [
  { code: 'skill',      label: '专业技能' },
  { code: 'experience', label: '项目经验' },
  { code: 'level',      label: '能力层级' },
  { code: 'strength',   label: '职业特长' },
  { code: 'quality',    label: '综合素质' },
  { code: 'fit',        label: '适配岗位' },
  { code: 'potential',  label: '潜力评级' },
]
const TYPE_LABEL = Object.fromEntries(TYPES.map((t) => [t.code, t.label]))

// hq+ 2026-09-01：默认 type=''（不传过滤），后端返回全量字典，前端按 type 客户端分组显示
// 之前 query.type='fit' 会传 category='fit' 过滤，云库无 fit 类 → 全 0 显示
const query = reactive({ type: '', keyword: '' })
const rows = ref([])
const allDicts = ref([])
const loading = ref(false)

const dialog = reactive({ visible: false, editing: false })
const formRef = ref()
const form = reactive({ id: null, code: '', name: '', type: 'fit', sort: 0, enabled: 1 })
const rules = {
  code: [{ required: true, message: '请输入标签编码', trigger: 'blur' }],
  name: [{ required: true, message: '请输入标签名称', trigger: 'blur' }],
  type: [{ required: true, message: '请选择分类', trigger: 'change' }],
}

async function load() {
  loading.value = true
  try {
    // hq+ 始终拉全量（仅 keyword 过滤），让客户端按 type 分组；用户选具体 tab 时按 type 过滤
    const params = { only_enabled: true }
    if (query.keyword) params.keyword = query.keyword
    if (query.type) params.type = query.type
    const res = await listTalentDicts(params)
    const d = res.data || {}
    rows.value = d.items || []
    allDicts.value = d.items || []
    loading.value = false
  } catch (e) {
    console.error('[hq] 加载字典失败：', e)
    rows.value = []
    allDicts.value = []
    loading.value = false
  }
}

function openCreate() {
  Object.assign(form, { id: null, code: '', name: '', type: query.type || 'fit', sort: 0, enabled: 1 })
  dialog.editing = false
  dialog.visible = true
}
function openEdit(row) {
  Object.assign(form, {
    id: row.id, code: row.code, name: row.name, type: row.type, sort: row.sort, enabled: row.enabled,
  })
  dialog.editing = true
  dialog.visible = true
}

async function save() {
  await formRef.value.validate()
  if (form.id) await updateTalentDict(form.id, form)
  else await createTalentDict(form)
  ElMessage.success('已保存')
  dialog.visible = false
  load()
}

async function toggleEnabled(row) {
  await updateTalentDict(row.id, { enabled: row.enabled === 1 ? 0 : 1 })
  ElMessage.success(row.enabled === 1 ? '已停用' : '已启用')
  load()
}

async function del(row) {
  await ElMessageBox.confirm(
    `确定删除标签「${row.name}」（${row.code}）？删除后已被人才引用的关联记录会被一并级联删除。`,
    '提示',
    { type: 'warning' },
  )
  await deleteTalentDict(row.id)
  ElMessage.success('已删除')
  load()
}

// 按 type 分组（保证顺序稳定）
const grouped = computed(() => {
  const map = Object.fromEntries(TYPES.map((t) => [t.code, []]))
  rows.value.forEach((r) => { (map[r.type] || (map[r.type] = [])).push(r) })
  return TYPES.map((t) => ({ ...t, list: map[t.code] || [] }))
})

// hq+  批次A：点击「N 人」跳到人才列表并筛选该标签
function goTalentsByTag(row) {
  // 人才列表页支持 ?tag=xxx 参数过滤（后端 keyword 暂不支持按标签，
  // 这里仅跳列表 + 提示，真正筛选由后端 list 接口 tag 参数扩展——批次A 先跳详情筛选）
  router.push({ path: '/talent', query: { tag: row.name } })
}

onMounted(load)
</script>

<template>
  <el-card>
    <!-- 筛选条 -->
    <div class="bar">
      <el-radio-group v-model="query.type" @change="load">
        <el-radio-button value="">全部</el-radio-button>
        <el-radio-button v-for="t in TYPES" :key="t.code" :value="t.code">{{ t.label }}</el-radio-button>
      </el-radio-group>
      <el-input v-model="query.keyword" placeholder="按编码/名称搜索" style="width:220px" clearable
        @keyup.enter="load" />
      <el-button type="primary" @click="load">查询</el-button>
      <div style="flex:1" />
      <el-button type="primary" plain @click="openCreate">新增标签</el-button>
    </div>

    <!-- 当前类型列表 -->
    <el-table :data="rows" v-loading="loading" stripe>
      <el-table-column prop="id" label="ID" width="64" />
      <el-table-column prop="code" label="编码" min-width="160" />
      <!-- hq+  完善：名称列可点击升降序排序 -->
      <el-table-column prop="name" label="名称" min-width="140" sortable />
      <el-table-column label="分类" width="120">
        <template #default="{ row }">
          <el-tag size="small">{{ TYPE_LABEL[row.type] || row.type }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="sort" label="排序" width="80" sortable />
      <!-- hq+  批次A+完善：绑定人才列（点击人数表头可升降序） -->
      <el-table-column prop="talent_count" label="绑定人才" width="200" sortable
        :sort-method="(a, b) => (a.talent_count || 0) - (b.talent_count || 0)">
        <template #default="{ row }">
          <template v-if="row.talent_count > 0">
            <el-popover trigger="hover" width="260">
              <template #reference>
                <el-link type="primary" :underline="false" @click="goTalentsByTag(row)">
                  {{ row.talent_count }} 人
                </el-link>
              </template>
              <div class="pop-names">
                <el-tag v-for="(n, i) in row.talent_names" :key="i" size="small" effect="plain"
                  style="margin:2px">{{ n }}</el-tag>
                <div v-if="row.talent_count > (row.talent_names || []).length" class="more">
                  还有 {{ row.talent_count - (row.talent_names || []).length }} 人…
                </div>
              </div>
            </el-popover>
          </template>
          <span v-else style="color:#9ca3af;font-size:12px">0 人</span>
        </template>
      </el-table-column>
      <el-table-column label="状态" width="90">
        <template #default="{ row }">
          <el-switch
            :model-value="row.enabled === 1"
            :active-value="true" :inactive-value="false"
            @click="toggleEnabled(row)"
          />
          <span style="margin-left:6px;color:#6b7280;font-size:12px">
            {{ row.enabled === 1 ? '启用' : '停用' }}
          </span>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="160" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
          <el-button link type="danger" @click="del(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <!-- 全部类型的紧凑视图 -->
    <div class="overview">
      <div class="overview-title">字典全景（按分类）</div>
      <div v-for="g in grouped" :key="g.code" class="overview-row">
        <div class="overview-cat">{{ g.label }} <span>({{ g.list.length }})</span></div>
        <div class="overview-tags">
          <el-tag v-for="t in g.list" :key="t.id" :type="t.enabled === 1 ? '' : 'info'"
            effect="plain" size="small" :title="t.code">
            {{ t.name }}
          </el-tag>
          <span v-if="!g.list.length" class="empty">暂无</span>
        </div>
      </div>
    </div>
  </el-card>

  <!-- 新增/编辑对话框 -->
  <el-dialog v-model="dialog.visible" :title="dialog.editing ? '编辑标签' : '新增标签'" width="480px">
    <el-form ref="formRef" :model="form" :rules="rules" label-width="80px">
      <el-form-item label="编码" prop="code">
        <el-input v-model="form.code" :disabled="dialog.editing" placeholder="唯一编码，如 architect" />
      </el-form-item>
      <el-form-item label="名称" prop="name"><el-input v-model="form.name" /></el-form-item>
      <el-form-item label="分类" prop="type">
        <el-select v-model="form.type" style="width:100%">
          <el-option v-for="t in TYPES" :key="t.code" :label="t.label" :value="t.code" />
        </el-select>
      </el-form-item>
      <el-form-item label="排序"><el-input-number v-model="form.sort" :min="0" :max="9999" /></el-form-item>
      <el-form-item v-if="dialog.editing" label="启用">
        <el-switch v-model="form.enabled" :active-value="1" :inactive-value="0" />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="dialog.visible=false">取消</el-button>
      <el-button type="primary" @click="save">保存</el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.bar { display: flex; gap: 10px; margin-bottom: 14px; align-items: center; flex-wrap: wrap; }
.overview { margin-top: 24px; }
.overview-title { font-weight: 600; color: #374151; margin-bottom: 12px; }
.overview-row { display: flex; align-items: center; padding: 8px 0; border-bottom: 1px dashed #eef1f5; }
.overview-cat { width: 100px; color: #6b7280; font-size: 13px; }
.overview-cat span { color: #9ca3af; font-size: 12px; }
.overview-tags { flex: 1; display: flex; flex-wrap: wrap; gap: 6px; }
.overview-tags .empty { color: #9ca3af; font-size: 12px; }
</style>
