<!-- hq新增内容 - 数据治理与查重合并（需求③ 智能查重与数据治理）
     功能：治理扫描（重复/错误/缺失识别+整改建议）、一键查重合并、
           Excel/Word 批量导入、多维统计、过期提醒、一键导出 -->
<template>
  <div class="page">
    <!-- 标题 + 工具栏 -->
    <div class="toolbar">
      <div class="title">数据治理与查重合并</div>
      <div class="actions">
        <el-button type="primary" :loading="scanning" @click="onGovern">
          <el-icon style="margin-right:4px"><Search /></el-icon>数据治理扫描
        </el-button>
        <el-button type="warning" :loading="repairing" @click="onRepair">
          <el-icon style="margin-right:4px"><MagicStick /></el-icon>一键标准化整改
        </el-button>
        <el-button @click="onStats">多维统计</el-button>
        <el-button @click="onExpiring">过期提醒</el-button>
        <el-button type="success" :loading="exporting" @click="onExport">导出 Excel</el-button>
      </div>
    </div>

    <!-- 治理问题清单 -->
    <el-card shadow="never">
      <template #header>
        <div class="card-head">
          <span>治理问题清单（AI 自动识别重复 / 错误 / 缺失数据）</span>
          <el-tag v-if="governRows.length" type="danger" size="small">
            发现 {{ governRows.length }} 个问题
          </el-tag>
          <el-tag v-else type="success" size="small">暂未扫描</el-tag>
        </div>
      </template>
      <el-table :data="governRows" v-loading="scanning" stripe size="small" empty-text="点击「数据治理扫描」识别问题">
        <el-table-column prop="name" label="姓名" width="140" show-overflow-tooltip />
        <el-table-column label="问题类型" width="110">
          <template #default="{ row }">
            <el-tag :type="issueTag(row.issue_type)" size="small">{{ issueLabel(row.issue_type) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="field" label="问题字段" width="140" show-overflow-tooltip>
          <template #default="{ row }">{{ row.field || '—' }}</template>
        </el-table-column>
        <el-table-column prop="suggestion" label="整改建议" min-width="260" show-overflow-tooltip />
        <el-table-column label="操作" width="120" fixed="right">
          <template #default="{ row }">
            <el-button v-if="row.talent_id" link type="primary" @click="openMerge(row)">
              {{ row.issue_type === 'duplicate' ? '查重合并' : '查看' }}
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 查重合并 dialog -->
    <el-dialog v-model="mergeDlg.visible" title="查重合并" width="620" append-to-body>
      <template v-if="mergePrimary">
        <el-alert type="info" :closable="false" style="margin-bottom:12px">
          主档案：<b>{{ mergePrimary.name }}</b>（id={{ mergePrimary.id }}），勾选下方重复档案合并入主档案
        </el-alert>
        <el-table :data="mergeCandidates" size="small" max-height="360"
                  @selection-change="(sel) => (mergeSelected = sel)">
          <el-table-column type="selection" width="45" />
          <el-table-column prop="talent_id" label="ID" width="70" />
          <el-table-column prop="name" label="姓名" width="120" />
          <el-table-column prop="reason" label="重复依据" min-width="200" show-overflow-tooltip />
          <el-table-column label="相似度" width="90">
            <template #default="{ row }">
              <span v-if="row.similarity">{{ (row.similarity * 100).toFixed(0) }}%</span>
              <span v-else style="color:#9ca3af">—</span>
            </template>
          </el-table-column>
        </el-table>
        <div style="margin-top:14px;text-align:right">
          <el-button @click="mergeDlg.visible = false">取消</el-button>
          <el-button type="danger" :loading="merging" :disabled="!mergeSelected.length"
                     @click="doMerge">合并选中（{{ mergeSelected.length }} 条）</el-button>
        </div>
      </template>
    </el-dialog>

    <!-- 多维统计 dialog -->
    <el-dialog v-model="statsDlg.visible" title="人才多维统计" width="640" append-to-body>
      <div v-loading="statsLoading" style="min-height:200px">
        <div class="stat-grid" v-if="stats">
          <div class="stat"><div class="num">{{ stats.total }}</div><div class="lbl">人才总数</div></div>
          <div class="stat"><div class="num">{{ stats.expiring_count }}</div><div class="lbl">即将过期</div></div>
          <div class="stat"><div class="num">{{ eduTop }}</div><div class="lbl">主要学历</div></div>
          <div class="stat"><div class="num">{{ skillTop }}</div><div class="lbl">热门技能</div></div>
        </div>
        <template v-if="stats">
          <el-divider content-position="left">学历分布</el-divider>
          <el-progress v-for="(n, k) in stats.by_education" :key="k" :percentage="pct(n)" :format="() => `${k} ${n}人`"
                       style="margin-bottom:8px" :stroke-width="14" />
          <el-divider content-position="left">来源分布</el-divider>
          <div style="display:flex;gap:8px;flex-wrap:wrap">
            <el-tag v-for="(n, k) in stats.by_source" :key="k" effect="plain">
              {{ sourceLabel(k) }}：{{ n }} 人
            </el-tag>
          </div>
        </template>
      </div>
    </el-dialog>

    <!-- 过期提醒 dialog -->
    <el-dialog v-model="expiringDlg.visible" title="过期信息提醒（30 天内到期 / 已过期）" width="720" append-to-body>
      <el-table :data="expiringRows" v-loading="expiringDlg.loading" size="small" stripe max-height="420">
        <el-table-column prop="name" label="姓名" width="130" />
        <el-table-column prop="field" label="过期字段" width="130" />
        <el-table-column prop="expire_at" label="过期时间" width="180" />
        <el-table-column prop="days_left" label="剩余天数" width="100">
          <template #default="{ row }">
            <el-tag :type="(row.days_left ?? 0) < 0 ? 'danger' : 'warning'" size="small">
              {{ row.days_left < 0 ? `已过期 ${-row.days_left} 天` : `${row.days_left} 天` }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="suggestion" label="建议" min-width="200" show-overflow-tooltip />
      </el-table>
    </el-dialog>

    <!-- Excel 导入 dialog -->
    <el-dialog v-model="excelDlg.visible" title="Excel 批量导入" width="480" append-to-body>
      <el-upload drag :auto-upload="false" :limit="1" accept=".xlsx,.xls"
                 :on-change="onExcelChange" :file-list="excelFileList" style="margin-bottom:14px">
        <el-icon style="font-size:40px;color:#9ca3af"><UploadFilled /></el-icon>
        <div>拖拽或点击上传 Excel 文件（.xlsx）</div>
        <template #tip><div class="el-upload__tip">模板列：姓名/性别/手机/邮箱/最高学历/专业/当前职位/从业年限/技能/工作经历/项目经验/荣誉</div></template>
      </el-upload>
      <template #footer>
        <el-button @click="excelDlg.visible = false">取消</el-button>
        <el-button type="primary" :loading="excelDlg.loading" @click="doImportExcel">开始导入</el-button>
      </template>
    </el-dialog>

    <!-- Word 批量导入 dialog -->
    <el-dialog v-model="wordDlg.visible" title="Word 简历批量导入" width="480" append-to-body>
      <el-upload drag :auto-upload="false" :limit="1" accept=".docx,.doc"
                 :on-change="onWordChange" :file-list="wordFileList" style="margin-bottom:14px">
        <el-icon style="font-size:40px;color:#9ca3af"><UploadFilled /></el-icon>
        <div>拖拽或点击上传 Word 简历文件（.docx）</div>
      </el-upload>
      <template #footer>
        <el-button @click="wordDlg.visible = false">取消</el-button>
        <el-button type="primary" :loading="wordDlg.loading" @click="doImportWord">开始导入</el-button>
      </template>
    </el-dialog>
    <!-- 标准化整改结果 dialog -->
    <el-dialog v-model="repairDlg.visible" title="标准化整改结果" width="720" append-to-body>
      <el-alert type="success" :closable="false" style="margin-bottom:12px"
                title="已自动修复可判定的不规范数据项（学历/性别/手机号/邮箱/证件号/年限）" />
      <el-table :data="repairResult?.details || []" size="small" stripe max-height="420">
        <el-table-column prop="talent_id" label="ID" width="70" />
        <el-table-column prop="name" label="姓名" width="130" />
        <el-table-column prop="field" label="字段" width="150" />
        <el-table-column label="原值 → 新值" min-width="260" show-overflow-tooltip>
          <template #default="{ row }">
            <span style="color:#b45309;text-decoration:line-through">{{ row.from }}</span>
            <span style="margin:0 6px;color:#9ca3af">→</span>
            <span style="color:#16a34a">{{ row.to }}</span>
          </template>
        </el-table-column>
      </el-table>
      <template #footer>
        <el-button type="primary" @click="repairDlg.visible = false">知道了</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { MagicStick, Search, UploadFilled } from '@element-plus/icons-vue'
import {
  governanceScan, governanceRepair, findDuplicates, mergeTalents,
  talentStats, exportTalents, scanExpiring,
} from '@/api/talent'

// ---------- 治理扫描 ----------
const governRows = ref([])
const scanning = ref(false)
async function onGovern() {
  scanning.value = true
  try {
    const res = await governanceScan()
    const d = res.data || {}
    governRows.value = d.issues || []
    const bt = d.by_type || {}
    ElMessage.success(`扫描完成：共 ${d.total ?? governRows.value.length} 个问题` +
      `（缺失 ${bt.missing_field || 0} / 错误 ${bt.error || 0} / 重复 ${bt.duplicate || 0}）`)
  } catch (e) { /* 拦截器已提示 */ } finally { scanning.value = false }
}
const issueLabel = (t) => ({ duplicate: '重复', missing_field: '缺失', error: '错误', outdated: '过期' }[t] || t)
const issueTag = (t) => ({ duplicate: 'danger', missing_field: 'warning', error: 'danger', outdated: 'info' }[t] || 'info')

// ---------- 一键标准化整改 ----------
const repairing = ref(false)
const repairDlg = reactive({ visible: false })
const repairResult = ref(null)
async function onRepair() {
  try {
    await ElMessageBox.confirm(
      '将自动标准化修复可判定的数据项（学历/性别/手机号/邮箱/证件号/年限等），幂等安全，确认执行？',
      '一键标准化整改', { type: 'warning' })
  } catch { return }
  repairing.value = true
  try {
    const res = await governanceRepair({})
    repairResult.value = res.data
    repairDlg.visible = true
    ElMessage.success(`整改完成：修复 ${res.data?.repaired || 0} 项`)
    onGovern()
  } catch (e) { ElMessage.error('整改失败：' + (e.message || '')) } finally { repairing.value = false }
}

// ---------- 查重合并 ----------
const mergeDlg = reactive({ visible: false })
const mergePrimary = ref(null)
const mergeCandidates = ref([])
const mergeSelected = ref([])
const merging = ref(false)
async function openMerge(row) {
  try {
    const res = await findDuplicates(row.talent_id)
    mergePrimary.value = { id: res.data.talent_id, name: res.data.name }
    mergeCandidates.value = res.data.candidates || []
    mergeSelected.value = []
    mergeDlg.visible = true
  } catch (e) { ElMessage.error('查重失败：' + (e.message || '')) }
}
async function doMerge() {
  if (!mergeSelected.value.length) return ElMessage.warning('请勾选待合并的重复档案')
  try {
    await ElMessageBox.confirm(
      `将把选中的 ${mergeSelected.value.length} 条档案合并到「${mergePrimary.value.name}」主档案，确认？`,
      '合并确认', { type: 'warning' })
  } catch { return }
  merging.value = true
  try {
    const res = await mergeTalents({
      primary_id: mergePrimary.value.id,
      duplicate_ids: mergeSelected.value.map((c) => c.talent_id),
    })
    ElMessage.success(res.data?.message || '合并成功')
    mergeDlg.visible = false
    onGovern()
  } catch (e) { ElMessage.error('合并失败：' + (e.message || '')) } finally { merging.value = false }
}

// ---------- 多维统计 ----------
const statsDlg = reactive({ visible: false })
const stats = ref(null)
const statsLoading = ref(false)
async function onStats() {
  statsDlg.visible = true
  statsLoading.value = true
  try {
    const res = await talentStats()
    stats.value = res.data
  } finally { statsLoading.value = false }
}
const pct = (n) => (stats.value?.total ? Math.round((n / stats.value.total) * 100) : 0)
const eduTop = computed(() => {
  const m = stats.value?.by_education || {}
  const k = Object.keys(m)[0]
  return k ? `${k}` : '—'
})
const skillTop = computed(() => {
  const m = stats.value?.by_skill || {}
  const k = Object.keys(m)[0]
  return k ? `${k}` : '—'
})
const sourceLabel = (s) => ({ manual: '人工录入', import: '批量导入', text: '文本解析', agent_parsed: 'AI 智能解析' }[s] || s)

// ---------- 过期提醒 ----------
const expiringDlg = reactive({ visible: false })
const expiringRows = ref([])
async function onExpiring() {
  expiringDlg.visible = true
  expiringDlg.loading = true
  try {
    const res = await scanExpiring(30)
    expiringRows.value = res.data || []
  } catch (e) { ElMessage.error('获取过期提醒失败：' + (e.message || '')) } finally { expiringDlg.loading = false }
}

// ---------- Excel / Word 导入 ----------
const excelDlg = reactive({ visible: false, loading: false })
const excelFileList = ref([])
const excelFile = ref(null)
const onExcelChange = (f) => { excelFile.value = f.raw }
async function doImportExcel() {
  if (!excelFile.value) return ElMessage.warning('请先选择 Excel 文件')
  excelDlg.loading = true
  try {
    const res = await importExcel(excelFile.value)
    const d = res.data || {}
    ElMessage.success(`导入成功 ${d.imported || 0} 条，跳过 ${d.skipped || 0} 条`)
    excelDlg.visible = false
    excelFileList.value = []
    excelFile.value = null
  } catch (e) { /* 拦截器已提示 */ } finally { excelDlg.loading = false }
}
const wordDlg = reactive({ visible: false, loading: false })
const wordFileList = ref([])
const wordFile = ref(null)
const onWordChange = (f) => { wordFile.value = f.raw }
async function doImportWord() {
  if (!wordFile.value) return ElMessage.warning('请先选择 Word 文件')
  wordDlg.loading = true
  try {
    const res = await importWord(wordFile.value)
    const d = res.data || {}
    ElMessage.success(`导入成功 ${d.imported || 0} 条，跳过 ${d.skipped || 0} 条`)
    wordDlg.visible = false
    wordFileList.value = []
    wordFile.value = null
  } catch (e) { /* 拦截器已提示 */ } finally { wordDlg.loading = false }
}

// ---------- 导出 ----------
const exporting = ref(false)
async function onExport() {
  exporting.value = true
  try {
    const blob = await exportTalents()
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `人才档案导出_${new Date().toISOString().slice(0, 10)}.xlsx`
    document.body.appendChild(a)
    a.click()
    a.remove()
    URL.revokeObjectURL(url)
    ElMessage.success('导出成功')
  } catch (e) { ElMessage.error('导出失败：' + (e.message || '')) } finally { exporting.value = false }
}
</script>

<style scoped>
.page { padding: 4px 2px; }
.toolbar { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; flex-wrap: wrap; gap: 10px; }
.title { font-size: 16px; font-weight: 600; color: #1f2937; }
.card-head { display: flex; align-items: center; gap: 10px; }
.stat-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px; margin-bottom: 6px; }
.stat { border: 1px solid #eef1f5; border-radius: 10px; text-align: center; padding: 16px 0; background: #fcfcfd; }
.num { font-size: 22px; font-weight: 600; color: #374151; }
.lbl { font-size: 12px; color: #9ca3af; margin-top: 4px; }
</style>
