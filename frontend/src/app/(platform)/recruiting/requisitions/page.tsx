"use client";

import { useState } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api/client";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Plus, Search, Filter } from "lucide-react";
import type { JobRequisition, PaginatedResponse } from "@/types";
import { formatDate } from "@/lib/utils";

const statusColors: Record<string, string> = {
  draft: "bg-gray-100 text-gray-800",
  pending_approval: "bg-yellow-100 text-yellow-800",
  open: "bg-green-100 text-green-800",
  on_hold: "bg-orange-100 text-orange-800",
  closed_filled: "bg-blue-100 text-blue-800",
  closed_cancelled: "bg-red-100 text-red-800",
};

export default function RequisitionsPage() {
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);

  const { data, isLoading } = useQuery({
    queryKey: ["requisitions", page, search],
    queryFn: () =>
      api.get<PaginatedResponse<JobRequisition & { candidate_count: number }>>(
        `/api/v1/recruiting/jobs?page=${page}&search=${search}`
      ),
  });

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Job Requisitions</h1>
          <p className="text-muted-foreground">
            Manage your open positions and hiring pipeline
          </p>
        </div>
        <Button asChild>
          <Link href="/recruiting/requisitions/new">
            <Plus className="mr-2 h-4 w-4" />
            New Requisition
          </Link>
        </Button>
      </div>

      <div className="flex items-center gap-4">
        <div className="relative flex-1 max-w-sm">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="Search requisitions..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-9"
          />
        </div>
        <Button variant="outline">
          <Filter className="mr-2 h-4 w-4" />
          Filters
        </Button>
      </div>

      {isLoading ? (
        <div className="flex justify-center py-8">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary" />
        </div>
      ) : (
        <div className="grid gap-4">
          {data?.items.map((job) => (
            <Card key={job.id}>
              <CardHeader className="pb-2">
                <div className="flex items-start justify-between">
                  <div>
                    <Link href={`/recruiting/requisitions/${job.id}`}>
                      <CardTitle className="hover:underline">
                        {job.external_title}
                      </CardTitle>
                    </Link>
                    <p className="text-sm text-muted-foreground">
                      {job.requisition_number}
                    </p>
                  </div>
                  <Badge className={statusColors[job.status] || "bg-gray-100"}>
                    {job.status.replace("_", " ")}
                  </Badge>
                </div>
              </CardHeader>
              <CardContent>
                <div className="flex items-center gap-6 text-sm text-muted-foreground">
                  <div>
                    <span className="font-medium text-foreground">
                      {job.candidate_count || 0}
                    </span>{" "}
                    candidates
                  </div>
                  <div>
                    <span className="font-medium text-foreground">
                      {job.positions_filled}/{job.positions_approved}
                    </span>{" "}
                    positions filled
                  </div>
                  <div>
                    SLA:{" "}
                    <span className="font-medium text-foreground">
                      {job.sla_days} days
                    </span>
                  </div>
                  {job.opened_at && (
                    <div>Opened: {formatDate(job.opened_at)}</div>
                  )}
                </div>
              </CardContent>
            </Card>
          ))}

          {data?.items.length === 0 && (
            <Card>
              <CardContent className="py-8 text-center">
                <p className="text-muted-foreground">No requisitions found</p>
                <Button asChild className="mt-4">
                  <Link href="/recruiting/requisitions/new">
                    Create your first requisition
                  </Link>
                </Button>
              </CardContent>
            </Card>
          )}
        </div>
      )}

      {data && data.total_pages > 1 && (
        <div className="flex justify-center gap-2">
          <Button
            variant="outline"
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page === 1}
          >
            Previous
          </Button>
          <span className="flex items-center px-4 text-sm">
            Page {page} of {data.total_pages}
          </span>
          <Button
            variant="outline"
            onClick={() => setPage((p) => p + 1)}
            disabled={page >= data.total_pages}
          >
            Next
          </Button>
        </div>
      )}
    </div>
  );
}
