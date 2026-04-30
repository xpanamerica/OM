import { createRouter, createWebHistory, type RouteLocationNormalized } from "vue-router";
import { ElMessage } from "@/util/elementPlusMessage";
import { useAuthStore } from "@/stores/auth";

const LoginView = () => import("@/views/LoginView.vue");
const AdminLayout = () => import("@/views/AdminLayout.vue");
const VideoListView = () => import("@/views/VideoListView.vue");
const VideoReviewView = () => import("@/views/VideoReviewView.vue");
const TaxonomyView = () => import("@/views/TaxonomyView.vue");
const ConceptListView = () => import("@/views/ConceptListView.vue");
const LearningPathListView = () => import("@/views/LearningPathListView.vue");
const UserListView = () => import("@/views/UserListView.vue");
const PlatformStatsView = () => import("@/views/PlatformStatsView.vue");
const PlatformSettingsView = () => import("@/views/PlatformSettingsView.vue");
const InviteCodesView = () => import("@/views/InviteCodesView.vue");
const RegistrationAuditView = () => import("@/views/RegistrationAuditView.vue");
const SecurityView = () => import("@/views/SecurityView.vue");

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: "/login",
      name: "login",
      component: LoginView,
      meta: { public: true, title: "登录" },
    },
    { path: "/login/:pathMatch(.*)*", redirect: { name: "login" } },
    {
      path: "/",
      component: AdminLayout,
      meta: { requiresAdmin: true },
      children: [
        { path: "", redirect: "/videos" },
        {
          path: "videos",
          name: "videos",
          component: VideoListView,
          meta: { title: "视频管理" },
        },
        {
          path: "review",
          name: "review",
          component: VideoReviewView,
          meta: { title: "视频审核" },
        },
        {
          path: "taxonomy",
          name: "taxonomy",
          component: TaxonomyView,
          meta: { title: "分类与标签" },
        },
        {
          path: "concepts",
          name: "concepts",
          component: ConceptListView,
          meta: { title: "概念" },
        },
        {
          path: "learning-paths",
          name: "learning-paths",
          component: LearningPathListView,
          meta: { title: "学习路径" },
        },
        {
          path: "users",
          name: "users",
          component: UserListView,
          meta: { title: "用户" },
        },
        {
          path: "stats",
          name: "stats",
          component: PlatformStatsView,
          meta: { title: "平台统计" },
        },
        {
          path: "settings",
          name: "settings",
          component: PlatformSettingsView,
          meta: { title: "平台设置" },
        },
        {
          path: "invite-codes",
          name: "invite-codes",
          component: InviteCodesView,
          meta: { title: "内测邀请码" },
        },
        {
          path: "registration-audit",
          name: "registration-audit",
          component: RegistrationAuditView,
          meta: { title: "注册审计" },
        },
        {
          path: "security",
          name: "security",
          component: SecurityView,
          meta: { title: "账号安全" },
        },
        {
          path: ":pathMatch(.*)*",
          name: "not-found",
          component: () => import("@/views/NotFoundView.vue"),
          meta: { title: "页面不存在" },
        },
      ],
    },
  ],
});

function isPublicRoute(to: RouteLocationNormalized): boolean {
  return to.matched.some((r) => r.meta.public);
}

router.beforeEach(async (to) => {
  const auth = useAuthStore();
  if (isPublicRoute(to)) {
    if (to.name === "login" && auth.token) {
      if (!auth.user) {
        try {
          await auth.fetchMe();
        } catch {
          return true;
        }
      }
      if (auth.isAdmin) return { path: "/" };
    }
    return true;
  }

  if (!auth.token) {
    return { name: "login", query: { redirect: to.fullPath } };
  }

  if (!auth.user) {
    try {
      await auth.fetchMe();
    } catch {
      auth.clearSession();
      return { name: "login", query: { redirect: to.fullPath } };
    }
  }

  const needAdmin = to.matched.some((record) => record.meta.requiresAdmin);
  if (needAdmin && !auth.isAdmin) {
    ElMessage.error("需要管理员权限");
    auth.logout();
    return { name: "login" };
  }

  return true;
});

router.afterEach((to) => {
  const titles = to.matched.map((r) => r.meta.title).filter((x): x is string => typeof x === "string");
  const leaf = titles[titles.length - 1];
  document.title = leaf ? `${leaf} · 管理后台` : "管理后台";
});

export default router;
