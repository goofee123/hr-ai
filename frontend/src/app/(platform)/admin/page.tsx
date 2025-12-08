"use client";

import Link from "next/link";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Workflow, XCircle, Link2, Timer } from "lucide-react";

const adminSections = [
  {
    title: "Pipeline Templates",
    description: "Configure hiring workflow stages and templates",
    href: "/admin/pipeline-templates",
    icon: Workflow,
  },
  {
    title: "Disposition Reasons",
    description: "Manage rejection and withdrawal reason codes",
    href: "/admin/disposition-reasons",
    icon: XCircle,
  },
  {
    title: "Application Sources",
    description: "Configure candidate application sources",
    href: "/admin/application-sources",
    icon: Link2,
  },
  {
    title: "SLA Settings",
    description: "Set up SLA configurations for job types",
    href: "/admin/sla-settings",
    icon: Timer,
  },
];

export default function AdminPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold">Admin Configuration</h1>
        <p className="text-muted-foreground">
          Configure system settings and templates for your organization
        </p>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        {adminSections.map((section) => (
          <Link key={section.href} href={section.href}>
            <Card className="hover:bg-muted/50 transition-colors cursor-pointer h-full">
              <CardHeader className="flex flex-row items-center space-y-0 pb-2">
                <section.icon className="h-5 w-5 text-muted-foreground mr-2" />
                <CardTitle className="text-lg font-medium">
                  {section.title}
                </CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-sm text-muted-foreground">
                  {section.description}
                </p>
              </CardContent>
            </Card>
          </Link>
        ))}
      </div>
    </div>
  );
}
