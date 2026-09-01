<script setup>
import { onMounted, reactive, ref } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { launchAssessment, listPapers } from '@/api/assessment'
import { listTalents } from '@/api/talent'

const route = useRoute()
const papers = ref([])
const talents = ref([])
const tLoading = ref(false)
const form = reactive({ paper_id: null, talent_ids: [] })
const selectedTalents = ref([])

async function loadPapers() {
  const res = await listPapers({ page_size: 200 })
  papers.value = res.data.items
}

async function loadTalents(keyword) {
  tLoading.value = true
  try {
    const res = await listTalents({ keyword: keyword || '', page_size: 100 })
    talents.value = res.data.items
  } finally { tLoading.value = false }
}

async function launch() {
  if (!form.paper_id) return ElMessage.warning('请选择试卷')
  if (!form.talent_ids.length) return ElMessage.warning('请选择参与人才')
  await launchAssessment(form)
  ElMessage.success(`已为 ${form.talent_ids.length} 位人才发起测评`)
  form.talent_ids = []
  selectedTalents.value = []
}

onMounted(async () => {
  await loadPapers()
  await loadTalents()
  if (route.query.paper_id) form.paper_id = Number(route.query.paper_id)
})
</script>

<template>
  <el-card>
    <el-alert title="发起测评：选择一张试卷和参与人才，系统会为每人创建一条测评批次并推送消息。" type="info" :closable="false" style="margin-bottom:16px" />
    <el-form :model="form" label-width="100px" style="max-width:640px">
      <el-form-item label="试卷">
        <el-select v-model="form.paper_id" placeholder="选择试卷" style="width:100%">
          <el-option v-for="p in papers" :key="p.id" :label="`${p.title}（${p.question_count}题 / ${p.total_score}分）`" :value="p.id" />
        </el-select>
      </el-form-item>
      <el-form-item label="参与人才">
        <div style="width:100%">
          <el-input placeholder="按姓名/手机号搜索人才" clearable style="margin-bottom:8px" @keyup.enter="loadTalents($event.target.value)" @clear="loadTalents('')" />
          <el-table :data="talents" v-loading="tLoading" max-height="340" border @selection-change="(sel) => { form.talent_ids = sel.map(s => s.id); selectedTalents = sel }">
            <el-table-column type="selection" width="44" />
            <el-table-column prop="id" label="ID" width="60" />
            <el-table-column prop="name" label="姓名" />
            <el-table-column prop="phone" label="手机号" width="140" />
            <el-table-column prop="level" label="等级" width="70" />
          </el-table>
        </div>
      </el-form-item>
      <el-form-item>
        <el-button type="primary" :disabled="!form.paper_id || !form.talent_ids.length" @click="launch">
          发起测评（已选 {{ form.talent_ids.length }} 人）
        </el-button>
      </el-form-item>
    </el-form>
  </el-card>
</template>
