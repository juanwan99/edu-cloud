# 登录 + Dashboard 基础验证

## 步骤

### 1. 打开登录页
- 导航到 https://mcu.asia/login
- 验证: 页面包含用户名输入框和密码输入框
- 截图: login-page

### 2. 登录
- 输入用户名 `admin`，密码 `123456`
- 点击登录按钮
- 验证: 跳转到首页（URL 不再包含 /login）
- 验证: 侧边栏可见
- 截图: dashboard

### 3. Dashboard 数据验证
- 验证: 页面包含 KPI 卡片（学生数/班级数/考试数等）
- 验证: KPI 数据非空（不是全 0 或 loading 状态）
- 截图: dashboard-kpi

### 4. 侧边栏导航检查
- 确认侧边栏包含以下菜单项（至少包含其中 5 个）:
  - 首页/Dashboard
  - 考试管理
  - 成绩分析
  - 错题本
  - 作业管理
  - 学生画像
- 截图: sidebar-menu
