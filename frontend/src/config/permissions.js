// 镜像后端 core/permissions.py ROLE_PERMISSIONS，值使用小写
export const ROLE_PERMISSIONS = {
  platform_admin: ['manage_schools', 'view_schools', 'create_joint_exam', 'manage_joint_exam',
    'view_joint_exam', 'view_cross_school_analytics', 'manage_question_bank', 'view_question_bank',
    'manage_users', 'manage_platform', 'view_students', 'view_exams', 'view_scores',
    'generate_report', 'generate_notification', 'approve_notification', 'send_notification',
    'use_ai_chat', 'write_paper'],
  district_admin: ['manage_schools', 'view_schools', 'manage_school_settings', 'create_joint_exam', 'manage_joint_exam',
    'view_joint_exam', 'view_cross_school_analytics', 'view_question_bank', 'manage_users',
    'view_students', 'view_exams', 'view_scores', 'generate_report', 'approve_notification',
    'send_notification', 'generate_notification', 'use_ai_chat'],
  principal: ['view_schools', 'manage_school_settings', 'view_joint_exam', 'view_cross_school_analytics', 'view_question_bank',
    'view_students', 'view_exams', 'view_scores', 'generate_report', 'approve_notification',
    'send_notification', 'generate_notification', 'use_ai_chat'],
  academic_director: ['view_schools', 'manage_school_settings', 'create_joint_exam', 'manage_joint_exam', 'view_joint_exam',
    'view_question_bank', 'view_students', 'view_exams', 'view_scores', 'generate_report',
    'generate_notification', 'send_notification', 'use_ai_chat'],
  grade_leader: ['view_students', 'view_exams', 'view_scores', 'view_joint_exam',
    'generate_report', 'generate_notification', 'use_ai_chat'],
  homeroom_teacher: ['view_students', 'view_exams', 'view_scores', 'generate_report',
    'generate_notification', 'send_notification', 'use_ai_chat'],
  subject_teacher: ['view_students', 'view_exams', 'view_scores', 'view_question_bank',
    'use_ai_chat', 'write_paper', 'generate_report'],
  parent: ['view_scores'],
}

export function hasPermission(role, permission) {
  const perms = ROLE_PERMISSIONS[role]
  return perms ? perms.includes(permission) : false
}
