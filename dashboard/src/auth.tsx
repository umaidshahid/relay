import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";
import { Navigate } from "react-router-dom";
import { login as apiLogin, logout as apiLogout, getMe } from "./api";

interface UserInfo {
  id: string;
  email: string;
  is_active: boolean;
}

interface AuthContextValue {
  user: UserInfo | null;
  token: string | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

const TOKEN_KEY = "relay_jwt";

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<UserInfo | null>(null);
  const [token, setToken] = useState<string | null>(
    () => localStorage.getItem(TOKEN_KEY)
  );
  const [loading, setLoading] = useState(true);

  // On mount, establish the session. A bearer token (password login) is sent
  // explicitly; otherwise we still call getMe with no token so the httpOnly
  // OAuth cookie (if present) is picked up via credentials: "include".
  useEffect(() => {
    getMe(token)
      .then((me) => setUser(me))
      .catch(() => {
        if (token) {
          localStorage.removeItem(TOKEN_KEY);
          setToken(null);
        }
      })
      .finally(() => setLoading(false));
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const login = useCallback(async (email: string, password: string) => {
    const { access_token } = await apiLogin(email, password);
    localStorage.setItem(TOKEN_KEY, access_token);
    setToken(access_token);
    const me = await getMe(access_token);
    setUser(me);
  }, []);

  const logout = useCallback(async () => {
    // Clears both the bearer session and the OAuth cookie session.
    await apiLogout(token).catch(() => {});
    localStorage.removeItem(TOKEN_KEY);
    setToken(null);
    setUser(null);
    window.location.href = "/";
  }, [token]);

  return (
    <AuthContext.Provider value={{ user, token, loading, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>");
  return ctx;
}

/** Redirects to /login when not authenticated (used to wrap protected routes). */
export function RequireAuth({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth();

  if (loading) return null;

  if (!user) {
    return <Navigate to="/login" replace />;
  }

  return <>{children}</>;
}
