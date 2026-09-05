/**
 * Typed client for citizen authentication (email + password + email
 * confirmation). The JWT returned by `login` is stored via `lib/auth`; authed
 * calls attach it as a bearer token (see `lib/api-client`).
 */

import { api } from "@/lib/api-client";

export type AuthUser = {
  id: number;
  email: string;
  email_confirmed: boolean;
  phone: string | null;
};

export type LoginResponse = {
  access_token: string;
  token_type: string;
  expires_in: number;
  email_confirmed: boolean;
};

export type MessageResponse = { message: string };

export type ConfirmResponse = { message: string; email_confirmed: boolean };

export const authApi = {
  register: (body: { email: string; password: string }) =>
    api.post<MessageResponse>("/auth/register", body),

  login: (body: { email: string; password: string }) =>
    api.post<LoginResponse>("/auth/login", body),

  me: () => api.get<AuthUser>("/auth/me", { auth: true }),

  confirmEmail: (token: string) =>
    api.post<ConfirmResponse>("/auth/confirm-email", { token }),

  resendConfirmation: (email: string) =>
    api.post<MessageResponse>("/auth/resend-confirmation", { email }),

  requestPasswordReset: (email: string) =>
    api.post<MessageResponse>("/auth/request-password-reset", { email }),

  resetPassword: (body: { token: string; new_password: string }) =>
    api.post<MessageResponse>("/auth/reset-password", body),

  changePassword: (body: { current_password: string; new_password: string }) =>
    api.post<MessageResponse>("/auth/change-password", body, { auth: true }),
};
