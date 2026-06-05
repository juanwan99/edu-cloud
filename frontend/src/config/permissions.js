// 镜像后端 core/permissions.py ROLE_PERMISSIONS，值使用小写
// 教师基线权限（班主任/科任/备课组长共享）
const _TEACHER_BASE = [
  'view_students', 'view_exams', 'view_scores', 'view_question_bank',
  'view_grading', 'view_homework', 'manage_homework', 'generate_report',
  'use_ai_chat', 'write_paper', 'view_knowledge_tree', 'edit_knowledge_tree',
  'view_conduct', 'manage_conduct',
]

export const ROLE_PERMISSIONS = {
  platform_admin: [
    'manage_schools', 'view_schools', 'manage_school_config', 'manage_scheduling', 'impersonate_roles',
    'manage_teachers', 'manage_exams', 'create_joint_exam', 'manage_joint_exam', 'view_joint_exam',
    'view_cross_school_analytics', 'manage_question_bank', 'view_question_bank',
    'manage_users', 'manage_platform', 'view_students', 'view_exams', 'view_scores',
    'generate_report', 'generate_notification', 'approve_notification', 'send_notification',
    'use_ai_chat', 'write_paper', 'import_exams', 'manage_grading', 'view_grading',
    'manage_exam_results', 'manage_homework', 'view_homework',
    'view_knowledge_tree', 'edit_knowledge_tree',
    'view_conduct', 'manage_conduct', 'manage_conduct_rules', 'manage_conduct_parents', 'export_conduct'],
  district_admin: [
    'manage_schools', 'view_schools', 'manage_school_config', 'manage_scheduling',
    'manage_teachers', 'manage_exams', 'create_joint_exam', 'manage_joint_exam', 'view_joint_exam',
    'view_cross_school_analytics', 'view_question_bank', 'manage_users',
    'view_students', 'view_exams', 'view_scores', 'generate_report',
    'approve_notification', 'send_notification', 'generate_notification',
    'use_ai_chat', 'manage_grading', 'view_grading', 'manage_exam_results',
    'manage_homework', 'view_homework', 'view_knowledge_tree', 'edit_knowledge_tree',
    'view_conduct', 'manage_conduct', 'manage_conduct_rules', 'manage_conduct_parents', 'export_conduct'],
  school_admin: [
    'view_schools', 'manage_school_config', 'manage_teachers', 'manage_scheduling', 'manage_exams', 'import_exams',
    'create_joint_exam', 'manage_joint_exam', 'view_joint_exam',
    'view_cross_school_analytics', 'view_question_bank',
    'view_students', 'view_exams', 'view_scores', 'generate_report',
    'approve_notification', 'send_notification', 'generate_notification',
    'use_ai_chat', 'manage_grading', 'view_grading', 'manage_exam_results',
    'manage_homework', 'view_homework', 'view_knowledge_tree', 'edit_knowledge_tree',
    'view_conduct', 'export_conduct'],
  principal: [
    'view_schools', 'manage_school_config', 'manage_teachers', 'manage_scheduling', 'manage_exams',
    'create_joint_exam', 'manage_joint_exam', 'view_joint_exam',
    'view_cross_school_analytics', 'view_question_bank',
    'view_students', 'view_exams', 'view_scores', 'generate_report',
    'approve_notification', 'send_notification', 'generate_notification',
    'use_ai_chat', 'manage_grading', 'view_grading', 'manage_exam_results',
    'manage_homework', 'view_homework', 'view_knowledge_tree', 'edit_knowledge_tree',
    'view_conduct', 'export_conduct'],
  academic_director: [
    'view_schools', 'manage_scheduling', 'manage_teachers', 'manage_exams', 'import_exams',
    'create_joint_exam', 'manage_joint_exam', 'view_joint_exam',
    'view_cross_school_analytics', 'manage_question_bank', 'view_question_bank',
    'view_students', 'view_exams', 'view_scores', 'generate_report',
    'generate_notification', 'send_notification', 'use_ai_chat',
    'manage_grading', 'view_grading', 'manage_exam_results',
    'manage_homework', 'view_homework', 'view_knowledge_tree', 'edit_knowledge_tree',
    'view_conduct', 'manage_conduct', 'manage_conduct_rules', 'export_conduct'],
  teaching_research_leader: [
    'view_students', 'view_exams', 'view_scores', 'view_question_bank',
    'view_grading', 'view_homework', 'generate_report',
    'use_ai_chat', 'write_paper', 'view_knowledge_tree', 'edit_knowledge_tree'],
  grade_leader: [
    'view_students', 'view_exams', 'view_scores', 'view_joint_exam',
    'view_question_bank', 'generate_report', 'generate_notification',
    'send_notification', 'use_ai_chat', 'view_grading', 'view_homework',
    'view_knowledge_tree',
    // 2026-04-13 补齐前端镜像（后端 core/permissions.py:218-234 已有）
    'view_conduct', 'manage_conduct', 'export_conduct'],
  lesson_prep_leader: _TEACHER_BASE.filter(p => p !== 'view_conduct' && p !== 'manage_conduct').concat('manage_grading', 'manage_exams'),
  homeroom_teacher: [..._TEACHER_BASE, 'manage_grading', 'generate_notification', 'send_notification', 'manage_conduct_rules', 'manage_conduct_parents', 'export_conduct'],
  subject_teacher: [..._TEACHER_BASE],
  parent: ['view_scores', 'view_homework', 'use_ai_chat', 'view_knowledge_tree', 'view_conduct'],
}

export function hasPermission(role, permission) {
  const perms = ROLE_PERMISSIONS[role]
  return perms ? perms.includes(permission) : false
}
