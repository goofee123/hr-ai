"use client";

import Link from "next/link";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { ClipboardList, ArrowLeft } from "lucide-react";

export default function CompensationCyclesPage() {
  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        <Button variant="ghost" size="icon" asChild>
          <Link href="/compensation">
            <ArrowLeft className="h-4 w-4" />
          </Link>
        </Button>
        <div>
          <h1 className="text-3xl font-bold">Compensation Cycles</h1>
          <p className="text-muted-foreground">
            Manage annual and off-cycle compensation reviews
          </p>
        </div>
      </div>

      <Card className="border-dashed">
        <CardContent className="py-16 text-center">
          <div className="mx-auto mb-6 flex h-16 w-16 items-center justify-center rounded-full bg-muted">
            <ClipboardList className="h-8 w-8 text-muted-foreground" />
          </div>
          <h2 className="text-2xl font-semibold mb-2">Coming Soon</h2>
          <p className="text-muted-foreground max-w-md mx-auto">
            Compensation cycle management is coming soon. You&apos;ll be able to create,
            configure, and track compensation review cycles.
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
