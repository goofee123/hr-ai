import { create } from "zustand";
import { persist } from "zustand/middleware";
import type { User, UserRole } from "@/types";

interface AuthState {
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  setUser: (user: User | null) => void;
  setLoading: (loading: boolean) => void;
  logout: () => void;
  hasPermission: (permission: string) => boolean;
  hasRole: (roles: UserRole[]) => boolean;
}

// Permission mappings by role
const rolePermissions: Record<UserRole, string[]> = {
  super_admin: ["*"],
  hr_admin: [
    "jobs:*",
    "candidates:*",
    "applications:*",
    "tasks:*",
    "compensation:*",
    "users:view",
  ],
  recruiter: [
    "jobs:view",
    "jobs:create",
    "jobs:edit",
    "candidates:*",
    "applications:*",
    "tasks:*",
  ],
  hiring_manager: [
    "jobs:view",
    "candidates:view",
    "applications:view",
    "applications:feedback",
    "tasks:view",
  ],
  executive: [
    "jobs:view",
    "candidates:view",
    "compensation:view",
    "compensation:approve",
  ],
  payroll: ["compensation:view", "compensation:export"],
  manager: ["compensation:input", "compensation:view_team"],
  employee: ["profile:view", "profile:edit"],
};

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      user: null,
      isAuthenticated: false,
      isLoading: true,

      setUser: (user) =>
        set({
          user,
          isAuthenticated: !!user,
          isLoading: false,
        }),

      setLoading: (isLoading) => set({ isLoading }),

      logout: () =>
        set({
          user: null,
          isAuthenticated: false,
          isLoading: false,
        }),

      hasPermission: (permission: string) => {
        const { user } = get();
        if (!user) return false;

        const permissions = rolePermissions[user.role] || [];
        if (permissions.includes("*")) return true;

        // Check for wildcard permissions (e.g., "jobs:*" matches "jobs:view")
        const [resource, action] = permission.split(":");
        const wildcardPermission = `${resource}:*`;

        return (
          permissions.includes(permission) ||
          permissions.includes(wildcardPermission)
        );
      },

      hasRole: (roles: UserRole[]) => {
        const { user } = get();
        if (!user) return false;
        return roles.includes(user.role);
      },
    }),
    {
      name: "auth-storage",
      partialize: (state) => ({ user: state.user }),
    }
  )
);
