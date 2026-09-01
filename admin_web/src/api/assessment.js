import http from '@/utils/request'

// 题库
export function listBanks(params) { return http.get('/assessment/banks', { params }) }
export function createBank(data) { return http.post('/assessment/banks', data) }
export function updateBank(id, data) { return http.put(`/assessment/banks/${id}`, data) }
export function deleteBank(id) { return http.delete(`/assessment/banks/${id}`) }
export function listBankQuestions(bankId, params) { return http.get(`/assessment/banks/${bankId}/questions`, { params }) }

// 题目
export function listQuestions(params) { return http.get('/assessment/banks/0/questions', { params }) }
export function createQuestion(data) { return http.post('/assessment/questions', data) }
export function updateQuestion(id, data) { return http.put(`/assessment/questions/${id}`, data) }
export function deleteQuestion(id) { return http.delete(`/assessment/questions/${id}`) }

// 试卷
export function listPapers(params) { return http.get('/assessment/papers', { params }) }
export function getPaper(id) { return http.get(`/assessment/papers/${id}`) }
export function createPaper(data) { return http.post('/assessment/papers', data) }
export function createPaperAuto(data) { return http.post('/assessment/papers/auto', data) }
export function updatePaper(id, data) { return http.put(`/assessment/papers/${id}`, data) }
export function deletePaper(id) { return http.delete(`/assessment/papers/${id}`) }

// 发起 + 作答 + 判分
export function launchAssessment(data) { return http.post('/assessment/launch', data) }
export function listResults(params) { return http.get('/assessment/results', { params }) }
export function getResult(id) { return http.get(`/assessment/results/${id}`) }
export function getAnswerView(id) { return http.get(`/assessment/results/${id}/answer`) }
export function submitAnswer(id, data) { return http.post(`/assessment/results/${id}/submit`, data) }
export function getReport(id) { return http.get(`/assessment/results/${id}/report`) }
export function getAssessmentStats() { return http.get('/assessment/stats') }
