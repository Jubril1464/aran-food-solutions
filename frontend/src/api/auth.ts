import { apiFetch, setAccessToken } from "./client";
import type { User } from "../types";

export interface RegisterPayload {
  full_name: string;
  phone_number: string;
  email: string;
  password: string;
  street: string;
  city: string;
  state: string;
  business_name?: string;
  business_type?: string;
}

export function register(payload: RegisterPayload) {
  return apiFetch<User>("/auth/register", { method: "POST", body: payload });
}

export async function login(email: string, password: string) {
  const data = await apiFetch<{ access_token: string }>("/auth/login", {
    method: "POST",
    body: { email, password },
    skipAuthRetry: true,
  });
  setAccessToken(data.access_token);
  return data;
}

export async function logout() {
  await apiFetch("/auth/logout", { method: "POST", skipAuthRetry: true });
  setAccessToken(null);
}

export function me() {
  return apiFetch<User>("/auth/me");
}

export function verifyAccount(token: string) {
  return apiFetch<User>("/auth/verify", { method: "POST", body: { token } });
}

export function requestPasswordReset(email: string) {
  return apiFetch<void>("/auth/password-reset/request", { method: "POST", body: { email } });
}

export function confirmPasswordReset(token: string, new_password: string) {
  return apiFetch<void>("/auth/password-reset/confirm", { method: "POST", body: { token, new_password } });
}
