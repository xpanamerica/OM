import { http } from "./http";

export type TokenResponse = {
  access_token: string;
  token_type: string;
};

/** OAuth2 密码模式：字段 ``username`` 可为 **用户名或邮箱**；``application/x-www-form-urlencoded`` */
export async function login(username: string, password: string): Promise<TokenResponse> {
  const body = new URLSearchParams();
  body.set("username", username);
  body.set("password", password);
  const { data } = await http.post<TokenResponse>("/auth/login", body, {
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
  });
  return data;
}
