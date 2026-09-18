"use client";

import React, { createContext, useContext, useEffect, useState } from "react";
import type { UserRole } from "./types";

interface RoleContextValue {
  role: UserRole;
  setRole: (role: UserRole) => void;
  isCitizen: boolean;
  isOfficial: boolean;
}

const RoleContext = createContext<RoleContextValue>({
  role: "official",
  setRole: () => {},
  isCitizen: false,
  isOfficial: true,
});

export function RoleProvider({ children }: { children: React.ReactNode }) {
  const [role, setRoleState] = useState<UserRole>("official");

  useEffect(() => {
    try {
      const stored = localStorage.getItem("mplads_user_role");
      if (stored === "citizen" || stored === "official") {
        setRoleState(stored);
      }
    } catch {
      // Ignore localStorage read errors in restricted contexts
    }
  }, []);

  const setRole = (newRole: UserRole) => {
    setRoleState(newRole);
    try {
      localStorage.setItem("mplads_user_role", newRole);
    } catch {
      // Ignore localStorage write errors
    }
  };

  return (
    <RoleContext.Provider
      value={{
        role,
        setRole,
        isCitizen: role === "citizen",
        isOfficial: role === "official",
      }}
    >
      {children}
    </RoleContext.Provider>
  );
}

export function useRole() {
  return useContext(RoleContext);
}
