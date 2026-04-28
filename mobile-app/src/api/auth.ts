import type { TokenResponse } from "./types";
import { apiPostForm } from "./client";

/** 与 user-web ``/auth/login`` + OAuth2PasswordRequestForm 一致 */
export async function login(username: string, password: string): Promise<TokenResponse> {
  const body = new URLSearchParams();
  body.set("username", username);
  body.set("password", password);
  const { data } = await apiPostForm<TokenResponse>("/auth/login", body, { skipAuth: true });
  return data;
}
