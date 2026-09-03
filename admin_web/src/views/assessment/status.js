export const assessmentResultStatus = {
  0: { label: '未答', type: 'info' },
  1: { label: '答题中', type: 'warning' },
  2: { label: '已交卷', type: 'primary' },
  3: { label: '报告已生成', type: 'success' },
}

export const assessmentStatusMeta = (status) => (
  assessmentResultStatus[status] || { label: '未知状态', type: 'info' }
)

export const trainingLinkStatus = {
  pending: { label: '待处理', type: 'warning' },
  sent: { label: '已联动', type: 'success' },
  failed: { label: '联动失败', type: 'danger' },
}

export const trainingStatusMeta = (status) => (
  trainingLinkStatus[status] || { label: '未知状态', type: 'info' }
)
