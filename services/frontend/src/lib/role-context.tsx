"use client";

import React, { createContext, useContext, useEffect, useState, useCallback } from "react";
import type { UserRole } from "./types";

export interface OfficialUser {
  id: string;
  official_id?: string;
  name: string;
  email?: string;
  role: "reviewer" | "admin";
  exp?: number;
}

interface RoleContextValue {
  role: UserRole;
  setRole: (role: UserRole) => void;
  isCitizen: boolean;
  isOfficial: boolean;
  official: OfficialUser | null;
  loading: boolean;
  checkSession: () => Promise<OfficialUser | null>;
  logout: () => Promise<void>;
}

const RoleContext = createContext<RoleContextValue>({
  role: "citizen",
  setRole: () => {},
  isCitizen: true,
  isOfficial: false,
  official: null,
  loading: true,
  checkSession: async () => null,
  logout: async () => {},
});

export function RoleProvider({ children }: { children: React.ReactNode }) {
  const [role, setRoleState] = useState<UserRole>("citizen");
  const [official, setOfficial] = useState<OfficialUser | null>(null);
  const [loading, setLoading] = useState(true);

  const checkSession = useCallback(async (): Promise<OfficialUser | null> => {
    try {
      const res = await fetch("/api/auth/me", {
        method: "GET",
        headers: { "Content-Type": "application/json" },
        cache: "no-store",
      });

      if (res.ok) {
        const data = await res.json();
        if (data.official) {
          const user: OfficialUser = {
            id: data.official.id || data.official.official_id,
            official_id: data.official.official_id || data.official.id,
            name: data.official.name || "Official",
            email: data.official.email,
            role: data.official.role || "reviewer",
            exp: data.official.exp,
          };
          setOfficial(user);
          setRoleState("official");
          try {
            localStorage.setItem("mplads_user_role", "official");
          } catch {}
          return user;
        }
      } else {
        setOfficial(null);
        // Fall back to saved preference or citizen
        try {
          const stored = localStorage.getItem("mplads_user_role");
          if (stored === "official" && !official) {
            // Not truly logged in
            setRoleState("citizen");
            localStorage.setItem("mplads_user_role", "citizen");
          } else if (stored === "citizen") {
            setRoleState("citizen");
          }
        } catch {}
      }
    } catch {
      setOfficial(null);
    } finally {
      setLoading(false);
    }
    return null;
  }, [official]);

  useEffect(() => {
    void checkSession();
  }, [checkSession]);

  const setRole = (newRole: UserRole) => {
    setRoleState(newRole);
    try {
      localStorage.setItem("mplads_user_role", newRole);
    } catch {
      // Ignore localStorage write errors
    }
  };

  const logout = async () => {
    try {
      await fetch("/api/auth/logout", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
      });
    } catch (err) {
      console.error("Logout request failed:", err);
    } finally {
      setOfficial(null);
      setRoleState("citizen");
      try {
        localStorage.setItem("mplads_user_role", "citizen");
      } catch {}
    }
  };

  const isOfficial = Boolean(official) && role === "official";

  return (
    <RoleContext.Provider
      value={{
        role,
        setRole,
        isCitizen: !isOfficial,
        isOfficial,
        official,
        loading,
        checkSession,
        logout,
      }}
    >
      {children}
    </RoleContext.Provider>
  );
}

export function useRole() {
  return useContext(RoleContext);
}
