import { ref } from 'vue'
import { useMessage } from 'naive-ui'
import { exportGradeReport, downloadBlob } from '../api/analytics'

export function useReportExport() {
  const message = useMessage()
  const exporting = ref(false)

  async function handleDownload(examId, subjectId, format) {
    if (!examId || !subjectId) {
      message.warning('请选择 1 次考试 + 1 个科目后再导出')
      return
    }
    exporting.value = true
    try {
      const resp = await exportGradeReport(examId, subjectId, format)
      downloadBlob(resp, `年级报告.${format}`)
    } catch (e) {
      message.error(e.response?.data?.detail || '导出失败')
    } finally {
      exporting.value = false
    }
  }

  async function exportStudentRank(examId, subjectId) {
    if (!examId || !subjectId) {
      message.warning('请先选择导出科目')
      return
    }
    exporting.value = true
    try {
      const resp = await exportGradeReport(examId, subjectId, 'xlsx')
      downloadBlob(resp, '学生排名.xlsx')
    } catch (e) {
      message.error(e.response?.data?.detail || '导出失败')
    } finally {
      exporting.value = false
    }
  }

  return { exporting, handleDownload, exportStudentRank }
}
