import axios from "axios";

/** 请求被 AbortController 取消（路由切换等），不应弹错误提示。 */
export function isCanceledRequest(e: unknown): boolean {
  return axios.isAxiosError(e) && (e.code === "ERR_CANCELED" || e.name === "CanceledError");
}
