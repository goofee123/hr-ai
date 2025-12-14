"use client";

import { useState } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  ArrowLeft,
  Plus,
  Calendar,
  ChevronRight,
  Loader2,
} from "lucide-react";
import { cyclesApi, type CompCycle } from "@/lib/api/compensation";

const statusColors: Record<string, string> = {
  draft: "bg-gray-100 text-gray-800",
  modeling: "bg-blue-100 text-blue-800",
  manager_review: "bg-yellow-100 text-yellow-800",
  executive_review: "bg-purple-100 text-purple-800",
  comp_qa: "bg-orange-100 text-orange-800",
  approved: "bg-green-100 text-green-800",
  exported: "bg-teal-100 text-teal-800",
  archived: "bg-gray-100 text-gray-600",
};

const statusLabels: Record<string, string> = {
  draft: "Draft",
  modeling: "Modeling",
  manager_review: "Manager Review",
  executive_review: "Executive Review",
  comp_qa: "Comp QA",
  approved: "Approved",
  exported: "Exported",
  archived: "Archived",
};

const cycleTypeLabels: Record<string, string> = {
  annual: "Annual",
  mid_year: "Mid-Year",
  off_cycle: "Off-Cycle",
};

export default function CompensationCyclesPage() {
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [yearFilter, setYearFilter] = useState<string>("all");

  const { data, isLoading, error } = useQuery({
    queryKey: ["compensation-cycles", statusFilter, yearFilter],
    queryFn: () =>
      cyclesApi.list({
        status: statusFilter !== "all" ? statusFilter : undefined,
        fiscal_year: yearFilter !== "all" ? parseInt(yearFilter) : undefined,
      }),
  });

  const cycles = data?.items || [];

  const currentYear = new Date().getFullYear();
  const years = [currentYear - 1, currentYear, currentYear + 1];

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        <Button variant="ghost" size="icon" asChild>
          <Link href="/compensation">
            <ArrowLeft className="h-4 w-4" />
          </Link>
        </Button>
        <div className="flex-1">
          <h1 className="text-3xl font-bold">Compensation Cycles</h1>
          <p className="text-muted-foreground">
            Manage annual and off-cycle compensation reviews
          </p>
        </div>
        <Button asChild>
          <Link href="/compensation/cycles/new">
            <Plus className="mr-2 h-4 w-4" />
            New Cycle
          </Link>
        </Button>
      </div>

      {/* Filters */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base">Filters</CardTitle>
        </CardHeader>
        <CardContent className="flex gap-4">
          <div className="w-48">
            <Select value={statusFilter} onValueChange={setStatusFilter}>
              <SelectTrigger>
                <SelectValue placeholder="All Statuses" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Statuses</SelectItem>
                <SelectItem value="draft">Draft</SelectItem>
                <SelectItem value="modeling">Modeling</SelectItem>
                <SelectItem value="manager_review">Manager Review</SelectItem>
                <SelectItem value="executive_review">Executive Review</SelectItem>
                <SelectItem value="comp_qa">Comp QA</SelectItem>
                <SelectItem value="approved">Approved</SelectItem>
                <SelectItem value="exported">Exported</SelectItem>
                <SelectItem value="archived">Archived</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div className="w-36">
            <Select value={yearFilter} onValueChange={setYearFilter}>
              <SelectTrigger>
                <SelectValue placeholder="All Years" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Years</SelectItem>
                {years.map((year) => (
                  <SelectItem key={year} value={year.toString()}>
                    {year}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </CardContent>
      </Card>

      {/* Cycles Table */}
      <Card>
        <CardHeader>
          <CardTitle>Compensation Cycles</CardTitle>
          <CardDescription>
            {cycles.length} cycle{cycles.length !== 1 ? "s" : ""} found
          </CardDescription>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
            </div>
          ) : error ? (
            <div className="text-center py-12 text-destructive">
              Failed to load cycles. Please try again.
            </div>
          ) : cycles.length === 0 ? (
            <div className="text-center py-12">
              <Calendar className="mx-auto h-12 w-12 text-muted-foreground mb-4" />
              <h3 className="text-lg font-semibold mb-2">No cycles found</h3>
              <p className="text-muted-foreground mb-4">
                Create your first compensation cycle to get started.
              </p>
              <Button asChild>
                <Link href="/compensation/cycles/new">
                  <Plus className="mr-2 h-4 w-4" />
                  New Cycle
                </Link>
              </Button>
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead>Type</TableHead>
                  <TableHead>Fiscal Year</TableHead>
                  <TableHead>Effective Date</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead className="w-[50px]"></TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {cycles.map((cycle) => (
                  <TableRow key={cycle.id} className="cursor-pointer hover:bg-muted/50">
                    <TableCell>
                      <Link
                        href={`/compensation/cycles/${cycle.id}`}
                        className="font-medium hover:underline"
                      >
                        {cycle.name}
                      </Link>
                      {cycle.description && (
                        <p className="text-sm text-muted-foreground truncate max-w-md">
                          {cycle.description}
                        </p>
                      )}
                    </TableCell>
                    <TableCell>
                      <Badge variant="outline">
                        {cycleTypeLabels[cycle.cycle_type] || cycle.cycle_type}
                      </Badge>
                    </TableCell>
                    <TableCell>{cycle.fiscal_year}</TableCell>
                    <TableCell>
                      {new Date(cycle.effective_date).toLocaleDateString()}
                    </TableCell>
                    <TableCell>
                      <Badge className={statusColors[cycle.status]}>
                        {statusLabels[cycle.status] || cycle.status}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <Link href={`/compensation/cycles/${cycle.id}`}>
                        <ChevronRight className="h-4 w-4 text-muted-foreground" />
                      </Link>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
