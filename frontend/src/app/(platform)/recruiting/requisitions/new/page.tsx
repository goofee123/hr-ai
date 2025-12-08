"use client";

import { useRouter } from "next/navigation";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { api } from "@/lib/api/client";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useToast } from "@/hooks/use-toast";
import { ArrowLeft } from "lucide-react";
import Link from "next/link";

const requisitionSchema = z.object({
  external_title: z.string().min(1, "Title is required"),
  internal_title: z.string().optional(),
  job_description: z.string().optional(),
  requirements: z.string().optional(),
  worker_type: z.enum(["full_time", "part_time", "contractor", "intern", "temporary"]),
  positions_approved: z.number().min(1),
  salary_min: z.number().optional(),
  salary_max: z.number().optional(),
  is_salary_visible: z.boolean(),
  sla_days: z.number().min(1),
});

type RequisitionFormData = z.infer<typeof requisitionSchema>;

export default function NewRequisitionPage() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const { toast } = useToast();

  const {
    register,
    handleSubmit,
    setValue,
    watch,
    formState: { errors },
  } = useForm<RequisitionFormData>({
    resolver: zodResolver(requisitionSchema),
    defaultValues: {
      worker_type: "full_time",
      positions_approved: 1,
      is_salary_visible: false,
      sla_days: 45,
    },
  });

  const createRequisition = useMutation({
    mutationFn: (data: RequisitionFormData) =>
      api.post("/api/v1/recruiting/jobs", data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["requisitions"] });
      toast({
        title: "Requisition created",
        description: "Your job requisition has been created successfully.",
      });
      router.push("/recruiting/requisitions");
    },
    onError: () => {
      toast({
        title: "Error",
        description: "Failed to create requisition. Please try again.",
        variant: "destructive",
      });
    },
  });

  const onSubmit = (data: RequisitionFormData) => {
    createRequisition.mutate(data);
  };

  return (
    <div className="space-y-6 max-w-3xl">
      <div className="flex items-center gap-4">
        <Button variant="ghost" size="icon" asChild>
          <Link href="/recruiting/requisitions">
            <ArrowLeft className="h-4 w-4" />
          </Link>
        </Button>
        <div>
          <h1 className="text-2xl font-bold">New Job Requisition</h1>
          <p className="text-muted-foreground">
            Create a new position to start recruiting
          </p>
        </div>
      </div>

      <form onSubmit={handleSubmit(onSubmit)} className="space-y-6">
        <Card>
          <CardHeader>
            <CardTitle>Basic Information</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="external_title">Job Title *</Label>
              <Input
                id="external_title"
                {...register("external_title")}
                placeholder="e.g., Senior Software Engineer"
              />
              {errors.external_title && (
                <p className="text-sm text-destructive">
                  {errors.external_title.message}
                </p>
              )}
            </div>

            <div className="space-y-2">
              <Label htmlFor="internal_title">Internal Title</Label>
              <Input
                id="internal_title"
                {...register("internal_title")}
                placeholder="Internal job code or title"
              />
            </div>

            <div className="grid gap-4 md:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor="worker_type">Worker Type</Label>
                <Select
                  value={watch("worker_type")}
                  onValueChange={(value) =>
                    setValue("worker_type", value as RequisitionFormData["worker_type"])
                  }
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="full_time">Full Time</SelectItem>
                    <SelectItem value="part_time">Part Time</SelectItem>
                    <SelectItem value="contractor">Contractor</SelectItem>
                    <SelectItem value="intern">Intern</SelectItem>
                    <SelectItem value="temporary">Temporary</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-2">
                <Label htmlFor="positions_approved">Positions</Label>
                <Input
                  id="positions_approved"
                  type="number"
                  min={1}
                  {...register("positions_approved", { valueAsNumber: true })}
                />
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Job Description</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="job_description">Description</Label>
              <Textarea
                id="job_description"
                {...register("job_description")}
                rows={6}
                placeholder="Describe the role, responsibilities, and team..."
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="requirements">Requirements</Label>
              <Textarea
                id="requirements"
                {...register("requirements")}
                rows={6}
                placeholder="List required skills, experience, and qualifications..."
              />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Compensation</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid gap-4 md:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor="salary_min">Minimum Salary</Label>
                <Input
                  id="salary_min"
                  type="number"
                  {...register("salary_min", { valueAsNumber: true })}
                  placeholder="0"
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="salary_max">Maximum Salary</Label>
                <Input
                  id="salary_max"
                  type="number"
                  {...register("salary_max", { valueAsNumber: true })}
                  placeholder="0"
                />
              </div>
            </div>

            <div className="flex items-center gap-2">
              <input
                type="checkbox"
                id="is_salary_visible"
                {...register("is_salary_visible")}
                className="h-4 w-4 rounded border-gray-300"
              />
              <Label htmlFor="is_salary_visible" className="font-normal">
                Show salary range to candidates
              </Label>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Hiring Timeline</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              <Label htmlFor="sla_days">Target Days to Fill (SLA)</Label>
              <Input
                id="sla_days"
                type="number"
                min={1}
                {...register("sla_days", { valueAsNumber: true })}
              />
              <p className="text-sm text-muted-foreground">
                The target number of days to fill this position
              </p>
            </div>
          </CardContent>
        </Card>

        <div className="flex justify-end gap-4">
          <Button type="button" variant="outline" asChild>
            <Link href="/recruiting/requisitions">Cancel</Link>
          </Button>
          <Button type="submit" disabled={createRequisition.isPending}>
            {createRequisition.isPending ? "Creating..." : "Create Requisition"}
          </Button>
        </div>
      </form>
    </div>
  );
}
