"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { DollarSign, Settings, LineChart, FileSpreadsheet } from "lucide-react";

export default function CompensationPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold">Compensation Management</h1>
        <p className="text-muted-foreground">
          Plan, model, and manage employee compensation cycles
        </p>
      </div>

      <Card className="border-dashed">
        <CardContent className="py-16 text-center">
          <div className="mx-auto mb-6 flex h-16 w-16 items-center justify-center rounded-full bg-muted">
            <DollarSign className="h-8 w-8 text-muted-foreground" />
          </div>
          <h2 className="text-2xl font-semibold mb-2">Coming Soon</h2>
          <p className="text-muted-foreground max-w-md mx-auto mb-8">
            The Compensation Management module is currently under development.
            Check back soon for powerful compensation planning tools.
          </p>

          <div className="grid gap-4 md:grid-cols-3 max-w-2xl mx-auto">
            <Card className="bg-muted/50">
              <CardHeader className="pb-2">
                <LineChart className="h-6 w-6 text-muted-foreground mb-2" />
                <CardTitle className="text-sm font-medium">Scenario Modeling</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-xs text-muted-foreground">
                  Model different compensation scenarios and compare costs
                </p>
              </CardContent>
            </Card>

            <Card className="bg-muted/50">
              <CardHeader className="pb-2">
                <Settings className="h-6 w-6 text-muted-foreground mb-2" />
                <CardTitle className="text-sm font-medium">Rules Engine</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-xs text-muted-foreground">
                  Define compensation rules based on performance and tenure
                </p>
              </CardContent>
            </Card>

            <Card className="bg-muted/50">
              <CardHeader className="pb-2">
                <FileSpreadsheet className="h-6 w-6 text-muted-foreground mb-2" />
                <CardTitle className="text-sm font-medium">Manager Worksheet</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-xs text-muted-foreground">
                  Excel-like grid for manager compensation input
                </p>
              </CardContent>
            </Card>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
