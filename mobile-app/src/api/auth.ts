import type { TokenResponse } from "./types";
import { apiPostForm } from "./client";

/** 与 user-web ``/auth/login`` + OAuth2PasswordRequestForm 一致 */
export async function login(username: string, password: string, turnstileToken?: string): Promise<TokenResponse> {
  const body = new URLSearchParams();
  body.set("username", username);
  body.set("password", password);
  if (turnstileToken) {
    body.set("turnstile_token", turnstileToken);
  }
  const { data } = await apiPostForm<TokenResponse>("/auth/login", body, { skipAuth: true });
  return data;
}
