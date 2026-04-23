interface RequestOptions {
  method?: string
  body?: any
  query?: Record<string, any>
  responseType?: string
}

export class AuthError extends Error {
  public status: number
  constructor(status: number, message: string) {
    super(message)
    this.name = 'AuthError'
    this.status = status
  }
}

export function useApi() {
  const token = useCookie('edu_token')
  const config = useRuntimeConfig()

  async function request<T = any>(
    path: string,
    opts: RequestOptions = {},
  ): Promise<T> {
    const { method = 'GET', body, query, ...rest } = opts
    return $fetch<T>(path, {
      baseURL: config.public.apiBase + '/api/v1',
      method: method as any,
      headers: token.value
        ? { Authorization: `Bearer ${token.value}` }
        : {},
      body,
      query,
      ...rest,
    })
  }

  return {
    // === Auth (已有后端端点) ===
    login: (phone: string, password: string) =>
      request('/auth/login', { method: 'POST', body: { username: phone, password } }),
    switchRole: (roleId: string) =>
      request('/auth/switch-role', { method: 'POST', body: { role_id: roleId } }),

    // === Menu (本 Phase 新增) ===
    getMenus: async () => {
      try {
        return await request<{ menus: any[] }>('/menus')
      } catch (err: any) {
        const status = err?.response?.status ?? err?.statusCode ?? err?.status
        if (status === 401 || status === 403) {
          throw new AuthError(status, 'auth failed on getMenus')
        }
        throw err
      }
    },

    // === Exam ===
    getExams: (params?: Record<string, any>) => request('/exams', { query: params }),
    getExam: (id: string) => request(`/exams/${id}`),
    createExam: (data: any) => request('/exams', { method: 'POST', body: data }),

    // === Analytics ===
    getExamSummary: (examId: string, params?: Record<string, any>) =>
      request(`/analytics/exam/${examId}/summary`, { query: params }),
    getSubjectSummary: (subjectId: string, params?: Record<string, any>) =>
      request(`/analytics/subject/${subjectId}/summary`, { query: params }),
    getExamDistribution: (examId: string, params?: Record<string, any>) =>
      request(`/analytics/exam/${examId}/distribution`, { query: params }),
    getSubjectDistribution: (subjectId: string, params?: Record<string, any>) =>
      request(`/analytics/subject/${subjectId}/distribution`, { query: params }),
    getSubjectQuestions: (subjectId: string, params?: Record<string, any>) =>
      request(`/analytics/subject/${subjectId}/questions`, { query: params }),
    getExamGradeAggregates: (examId: string, params?: Record<string, any>) =>
      request(`/analytics/exam/${examId}/grade-aggregates`, { query: params }),
    getScoreSegments: () => request('/analytics/segments/config'),
    getAnalyticsReportTrendGrade: (params?: Record<string, any>) =>
      request('/analytics/report/trend/grade', { query: params }),
    getAnalyticsReportTrendClass: (params?: Record<string, any>) =>
      request('/analytics/report/trend/class', { query: params }),
    getAnalyticsReportTrendStudent: (params?: Record<string, any>) =>
      request('/analytics/report/trend/student', { query: params }),

    getPowerOptions: (params?: Record<string, any>) =>
      request('/analytics/power-options', { query: params }),

    // === Homework ===
    getHomeworkList: (params?: Record<string, any>) =>
      request('/homework/tasks', { query: params }),
    createHomework: (data: any) =>
      request('/homework/tasks', { method: 'POST', body: data }),
    getSubmissions: (taskId: string) =>
      request(`/homework/tasks/${taskId}/submissions`),
    gradeSubmission: (taskId: string, subId: string, data: any) =>
      request(`/homework/tasks/${taskId}/submissions/${subId}/grade`, { method: 'POST', body: data }),

    // === Knowledge ===
    getKnowledgeTree: (params?: Record<string, any>) =>
      request('/knowledge-tree/graph', { query: params }),
    searchKnowledge: (params?: Record<string, any>) =>
      request('/knowledge-tree/search', { query: params }),
    searchQuestions: (params?: Record<string, any>) =>
      request('/bank/questions', { query: params }),

    // === BaseInfo ===
    getStudents: (params?: Record<string, any>) => request('/students', { query: params }),
    getClasses: (params?: Record<string, any>) => request('/classes', { query: params }),

    // === Profile ===
    getStudentTrend: (studentId: string, params?: Record<string, any>) =>
      request(`/profile/students/${studentId}/trend`, { query: params }),
    getStudentKnowledge: (studentId: string, params?: Record<string, any>) =>
      request(`/profile/students/${studentId}/knowledge`, { query: params }),

    // === AI ===
    chatStream: (message: string, sessionId?: string) =>
      $fetch('/api/v1/ai/chat', {
        baseURL: config.public.apiBase,
        method: 'POST',
        body: { message, session_id: sessionId },
        responseType: 'stream' as any,
        headers: token.value ? { Authorization: `Bearer ${token.value}` } : {},
      }),

    // === Dashboard ===
    getDashboardSummary: () => request('/dashboard/summary'),

    // === Level Score ===
    convertLevelScore: (data: any) =>
      request('/analytics/level-score/convert', { method: 'POST', body: data }),

    // === Report ===
    queryReport: (data: any) =>
      request('/analytics/report/query', { method: 'POST', body: data }),
    upsertSegmentsConfig: (data: any) =>
      request('/analytics/segments/config', { method: 'PUT', body: data }),
    deleteSegmentOverride: (subjectCode: string) =>
      request(`/analytics/segments/config/${subjectCode}`, { method: 'DELETE' }),

    // === Advanced Analytics ===
    getQuestionInsights: (examId: string, subjectId?: string) =>
      request('/analytics/exam/' + examId + '/question-insights', { query: { subject_id: subjectId } }),
    getExamDiagnosis: (examId: string, subjectId?: string, classId?: string) =>
      request('/analytics/exam/' + examId + '/diagnosis', { query: { subject_id: subjectId, class_id: classId } }),
    getStudentRankings: (examId: string, subjectId?: string, classId?: string) =>
      request('/analytics/exam/' + examId + '/student-rankings', { query: { subject_id: subjectId, class_id: classId } }),
    getCriticalStudents: (examId: string, subjectId?: string, classId?: string, threshold?: number) =>
      request('/analytics/exam/' + examId + '/critical-students', { query: { subject_id: subjectId, class_id: classId, threshold } }),
    getStudentAiDiagnosis: (studentId: string, examId?: string, subjectId?: string) =>
      request('/profile/students/' + studentId + '/ai-diagnosis', { query: { exam_id: examId, subject_code: subjectId } }),
    getClassBoxplot: (examId: string, subjectId?: string) =>
      request('/analytics/exam/' + examId + '/class-boxplot', { query: { subject_id: subjectId } }),
    getClassKnowledge: (examId: string, subjectId?: string) =>
      request('/analytics/exam/' + examId + '/class-knowledge', { query: { subject_id: subjectId } }),
    getClassErrorPatterns: (examId: string, subjectId?: string) =>
      request('/analytics/exam/' + examId + '/class-error-patterns', { query: { subject_id: subjectId } }),

    // === Raw ===
    raw: request,
    token,
  }
}
