import React, { createContext, useContext, useState } from "react";
import type { User } from "../types";

interface AuthContextValue {
  user: User | null;
  setUser: (user: User | null) => void;
  isAdmin: boolean;
}

const AuthContext = createContext<AuthContextValue>({
  user: null,
  setUser: () => {},
  isAdmin: false,
});

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(() => {
    const saved = localStorage.getItem("breathe_user");
    try {
      return saved ? JSON.parse(saved) : null;
    } catch {
      return null;
    }
  });

  const handleSetUser = (u: User | null) => {
    setUser(u);
    if (u) {
      localStorage.setItem("breathe_user", JSON.stringify(u));
    } else {
      localStorage.removeItem("breathe_user");
    }
  };

  return (
    <AuthContext.Provider value={{ user, setUser: handleSetUser, isAdmin: user?.role === "ADMIN" }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}
