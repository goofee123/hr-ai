"use client";

import Link from "next/link";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Users,
  TrendingUp,
  Clock,
  BarChart3,
  PieChart,
  Shield,
} from "lucide-react";

const reports = [
  {
    title: "EEO Compliance",
    description: "Equal Employment Opportunity analytics and OFCCP compliance reports",
    href: "/recruiting/reports/eeo",
    icon: Shield,
    badge: "Compliance",
  },
  {
    title: "Pipeline Funnel",
    description: "Conversion rates through hiring stages",
    href: "/recruiting/reports/pipeline-funnel",
    icon: BarChart3,
    badge: null,
  },
  {
    title: "Time to Fill",
    description: "Average time to fill positions by department",
    href: "/recruiting/reports/time-to-fill",
    icon: Clock,
    badge: null,
  },
  {
    title: "Source Effectiveness",
    description: "Analyze which sources bring the best candidates",
    href: "/recruiting/reports/source-effectiveness",
    icon: PieChart,
    badge: null,
  },
  {
    title: "Hiring Velocity",
    description: "Track hiring speed trends over time",
    href: "/recruiting/reports/hiring-velocity",
    icon: TrendingUp,
    badge: null,
  },
  {
    title: "Recruiter Performance",
    description: "Individual and team recruiter metrics",
    href: "/recruiting/reports/recruiter-performance",
    icon: Users,
    badge: null,
  },
];

export default function ReportsPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold">Recruiting Reports</h1>
        <p className="text-muted-foreground">
          Analytics and insights for your recruiting pipeline
        </p>
      </div>

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {reports.map((report) => {
          const Icon = report.icon;
          return (
            <Link key={report.href} href={report.href}>
              <Card className="hover:shadow-md transition-shadow h-full">
                <CardHeader>
                  <div className="flex items-center justify-between">
                    <Icon className="h-8 w-8 text-primary" />
                    {report.badge && (
                      <span className="text-xs bg-primary/10 text-primary px-2 py-1 rounded-full">
                        {report.badge}
                      </span>
                    )}
                  </div>
                  <CardTitle className="mt-4">{report.title}</CardTitle>
                  <CardDescription>{report.description}</CardDescription>
                </CardHeader>
                <CardContent>
                  <span className="text-sm text-primary hover:underline">
                    View Report →
                  </span>
                </CardContent>
              </Card>
            </Link>
          );
        })}
      </div>
    </div>
  );
}
