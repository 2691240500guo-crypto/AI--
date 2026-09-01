// hq新增内容 - 在线学习批次3
// 与后端 app/routers/course.py 严格对齐
import http from '@/utils/request'

// ===== 视频管理 =====
// 上传视频（multipart，大文件长超时）
export function uploadCourseVideo(file, onProgress) {
  const fd = new FormData()
  fd.append('file', file)
  fd.append('title', file.name)
  return http.post('/course/videos/upload', fd, {
    timeout: 10 * 60 * 1000,  // 10 分钟（大视频）
    onUploadProgress: (e) => {
      if (onProgress && e.total) onProgress(Math.round((e.loaded * 100) / e.total))
    },
  })
}
// 视频列表
export function listCourseVideos(params = {}) {
  return http.get('/course/videos', { params })
}
// 由视频生成课程 → 返回 course_id
export function generateCourseFromVideo(videoId) {
  return http.post(`/course/videos/${videoId}/course`, {})
}
// 视频流播放地址（带 token，video 标签 src 直接用）
export function videoStreamUrl(videoId) {
  const token = sessionStorage.getItem('token') || ''
  const base = (import.meta.env.VITE_API_BASE || '').replace(/\/api\/v1$/, '')
  // 若配置了 VITE_API_BASE 则直连后端；否则走 vite proxy（相对路径）
  return `${base}/api/v1/course/videos/${videoId}/stream?token=${encodeURIComponent(token)}`
}

// ===== 课程列表 =====
export function listCourses(params = {}) {
  return http.get('/course/courses', { params })
}

// ===== 学习进度 =====
// 上报进度（播放器定时调）
export function reportCourseProgress(courseId, position, duration) {
  return http.post('/course/progress', { course_id: courseId, position, duration })
}
// 我的学习进度页
export function getMyCourseProgress() {
  return http.get('/course/progress')
}
