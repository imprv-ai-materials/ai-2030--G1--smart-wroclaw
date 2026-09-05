"use client";

/**
 * Citizen auth: a small context over the JWT stored in localStorage. The token
 * lives under `sw_token` (see `lib/api-client`) and is read via
 * `useSyncExternalStore`, so it stays in sync across tabs and never mismatches
 * during hydration. `user` is loaded from `GET /auth/me` while a token is
 * present; on a 401 the api-client clears the token, which re-renders here.
 */

import {
  createContext,
  useCallback,
  useContext,
  useSyncExternalStore,
  type ReactNode,
} from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";

import {
  clearToken,
  getToken,
  getTokenServerSnapshot,
  setToken,
  subscribeToken,
} from "@/lib/api-client";
import { authApi, type AuthUser } from "@/lib/auth-api";

// Re-export the token primitives so callers can `import { ... } from "@/lib/auth"`.
export { getToken, setToken, clearToken };

export const authKeys = { me: ["auth", "me"] as const };

type AuthContextValue = {
  token: string | null;
  user: AuthUser | null;
  isLoading: boolean;
  refresh: () => Promise<void>;
  login: (token: string) => void;
  logout: () => void;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient();
  const token = useSyncExternalStore(
    subscribeToken,
    getToken,
    getTokenServerSnapshot,
  );

  const meQuery = useQuery({
    queryKey: authKeys.me,
    queryFn: () => authApi.me(),
    enabled: token != null,
    retry: false,
    staleTime: 60_000,
  });

  const login = useCallback(
    (newToken: string) => {
      setToken(newToken);
      queryClient.invalidateQueries({ queryKey: authKeys.me });
    },
    [queryClient],
  );

  const logout = useCallback(() => {
    clearToken();
    queryClient.removeQueries({ queryKey: authKeys.me });
  }, [queryClient]);

  const refresh = useCallback(async () => {
    await queryClient.invalidateQueries({ queryKey: authKeys.me });
  }, [queryClient]);

  const value: AuthContextValue = {
    token,
    user: meQuery.data ?? null,
    isLoading: token != null && meQuery.isLoading,
    refresh,
    login,
    logout,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within <AuthProvider>");
  return ctx;
}
