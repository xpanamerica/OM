import { http } from "./http";
import type { UserPublic } from "./users";

export type TokenResponse = { access_token: string; token_type: string };

/** 与 ``OAuth2PasswordRequestForm`` 一致：表单字段名为 ``username``，值可为 **用户名或邮箱**（后端 ``login_identifier``）。 */
export async function login(username: string, password: string): Promise<TokenResponse> {
  const body = new URLSearchParams();
  body.set("username", username);
  body.set("password", password);
  const { data } = await http.post<TokenResponse>("/auth/login", body, {
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
  });
  return data;
}

/** 与 ``UserRegister`` JSON 体一致 */
export type RegisterBody = {
  email: string;
  username: string;
  password: string;
};

export async function register(body: RegisterBody): Promise<UserPublic> {
  const { data } = await http.post<UserPublic>("/auth/register", body);
  return data;
}
