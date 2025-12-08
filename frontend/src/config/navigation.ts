import {
  Briefcase,
  Users,
  LayoutDashboard,
  ClipboardList,
  DollarSign,
  Settings,
  Building2,
  UserCog,
  Workflow,
  XCircle,
  Link2,
  Timer,
  Wrench,
  type LucideIcon,
} from "lucide-react";
import type { UserRole } from "@/types";

export interface NavItem {
  title: string;
  href: string;
  icon: LucideIcon;
  roles: UserRole[];
  children?: NavItem[];
}

export const navigation: NavItem[] = [
  {
    title: "Dashboard",
    href: "/dashboard",
    icon: LayoutDashboard,
    roles: [
      "super_admin",
      "hr_admin",
      "recruiter",
      "hiring_manager",
      "executive",
      "payroll",
      "manager",
      "employee",
    ],
  },
  {
    title: "Recruiting",
    href: "/recruiting",
    icon: Users,
    roles: ["super_admin", "hr_admin", "recruiter", "hiring_manager"],
    children: [
      {
        title: "Requisitions",
        href: "/recruiting/requisitions",
        icon: Briefcase,
        roles: ["super_admin", "hr_admin", "recruiter", "hiring_manager"],
      },
      {
        title: "Candidates",
        href: "/recruiting/candidates",
        icon: Users,
        roles: ["super_admin", "hr_admin", "recruiter", "hiring_manager"],
      },
      {
        title: "Tasks",
        href: "/recruiting/tasks",
        icon: ClipboardList,
        roles: ["super_admin", "hr_admin", "recruiter"],
      },
    ],
  },
  {
    title: "Compensation",
    href: "/compensation",
    icon: DollarSign,
    roles: ["super_admin", "hr_admin", "executive", "payroll"],
    children: [
      {
        title: "Cycles",
        href: "/compensation/cycles",
        icon: ClipboardList,
        roles: ["super_admin", "hr_admin", "executive", "payroll"],
      },
      {
        title: "Rules",
        href: "/compensation/rules",
        icon: Settings,
        roles: ["super_admin", "hr_admin"],
      },
    ],
  },
  {
    title: "Organization",
    href: "/organization",
    icon: Building2,
    roles: ["super_admin", "hr_admin"],
    children: [
      {
        title: "Departments",
        href: "/organization/departments",
        icon: Building2,
        roles: ["super_admin", "hr_admin"],
      },
      {
        title: "Locations",
        href: "/organization/locations",
        icon: Building2,
        roles: ["super_admin", "hr_admin"],
      },
    ],
  },
  {
    title: "Admin",
    href: "/admin",
    icon: Wrench,
    roles: ["super_admin", "hr_admin"],
    children: [
      {
        title: "Pipeline Templates",
        href: "/admin/pipeline-templates",
        icon: Workflow,
        roles: ["super_admin", "hr_admin"],
      },
      {
        title: "Disposition Reasons",
        href: "/admin/disposition-reasons",
        icon: XCircle,
        roles: ["super_admin", "hr_admin"],
      },
      {
        title: "Application Sources",
        href: "/admin/application-sources",
        icon: Link2,
        roles: ["super_admin", "hr_admin"],
      },
      {
        title: "SLA Settings",
        href: "/admin/sla-settings",
        icon: Timer,
        roles: ["super_admin", "hr_admin"],
      },
    ],
  },
  {
    title: "Settings",
    href: "/settings",
    icon: UserCog,
    roles: ["super_admin", "hr_admin"],
  },
];

export function getNavigationForRole(role: UserRole): NavItem[] {
  return navigation.filter((item) => item.roles.includes(role));
}
