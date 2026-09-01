import http from '@/utils/request'

export function listBanks(params) {
  return http.get('/assessment/banks', { params })
}

export function createBank(data) {
  return http.post('/assessment/banks', data)
}

export function updateBank(id, data) {
  return http.put(`/assessment/banks/${id}`, data)
}

export function deleteBank(id) {
  return http.delete(`/assessment/banks/${id}`)
}

export function listQuestions(params) {
  return http.get('/assessment/questions', { params })
}

export function listBankQuestions(bankId) {
  return http.get(`/assessment/banks/${bankId}/questions`)
}

export function createQuestion(data) {
  return http.post('/assessment/questions', data)
}

export function updateQuestion(id, data) {
  return http.put(`/assessment/questions/${id}`, data)
}

export function deleteQuestion(id) {
  return http.delete(`/assessment/questions/${id}`)
}

export function downloadQuestionImportTemplate() {
  return http.get('/assessment/questions/import-template', { responseType: 'blob' })
}

export function importQuestions(bankId, file) {
  const form = new FormData()
  form.append('bank_id', bankId)
  form.append('file', file)
  return http.post('/assessment/questions/import', form)
}

export function listPapers(params) {
  return http.get('/assessment/papers', { params })
}

export function getPaper(id) {
  return http.get(`/assessment/papers/${id}`)
}

export function createPaper(data) {
  return http.post('/assessment/papers', data)
}

export function updatePaper(id, data) {
  return http.put(`/assessment/papers/${id}`, data)
}

export function deletePaper(id) {
  return http.delete(`/assessment/papers/${id}`)
}

export function listAssessmentPositions() {
  return http.get('/assessment/positions')
}

export function listCapabilityModels(params) {
  return http.get('/assessment/capability-models', { params })
}

export function createCapabilityModel(data) {
  return http.post('/assessment/capability-models', data)
}

export function updateCapabilityModel(id, data) {
  return http.put(`/assessment/capability-models/${id}`, data)
}

export function deleteCapabilityModel(id) {
  return http.delete(`/assessment/capability-models/${id}`)
}

export function launchAssessment(data) {
  return http.post('/assessment/launch', data)
}

export function listResults(params) {
  return http.get('/assessment/results', { params })
}

export function listAssessmentBatches(params) {
  return http.get('/assessment/batches', { params })
}

export function getAssessmentBatch(id) {
  return http.get(`/assessment/batches/${id}`)
}

export function getStatistics(params) {
  return http.get('/assessment/results/statistics', { params })
}

export function getQuestionStatistics(params) {
  return http.get('/assessment/results/statistics/questions', { params })
}

export function getBatchStatistics(params) {
  return http.get('/assessment/results/statistics/batches', { params })
}

export function getResult(id) {
  return http.get(`/assessment/result/${id}`)
}

export function getReport(id) {
  return http.get(`/assessment/result/${id}/report`)
}

export function getAgentTask(id) {
  return http.get(`/assessment/agent-tasks/${id}`)
}

export function linkTraining(id) {
  return http.post(`/assessment/result/${id}/link-training`)
}

export function getTrainingLink(id) {
  return http.get(`/assessment/result/${id}/training-link`)
}

export function retryTrainingLink(id) {
  return http.post(`/assessment/result/${id}/training-link/retry`)
}
