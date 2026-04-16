export const useContextStore = defineStore('context', {
  state: () => ({
    schoolYear: '',
    semester: '',
  }),

  actions: {
    setSchoolYear(year: string) {
      this.schoolYear = year
    },
    setSemester(semester: string) {
      this.semester = semester
    },
  },
})
