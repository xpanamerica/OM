import { createRouter, createWebHistory, type RouteLocationNormalized } from "vue-router";
import { useAuthStore } from "@/stores/auth";

const MainLayout = () => import("@/layouts/MainLayout.vue");
const AuthView = () => import("@/views/AuthView.vue");
const VideoListView = () => import("@/views/VideoListView.vue");
const VideoDetailView = () => import("@/views/VideoDetailView.vue");
const SearchView = () => import("@/views/SearchView.vue");
const LearningPathListView = () => import("@/views/LearningPathListView.vue");
const LearningPathDetailView = () => import("@/views/LearningPathDetailView.vue");
const ConceptDetailView = () => import("@/views/ConceptDetailView.vue");
const ProfileView = () => import("@/views/ProfileView.vue");
const HistoryView = () => import("@/views/HistoryView.vue");
const FavoritesView = () => import("@/views/FavoritesView.vue");
const NativeFeedView = () => import("@/views/native/NativeFeedView.vue");
const NativeDiscoverView = () => import("@/views/native/NativeDiscoverView.vue");
const NativeCreateView = () => import("@/views/native/NativeCreateView.vue");
const NativePublishPreviewView = () => import("@/views/native/NativePublishPreviewView.vue");
const NativeHubView = () => import("@/views/native/NativeHubView.vue");
const MessagesView = () => import("@/views/MessagesView.vue");
const UserProfileView = () => import("@/views/UserProfileView.vue");
const DirectMessagesView = () => import("@/views/DirectMessagesView.vue");

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: "/",
      component: MainLayout,
      children: [
        { path: "", redirect: { name: "native-feed" } },
        { path: "feed", name: "native-feed", component: NativeFeedView, meta: { title: "首页" } },
        { path: "discover", name: "native-discover", component: NativeDiscoverView, meta: { title: "发现" } },
        {
          path: "create",
          name: "native-create",
          component: NativeCreateView,
          meta: { title: "创作", requiresAuth: true },
        },
        {
          path: "create/preview/:id",
          name: "native-publish-preview",
          component: NativePublishPreviewView,
          meta: { title: "发布预览", requiresAuth: true },
        },
        { path: "hub", name: "native-hub", component: NativeHubView, meta: { title: "个人中心" } },
        { path: "videos", name: "videos", component: VideoListView, meta: { title: "视频" } },
        { path: "videos/:id", name: "video-detail", component: VideoDetailView, meta: { title: "视频详情" } },
        { path: "users/:id", name: "user-profile", component: UserProfileView, meta: { title: "用户主页" } },
        { path: "search", name: "search", component: SearchView, meta: { title: "搜索" } },
        {
          path: "learning-paths",
          name: "learning-paths",
          component: LearningPathListView,
          meta: { title: "学习路径" },
        },
        {
          path: "learning-paths/:id",
          name: "learning-path-detail",
          component: LearningPathDetailView,
          meta: { title: "学习路径详情" },
        },
        { path: "concepts/:id", name: "concept-detail", component: ConceptDetailView, meta: { title: "概念" } },
        {
          path: "me",
          name: "profile",
          component: ProfileView,
          meta: { title: "个人中心", requiresAuth: true },
        },
        {
          path: "me/history",
          name: "history",
          component: HistoryView,
          meta: { title: "历史记录", requiresAuth: true },
        },
        {
          path: "me/favorites",
          name: "favorites",
          component: FavoritesView,
          meta: { title: "个人收藏", requiresAuth: true },
        },
        {
          path: "me/messages",
          name: "messages",
          component: MessagesView,
          meta: { title: "互动消息", requiresAuth: true },
        },
        {
          path: "me/direct-messages/:peerId?",
          name: "direct-messages",
          component: DirectMessagesView,
          meta: { title: "私信", requiresAuth: true },
        },
        {
          path: ":pathMatch(.*)*",
          name: "not-found",
          component: () => import("@/views/NotFoundView.vue"),
          meta: { title: "页面不存在" },
        },
      ],
    },
    { path: "/auth", name: "auth", component: AuthView, meta: { public: true, title: "登录 / 注册" } },
    { path: "/auth/:pathMatch(.*)*", redirect: { name: "auth" } },
  ],
  scrollBehavior: () => ({ top: 0 }),
});

function isPublicRoute(to: RouteLocationNormalized): boolean {
  return to.matched.some((r) => r.meta.public);
}

router.beforeEach(async (to) => {
  const auth = useAuthStore();
  const needAuth = to.matched.some((r) => r.meta.requiresAuth);
  if (needAuth && !auth.token) {
    return { name: "auth", query: { redirect: to.fullPath } };
  }
  if (auth.token && !auth.user && !isPublicRoute(to)) {
    try {
      await auth.fetchMe();
    } catch {
      auth.logout();
      if (needAuth) return { name: "auth", query: { redirect: to.fullPath } };
    }
  }
  return true;
});

router.afterEach((to) => {
  const titles = to.matched.map((r) => r.meta.title).filter((x): x is string => typeof x === "string");
  const leaf = titles[titles.length - 1];
  document.title = leaf ? `${leaf} · 恒频OM` : "恒频OM";
});

export default router;
