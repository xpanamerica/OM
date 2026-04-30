import { createApp } from "vue";
import { createPinia } from "pinia";
import ElLoading from "element-plus/es/components/loading/index.mjs";
import "element-plus/theme-chalk/base.css";
import "element-plus/es/components/loading/style/css";
import "element-plus/es/components/message/style/css";
import "element-plus/es/components/message-box/style/css";
import "./styles/mobile.css";
import "./styles/design-tokens-native.css";
import "./styles/native-shell.css";

import App from "./App.vue";
import router from "./router";
import { bindAppRouter } from "./router/ready";
import { useAuthStore } from "./stores/auth";

const app = createApp(App);
app.use(ElLoading);
const pinia = createPinia();
app.use(pinia);
app.use(router);
bindAppRouter(router);

const auth = useAuthStore();
auth.attachCrossTabSessionSync();
auth.restoreSession().catch(() => auth.clearSession());

app.mount("#app");
