<script setup>
import { computed } from 'vue'
import {
  LayoutDashboard, FileText, BookOpen, GraduationCap,
  Users, School, CheckSquare, BarChart3, FlaskConical,
  Calendar, FileEdit, PenTool, RefreshCw, User,
  Settings, Bell, Star, Briefcase, Shield,
  ClipboardList, Target, Search, ChevronRight,
  Bot, ListTodo, BookCopy, Award, UserCircle,
} from 'lucide-vue-next'

const props = defineProps({
  name: { type: String, required: true },
  size: { type: [Number, String], default: 20 },
  color: { type: String, default: 'currentColor' },
})

const ICON_MAP = {
  dashboard: LayoutDashboard,
  exam: FileText,
  book: BookOpen,
  academic: GraduationCap,
  people: Users,
  school: School,
  marking: CheckSquare,
  chart: BarChart3,
  flask: FlaskConical,
  calendar: Calendar,
  document: FileEdit,
  pencil: PenTool,
  reload: RefreshCw,
  person: User,
  settings: Settings,
  bell: Bell,
  star: Star,
  briefcase: Briefcase,
  shield: Shield,
  clipboard: ClipboardList,
  target: Target,
  search: Search,
  'chevron-right': ChevronRight,
  users: Users,
  ai: Bot,
  notification: Bell,
  todo: ListTodo,
  class: BookCopy,
  paper: BookOpen,
  score: Award,
  profile: UserCircle,
}

const iconComponent = computed(() => ICON_MAP[props.name] || null)
</script>

<template>
  <component
    v-if="iconComponent"
    :is="iconComponent"
    :size="size"
    :color="color"
    :stroke-width="1.75"
  />
</template>
