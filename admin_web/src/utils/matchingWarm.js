// 保温红绿灯共用工具（Result / Alert 展示完全一致）
// 4 态：⏳待激活(灰) ❄️冷却(红) 🔥火热(绿) 🟡常温(黄)

export function warmLabel(r) {
  return { 0: '无', 1: '低', 2: '中', 3: '高' }[(r && r.warm_level)] ?? '无'
}

export function fmtTime(t) {
  return t ? String(t).replace('T', ' ').slice(0, 19) : ''
}

export function daysSince(t) {
  if (!t) return Infinity
  const ts = new Date(String(t).replace(' ', 'T')).getTime()
  return Number.isFinite(ts) ? (Date.now() - ts) / 86400000 : Infinity
}

// 展示态唯一映射（顺序：无保温且从未跟进→灰；有保温但从未跟进/超14天→红；
// 近7天且保温≥中→绿；其余→黄）
export function warmState(row) {
  const days = daysSince(row && row.last_follow_up)
  const w = (row && row.warm_level) || 0
  if (w === 0 && !(row && row.last_follow_up)) return { label: '⏳ 待激活', type: 'info' }
  if (!(row && row.last_follow_up) || days > 14) return { label: '❄️ 冷却', type: 'danger' }
  if (days <= 7 && w >= 2) return { label: '🔥 火热', type: 'success' }
  return { label: '🟡 常温', type: 'warning' }
}

export function warmMeta(row) {
  if (!row || !row.last_follow_up) {
    return (row && row.warm_level) ? '有保温但从未跟进' : '未开始保温'
  }
  const days = daysSince(row.last_follow_up)
  const ago = days < 1 ? '今天跟进' : `${Math.floor(days)} 天前跟进`
  return `${ago} · 等级${warmLabel(row)}`
}
