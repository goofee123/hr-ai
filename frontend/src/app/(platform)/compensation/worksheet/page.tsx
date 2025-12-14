"use client";

import { useState, useCallback } from "react";
import Link from "next/link";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import dynamic from "next/dynamic";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  ArrowLeft,
  Save,
  Send,
  FileSpreadsheet,
  Loader2,
  Users,
  DollarSign,
  TrendingUp,
  AlertCircle,
} from "lucide-react";
import { cyclesApi, worksheetsApi, type WorksheetEntryUpdate, type CompCycle } from "@/lib/api/compensation";
import { useToast } from "@/hooks/use-toast";

// Dynamically import AG Grid to avoid SSR issues
const WorksheetGrid = dynamic(
  () => import("@/components/compensation/WorksheetGrid"),
  {
    ssr: false,
    loading: () => (
      <div className="flex items-center justify-center h-96">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    ),
  }
);

export default function WorksheetPage() {
  const [selectedCycleId, setSelectedCycleId] = useState<string>("");
  const [selectedDepartment, setSelectedDepartment] = useState<string>("all");
  const queryClient = useQueryClient();
  const { toast } = useToast();

  // Fetch available cycles
  const { data: cyclesData, isLoading: cyclesLoading } = useQuery({
    queryKey: ["compensation-cycles-active"],
    queryFn: () => cyclesApi.list({ status: "manager_review" }),
  });

  const cycles = cyclesData?.items || [];
  const selectedCycle = cycles.find((c: CompCycle) => c.id === selectedCycleId);

  // Fetch worksheet entries for selected cycle
  const { data: worksheetData, isLoading: worksheetLoading, error: worksheetError } = useQuery({
    queryKey: ["worksheet", selectedCycleId, selectedDepartment],
    queryFn: () =>
      worksheetsApi.list(selectedCycleId, {
        department: selectedDepartment !== "all" ? selectedDepartment : undefined,
      }),
    enabled: !!selectedCycleId,
  });

  const entries = worksheetData?.items || [];

  // Fetch totals
  const { data: totalsData } = useQuery({
    queryKey: ["worksheet-totals", selectedCycleId, selectedDepartment],
    queryFn: () =>
      worksheetsApi.getTotals(
        selectedCycleId,
        selectedDepartment !== "all" ? selectedDepartment : undefined
      ),
    enabled: !!selectedCycleId,
  });

  // Update mutation
  const updateMutation = useMutation({
    mutationFn: ({ entryId, data }: { entryId: string; data: WorksheetEntryUpdate }) =>
      worksheetsApi.update(entryId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["worksheet", selectedCycleId] });
      queryClient.invalidateQueries({ queryKey: ["worksheet-totals", selectedCycleId] });
    },
    onError: (error: Error) => {
      toast({
        title: "Update failed",
        description: error.message,
        variant: "destructive",
      });
    },
  });

  // Submit mutation
  const submitMutation = useMutation({
    mutationFn: () => worksheetsApi.submit(selectedCycleId),
    onSuccess: (data) => {
      toast({
        title: "Submitted successfully",
        description: `${data.submitted_count} entries submitted for review.`,
      });
      queryClient.invalidateQueries({ queryKey: ["worksheet", selectedCycleId] });
    },
    onError: (error: Error) => {
      toast({
        title: "Submit failed",
        description: error.message,
        variant: "destructive",
      });
    },
  });

  const handleUpdateEntry = useCallback(
    async (entryId: string, data: WorksheetEntryUpdate) => {
      await updateMutation.mutateAsync({ entryId, data });
    },
    [updateMutation]
  );

  const handleSubmit = () => {
    if (!selectedCycleId) return;
    submitMutation.mutate();
  };

  // Get unique departments from entries
  const departments = Array.from(
    new Set(entries.map((e) => e.department).filter(Boolean))
  ).sort();

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        <Button variant="ghost" size="icon" asChild>
          <Link href="/compensation">
            <ArrowLeft className="h-4 w-4" />
          </Link>
        </Button>
        <div className="flex-1">
          <h1 className="text-3xl font-bold">Manager Worksheet</h1>
          <p className="text-muted-foreground">
            Review and input compensation recommendations
          </p>
        </div>
        {selectedCycleId && (
          <Button
            onClick={handleSubmit}
            disabled={submitMutation.isPending || entries.length === 0}
          >
            {submitMutation.isPending ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            ) : (
              <Send className="mr-2 h-4 w-4" />
            )}
            Submit for Review
          </Button>
        )}
      </div>

      {/* Cycle & Department Selection */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base">Select Compensation Cycle</CardTitle>
        </CardHeader>
        <CardContent className="flex gap-4">
          <div className="w-80">
            <Select value={selectedCycleId} onValueChange={setSelectedCycleId}>
              <SelectTrigger>
                <SelectValue placeholder="Select a cycle..." />
              </SelectTrigger>
              <SelectContent>
                {cyclesLoading ? (
                  <SelectItem value="loading" disabled>
                    Loading...
                  </SelectItem>
                ) : cycles.length === 0 ? (
                  <SelectItem value="none" disabled>
                    No cycles in manager review
                  </SelectItem>
                ) : (
                  cycles.map((cycle: CompCycle) => (
                    <SelectItem key={cycle.id} value={cycle.id}>
                      {cycle.name} ({cycle.fiscal_year})
                    </SelectItem>
                  ))
                )}
              </SelectContent>
            </Select>
          </div>
          {selectedCycleId && departments.length > 0 && (
            <div className="w-48">
              <Select value={selectedDepartment} onValueChange={setSelectedDepartment}>
                <SelectTrigger>
                  <SelectValue placeholder="All Departments" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Departments</SelectItem>
                  {departments.map((dept) => (
                    <SelectItem key={dept} value={dept as string}>
                      {dept}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Summary Stats */}
      {selectedCycleId && totalsData && (
        <div className="grid gap-4 md:grid-cols-4">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">
                Employees
              </CardTitle>
              <Users className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{totalsData.total_employees}</div>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">
                Current Payroll
              </CardTitle>
              <DollarSign className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">
                {new Intl.NumberFormat("en-US", {
                  style: "currency",
                  currency: "USD",
                  notation: "compact",
                  maximumFractionDigits: 1,
                }).format(totalsData.total_current_payroll)}
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">
                Manager Increase
              </CardTitle>
              <TrendingUp className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">
                {new Intl.NumberFormat("en-US", {
                  style: "currency",
                  currency: "USD",
                  notation: "compact",
                  maximumFractionDigits: 1,
                }).format(totalsData.total_manager_increase)}
              </div>
              <p className="text-xs text-muted-foreground">
                {totalsData.overall_percent_increase.toFixed(2)}% overall
              </p>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">
                Status
              </CardTitle>
              <AlertCircle className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="flex flex-wrap gap-1">
                <Badge variant="outline" className="text-xs">
                  {totalsData.pending_count} pending
                </Badge>
                <Badge variant="outline" className="text-xs bg-yellow-50">
                  {totalsData.submitted_count} submitted
                </Badge>
                <Badge variant="outline" className="text-xs bg-green-50">
                  {totalsData.approved_count} approved
                </Badge>
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Worksheet Grid */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle>Compensation Worksheet</CardTitle>
              <CardDescription>
                {selectedCycleId
                  ? `${entries.length} employee${entries.length !== 1 ? "s" : ""}`
                  : "Select a cycle to view the worksheet"}
              </CardDescription>
            </div>
            {selectedCycle && (
              <Badge className="bg-blue-100 text-blue-800">
                {selectedCycle.name}
              </Badge>
            )}
          </div>
        </CardHeader>
        <CardContent>
          {!selectedCycleId ? (
            <div className="text-center py-12">
              <FileSpreadsheet className="mx-auto h-12 w-12 text-muted-foreground mb-4" />
              <h3 className="text-lg font-semibold mb-2">No cycle selected</h3>
              <p className="text-muted-foreground">
                Select a compensation cycle above to view and edit the worksheet.
              </p>
            </div>
          ) : worksheetError ? (
            <div className="text-center py-12 text-destructive">
              Failed to load worksheet. Please try again.
            </div>
          ) : (
            <WorksheetGrid
              entries={entries}
              onUpdateEntry={handleUpdateEntry}
              isLoading={worksheetLoading}
              readOnly={selectedCycle?.status !== "manager_review"}
            />
          )}
        </CardContent>
      </Card>

      {/* Legend */}
      {selectedCycleId && (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">Color Legend</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-wrap gap-4 text-sm">
            <div className="flex items-center gap-2">
              <div className="w-4 h-4 rounded bg-[#d1fae5]" />
              <span>Light Green: Getting increase</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-4 h-4 rounded bg-[#a7f3d0]" />
              <span>Dark Green: Cap bonus in lieu</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-4 h-4 rounded bg-[#fef3c7]" />
              <span>Beige: Becoming salaried</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-4 h-4 rounded bg-[#fecaca]" />
              <span>Red: No increase</span>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
