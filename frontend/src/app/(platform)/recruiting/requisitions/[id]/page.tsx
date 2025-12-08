"use client";

import { use } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api/client";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { CandidatePipeline } from "@/components/recruiting/candidate-pipeline";
import { ArrowLeft, Edit, MoreHorizontal } from "lucide-react";
import Link from "next/link";
import type { JobRequisition, Pipeline } from "@/types";

const statusColors: Record<string, string> = {
  draft: "bg-gray-100 text-gray-800",
  pending_approval: "bg-yellow-100 text-yellow-800",
  open: "bg-green-100 text-green-800",
  on_hold: "bg-orange-100 text-orange-800",
  closed_filled: "bg-blue-100 text-blue-800",
  closed_cancelled: "bg-red-100 text-red-800",
};

export default function RequisitionDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);

  const { data: job, isLoading: jobLoading } = useQuery({
    queryKey: ["requisition", id],
    queryFn: () => api.get<JobRequisition>(`/api/v1/recruiting/jobs/${id}`),
  });

  const { data: pipeline, isLoading: pipelineLoading } = useQuery({
    queryKey: ["pipeline", id],
    queryFn: () =>
      api.get<Pipeline>(`/api/v1/recruiting/pipeline/jobs/${id}/pipeline`),
  });

  if (jobLoading) {
    return (
      <div className="flex justify-center py-8">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary" />
      </div>
    );
  }

  if (!job) {
    return (
      <div className="text-center py-8">
        <p className="text-muted-foreground">Requisition not found</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        <Button variant="ghost" size="icon" asChild>
          <Link href="/recruiting/requisitions">
            <ArrowLeft className="h-4 w-4" />
          </Link>
        </Button>
        <div className="flex-1">
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold">{job.external_title}</h1>
            <Badge className={statusColors[job.status]}>
              {job.status.replace("_", " ")}
            </Badge>
          </div>
          <p className="text-muted-foreground">{job.requisition_number}</p>
        </div>
        <Button variant="outline" size="icon">
          <Edit className="h-4 w-4" />
        </Button>
        <Button variant="outline" size="icon">
          <MoreHorizontal className="h-4 w-4" />
        </Button>
      </div>

      <Tabs defaultValue="pipeline" className="space-y-4">
        <TabsList>
          <TabsTrigger value="pipeline">Pipeline</TabsTrigger>
          <TabsTrigger value="details">Details</TabsTrigger>
          <TabsTrigger value="activity">Activity</TabsTrigger>
        </TabsList>

        <TabsContent value="pipeline" className="space-y-4">
          {pipelineLoading ? (
            <div className="flex justify-center py-8">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary" />
            </div>
          ) : pipeline ? (
            <CandidatePipeline pipeline={pipeline} />
          ) : (
            <Card>
              <CardContent className="py-8 text-center">
                <p className="text-muted-foreground">No candidates yet</p>
              </CardContent>
            </Card>
          )}
        </TabsContent>

        <TabsContent value="details" className="space-y-4">
          <div className="grid gap-4 md:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle>Job Information</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div>
                  <p className="text-sm text-muted-foreground">Internal Title</p>
                  <p className="font-medium">{job.internal_title || "—"}</p>
                </div>
                <div>
                  <p className="text-sm text-muted-foreground">Worker Type</p>
                  <p className="font-medium capitalize">
                    {job.worker_type.replace("_", " ")}
                  </p>
                </div>
                <div>
                  <p className="text-sm text-muted-foreground">Positions</p>
                  <p className="font-medium">
                    {job.positions_filled} / {job.positions_approved} filled
                  </p>
                </div>
                <div>
                  <p className="text-sm text-muted-foreground">SLA</p>
                  <p className="font-medium">{job.sla_days} days</p>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Compensation</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                {job.salary_min || job.salary_max ? (
                  <>
                    <div>
                      <p className="text-sm text-muted-foreground">Salary Range</p>
                      <p className="font-medium">
                        ${job.salary_min?.toLocaleString()} - $
                        {job.salary_max?.toLocaleString()}
                      </p>
                    </div>
                    <div>
                      <p className="text-sm text-muted-foreground">
                        Visible to Candidates
                      </p>
                      <p className="font-medium">
                        {job.is_salary_visible ? "Yes" : "No"}
                      </p>
                    </div>
                  </>
                ) : (
                  <p className="text-muted-foreground">
                    No compensation details set
                  </p>
                )}
              </CardContent>
            </Card>
          </div>

          {job.job_description && (
            <Card>
              <CardHeader>
                <CardTitle>Job Description</CardTitle>
              </CardHeader>
              <CardContent>
                <div
                  className="prose prose-sm max-w-none"
                  dangerouslySetInnerHTML={{ __html: job.job_description }}
                />
              </CardContent>
            </Card>
          )}

          {job.requirements && (
            <Card>
              <CardHeader>
                <CardTitle>Requirements</CardTitle>
              </CardHeader>
              <CardContent>
                <div
                  className="prose prose-sm max-w-none"
                  dangerouslySetInnerHTML={{ __html: job.requirements }}
                />
              </CardContent>
            </Card>
          )}
        </TabsContent>

        <TabsContent value="activity">
          <Card>
            <CardHeader>
              <CardTitle>Recent Activity</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-muted-foreground">Activity log coming soon...</p>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
