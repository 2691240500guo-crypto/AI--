// hq新增内容 - 人才档案批次1
// 与后端 app/routers/talent.py 严格对齐；后来者参照 src/api/user.js 同款风格
import http from '@/utils/request'

export function listTalents(params) {
  // params: { page, page_size, keyword, status, source }
  return http.get('/talent', { params })
}

export function getTalent(id) {
  return http.get(`/talent/${id}`)
}

export function createTalent(data) {
  return http.post('/talent', data)
}

export function updateTalent(id, data) {
  return http.put(`/talent/${id}`, data)
}

export function deleteTalent(id) {
  return http.delete(`/talent/${id}`)
}

// ============ hq+  批次2.1 标签相关 ============

// 标签字典（与后端 /talent-dicts 对应）
export function listTalentDicts(params) {
  // params: { type, keyword, only_enabled }
  return http.get('/talent-dicts', { params })
}
export function createTalentDict(data) {
  return http.post('/talent-dicts', data)
}
export function updateTalentDict(id, data) {
  return http.put(`/talent-dicts/${id}`, data)
}
export function deleteTalentDict(id) {
  return http.delete(`/talent-dicts/${id}`)
}

// 人才 ↔ 标签关联（与后端 /talent/:id/tags 对应）
export function listTalentTags(talentId) {
  return http.get(`/talent/${talentId}/tags`)
}
// 覆盖式绑定：传 { tag_ids: [1,2,3], source: 'manual' }
export function bindTalentTags(talentId, body) {
  return http.put(`/talent/${talentId}/tags`, body)
}

// ============ hq+  批次2.3a 简历上传 ============
// 后端：POST /api/v1/resume/upload（multipart/form-data）
//
// hq+  修复：上传会触发「抽文本 + LLM 抽取 + 向量化」长链路，
//      实测 CPU 跑 qwen3:1.7b 模型需要 130-160 秒，远超 request.js 默认 15 秒。
//      axios 单接口 timeout 覆盖：传一个大数（5 分钟）。
export function uploadResume(file, onProgress) {
  const form = new FormData()
  form.append('file', file)
  return http.post('/resume/upload', form, {
    timeout: 5 * 60 * 1000,  // hq+  5 分钟，覆盖 LLM 抽取耗时
    onUploadProgress: (e) => {
      if (onProgress && e.total) onProgress(Math.round((e.loaded * 100) / e.total))
    },
  })
}

// ============ hq+  批次2.3b 重跑 AI 解析 ============
// reparse 也会调 LLM，同样需要长 timeout
export function getTalentReport(id) {
  return http.get(`/talent/${id}/report`)
}
export function reparseTalent(id) {
  // POST /api/v1/talent/:id/reparse
  return http.post(`/talent/${id}/reparse`, {}, { timeout: 5 * 60 * 1000 })
}

// ============ hq+  批次2.3c Milvus 向量 + 语义搜索 + 档案问答 ============
// 单独把某人才向量入 Milvus（批次B 起写三维：技能/经验/素质）
export function vectorizeTalent(id) {
  return http.post(`/talent/${id}/vectorize`, {})
}
// hq+  批次B：查看某人才三维向量画像（text 预览）
export function getTalentVectors(id) {
  return http.get(`/talent/${id}/vectors`)
}
// 自然语言语义搜索人才（袁文武 POST /talent/search，body: query/top_k/use_vector）
export function semanticSearchTalent(q, topK = 10, dimension = 'skill') {
  return http.post('/talent/search', { query: q, top_k: topK, use_vector: true })
}
// 针对单个人才做 RAG 问答（自然语言问题 → LLM 基于其画像字段回答）
export function askTalentQA(id, question) {
  return http.post(`/talent/${id}/qa`, { question })
}

// ============ hq+  批次补充：附件简历 下载 / 在线预览 ============
// 后端 GET /talent/:id/resume 返回原始字节流（带 Authorization）。
// 前端用 blob 处理，避免 iframe 无法带 token 的问题。
// inline=1 → 预览（objectURL）；inline=0 → 下载
export function fetchResumeBlob(id, inline = false) {
  return http.get(`/talent/${id}/resume`, {
    params: inline ? { inline: 1 } : {},
    responseType: 'blob',
    timeout: 60000,
  })
}
// 便捷：下载为文件（取 blob → <a download>）
export function downloadResume(id, filename) {
  return fetchResumeBlob(id, false).then((blob) => {
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = filename || 'resume.pdf'
    document.body.appendChild(a)
    a.click()
    a.remove()
    URL.revokeObjectURL(url)
  })
}
// 便捷：在线预览（返回 objectURL）
export function previewResume(id) {
  return fetchResumeBlob(id, true).then((blob) => URL.createObjectURL(blob))
}

// ============ hq+  批次C：人才去重（上传弹框人工确认后覆盖） ============
// 确认重复：用新简历覆盖旧档案
export function mergeOverwrite(newId, oldId) {
  return http.post('/talent/merge-overwrite', null, {
    params: { new_id: newId, old_id: oldId },
  })
}

// ============ hq+  合并袁文武功能：解析/画像/查重/治理/RAG/Excel/统计/导出/过期 ============

// ---- Agent① 简历智能解析（上传+解析一步到位，PDF/Word/图片）----
export function parseResume(file) {
  const fd = new FormData()
  fd.append('file', file)
  return http.post('/talent/parse', fd, { timeout: 5 * 60 * 1000 })
}
// 批量解析（多文件）
export function parseResumeBatch(files) {
  const fd = new FormData()
  files.forEach((f) => fd.append('files', f))
  return http.post('/talent/parse-batch', fd, { timeout: 10 * 60 * 1000 })
}

// ---- 需求② 向量级画像：生成 AI 数字画像（标签+三维向量+潜力评级）----
export function buildProfile(id) {
  return http.post(`/talent/${id}/portrait`, {}, { timeout: 5 * 60 * 1000 })
}

// ---- 需求③ 智能查重与数据治理 ----
// 对某人才查重（向量+身份识别）
export function findDuplicates(id) {
  return http.get(`/talent/${id}/duplicates`)
}
// 一键合并重复档案 { primary_id, duplicate_ids: [] }
export function mergeTalents(data) {
  return http.post('/talent/merge', data)
}
// 数据治理扫描（识别重复/错误/缺失数据 + 整改建议）
export function governanceScan() {
  return http.post('/talent/governance/scan', {})
}
// hq+ 一键标准化整改：自动修复学历/性别/手机号/邮箱等不规范项（{ talent_ids? }）
export function governanceRepair(body) {
  return http.post('/talent/governance/repair', body || {})
}
// 过期信息提醒（expire_at 距今 <=days 天）
export function scanExpiring(days = 30) {
  return http.get('/talent/expiring', { params: { days } })
}

// ---- 需求⑤ 档案 RAG 问答 ----
// { question, scope: 'single'|'batch', top_k, talent_id?, talent_ids? }
export function ragAsk(data) {
  return http.post('/talent/rag', data, { timeout: 5 * 60 * 1000 })
}

// ---- 内置标签库播种（幂等，已存在跳过）----
export function seedTags() {
  return http.post('/talent/tags/seed', {})
}

// ---- T-2 Excel 批量导入 / T-4 导出 / 统计 ----
export function importExcel(file) {
  const fd = new FormData()
  fd.append('file', file)
  return http.post('/talent/import-excel', fd, { timeout: 5 * 60 * 1000 })
}
export function importWord(file) {
  const fd = new FormData()
  fd.append('file', file)
  return http.post('/talent/import-word', fd, { timeout: 5 * 60 * 1000 })
}
export function talentStats() {
  return http.get('/talent/stats')
}
// 一键导出 .xlsx（blob）
export function exportTalents() {
  return http.get('/talent/export', { responseType: 'blob', timeout: 120000 })
}

// ---- 证书管理 ----
export function listCertificates(talentId) {
  return http.get(`/talent/${talentId}/certificates`)
}
export function saveCertificates(talentId, certs) {
  return http.put(`/talent/${talentId}/certificates`, certs)
}
