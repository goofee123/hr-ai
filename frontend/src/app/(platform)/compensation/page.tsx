"use client";

import Link from "next/link";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import {
  DollarSign,
  Settings,
  LineChart,
  FileSpreadsheet,
  Calendar,
  Upload,
  ChevronRight,
  Users,
  TrendingUp
} from "lucide-react";

const modules = [
  {
    title: "Compensation Cycles",
    description: "Create and manage annual and off-cycle compensation reviews",
    icon: Calendar,
    href: "/compensation/cycles",
    color: "text-blue-500",
    bgColor: "bg-blue-50",
  },
  {
    title: "Rules Engine",
    description: "Define compensation rules based on performance, tenure, and other criteria",
    icon: Settings,
    href: "/compensation/rules",
    color: "text-purple-500",
    bgColor: "bg-purple-50",
  },
  {
    title: "Scenario Modeling",
    description: "Create and compare different compensation scenarios",
    icon: LineChart,
    href: "/compensation/scenarios",
    color: "text-green-500",
    bgColor: "bg-green-50",
  },
  {
    title: "Manager Worksheet",
    description: "Excel-like grid for manager compensation input and review",
    icon: FileSpreadsheet,
    href: "/compensation/worksheet",
    color: "text-orange-500",
    bgColor: "bg-orange-50",
  },
  {
    title: "Data Import",
    description: "Import employee data from Dayforce or other HR systems",
    icon: Upload,
    href: "/compensation/import",
    color: "text-teal-500",
    bgColor: "bg-teal-50",
  },
];

const stats = [
  {
    label: "Active Cycles",
    value: "0",
    icon: Calendar,
    change: null,
  },
  {
    label: "Employees",
    value: "0",
    icon: Users,
    change: null,
  },
  {
    label: "Pending Reviews",
    value: "0",
    icon: FileSpreadsheet,
    change: null,
  },
  {
    label: "Budget Utilization",
    value: "0%",
    icon: TrendingUp,
    change: null,
  },
];

export default function CompensationPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold">Compensation Management</h1>
        <p className="text-muted-foreground">
          Plan, model, and manage employee compensation cycles
        </p>
      </div>

      {/* Quick Stats */}
      <div className="grid gap-4 md:grid-cols-4">
        {stats.map((stat) => (
          <Card key={stat.label}>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">
                {stat.label}
              </CardTitle>
              <stat.icon className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{stat.value}</div>
              {stat.change && (
                <p className="text-xs text-muted-foreground">{stat.change}</p>
              )}
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Module Cards */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {modules.map((module) => (
          <Link key={module.href} href={module.href}>
            <Card className="h-full transition-colors hover:border-primary/50 hover:bg-muted/50 cursor-pointer">
              <CardHeader>
                <div className="flex items-center gap-4">
                  <div className={`rounded-lg p-2 ${module.bgColor}`}>
                    <module.icon className={`h-6 w-6 ${module.color}`} />
                  </div>
                  <div className="flex-1">
                    <CardTitle className="text-lg">{module.title}</CardTitle>
                  </div>
                  <ChevronRight className="h-5 w-5 text-muted-foreground" />
                </div>
              </CardHeader>
              <CardContent>
                <CardDescription>{module.description}</CardDescription>
              </CardContent>
            </Card>
          </Link>
        ))}
      </div>

      {/* Quick Actions */}
      <Card>
        <CardHeader>
          <CardTitle>Quick Actions</CardTitle>
          <CardDescription>Common tasks and workflows</CardDescription>
        </CardHeader>
        <CardContent className="flex flex-wrap gap-2">
          <Button asChild variant="outline">
            <Link href="/compensation/cycles/new">
              <Calendar className="mr-2 h-4 w-4" />
              New Compensation Cycle
            </Link>
          </Button>
          <Button asChild variant="outline">
            <Link href="/compensation/import">
              <Upload className="mr-2 h-4 w-4" />
              Import Employee Data
            </Link>
          </Button>
          <Button asChild variant="outline">
            <Link href="/compensation/rules">
              <Settings className="mr-2 h-4 w-4" />
              Configure Rules
            </Link>
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
