import { http } from "./http";
import type { UserPublic } from "./users";

export type TokenResponse = {
  access_token?: string | null;
  token_type: string;
  mfa_required?: boolean;
  mfa_setup_required?: boolean;
  mfa_challenge_token?: string | null;
};
export type MfaStatus = { enabled: boolean; required: boolean; setup_required: boolean };
export type MfaSetup = { secret: string; otpauth_uri: string };
export type MfaEnableResult = { enabled: boolean; recovery_codes: string[] };
export type AuthSession = {
  id: string;
  device_label?: string | null;
  ip_address?: string | null;
  user_agent?: string | null;
  created_at: string;
  last_used_at?: string | null;
  expires_at: string;
  is_current: boolean;
};

/** 与 ``OAuth2PasswordRequestForm`` 一致：表单字段名为 ``username``，值可为 **用户名或邮箱**（后端 ``login_identifier``）。 */
export async function login(username: string, password: string, turnstileToken?: string): Promise<TokenResponse> {
  const body = new URLSearchParams();
  body.set("username", username);
  body.set("password", password);
  if (turnstileToken) {
    body.set("turnstile_token", turnstileToken);
  }
  const { data } = await http.post<TokenResponse>("/auth/login", body, {
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
  });
  return data;
}

export async function refreshAccessToken(): Promise<TokenResponse> {
  const { data } = await http.post<TokenResponse>("/auth/refresh", undefined, {
    skipAuthRedirect: true,
  });
  return data;
}

export async function logout(): Promise<void> {
  await http.post("/auth/logout", undefined, {
    skipAuthRedirect: true,
  });
}

export async function verifyMfaLogin(mfa_challenge_token: string, code: string): Promise<TokenResponse> {
  const { data } = await http.post<TokenResponse>("/auth/mfa/verify-login", { mfa_challenge_token, code });
  return data;
}

export async function fetchMfaStatus(): Promise<MfaStatus> {
  const { data } = await http.get<MfaStatus>("/auth/mfa/status");
  return data;
}

export async function startMfaSetup(mfa_challenge_token?: string | null): Promise<MfaSetup> {
  const { data } = await http.post<MfaSetup>("/auth/mfa/setup", { mfa_challenge_token });
  return data;
}

export async function enableMfa(code: string, mfa_challenge_token?: string | null): Promise<MfaEnableResult> {
  const { data } = await http.post<MfaEnableResult>("/auth/mfa/enable", { code, mfa_challenge_token });
  return data;
}

export async function disableMfa(code: string): Promise<void> {
  await http.post("/auth/mfa/disable", { code });
}

export async function listSessions(): Promise<AuthSession[]> {
  const { data } = await http.get<{ sessions: AuthSession[] }>("/auth/sessions");
  return data.sessions;
}

export async function revokeSession(id: string): Promise<void> {
  await http.post(`/auth/sessions/${id}/revoke`);
}

export async function revokeOtherSessions(): Promise<number> {
  const { data } = await http.post<{ revoked_count: number }>("/auth/sessions/revoke-others");
  return data.revoked_count;
}

/** 与 ``UserRegister`` JSON 体一致 */
export type RegisterBody = {
  email: string;
  username: string;
  password: string;
  turnstile_token?: string | null;
  invite_code?: string | null;
};

export type RegistrationOptions = {
  invite_code_required: boolean;
};

export async function fetchRegistrationOptions(): Promise<RegistrationOptions> {
  const { data } = await http.get<RegistrationOptions>("/auth/registration-options");
  return data;
}

export async function register(body: RegisterBody): Promise<UserPublic> {
  const { data } = await http.post<UserPublic>("/auth/register", body);
  return data;
}
