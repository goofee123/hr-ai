"use client";

import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import {
  DndContext,
  DragOverlay,
  closestCorners,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
  type DragEndEvent,
  type DragStartEvent,
} from "@dnd-kit/core";
import {
  SortableContext,
  verticalListSortingStrategy,
  useSortable,
} from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { api } from "@/lib/api/client";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { ScrollArea, ScrollBar } from "@/components/ui/scroll-area";
import { useToast } from "@/hooks/use-toast";
import { formatRelativeTime } from "@/lib/utils";
import { MoreHorizontal, Clock, Star } from "lucide-react";
import type { Pipeline, PipelineCandidate } from "@/types";

interface CandidatePipelineProps {
  pipeline: Pipeline;
}

function SortableCandidateCard({ candidate }: { candidate: PipelineCandidate }) {
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({ id: candidate.application_id });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.5 : 1,
  };

  const initials = candidate.candidate_name
    .split(" ")
    .map((n) => n[0])
    .join("")
    .toUpperCase();

  return (
    <div ref={setNodeRef} style={style} {...attributes} {...listeners}>
      <Card className="mb-2 cursor-grab hover:shadow-md transition-shadow active:cursor-grabbing">
        <CardContent className="p-3">
          <div className="flex items-start gap-3">
            <Avatar className="h-8 w-8">
              <AvatarFallback className="text-xs">{initials}</AvatarFallback>
            </Avatar>
            <div className="flex-1 min-w-0">
              <p className="font-medium text-sm truncate">
                {candidate.candidate_name}
              </p>
              <p className="text-xs text-muted-foreground truncate">
                {candidate.candidate_email}
              </p>
            </div>
            <Button variant="ghost" size="icon" className="h-6 w-6">
              <MoreHorizontal className="h-3 w-3" />
            </Button>
          </div>

          <div className="mt-2 flex items-center gap-3 text-xs text-muted-foreground">
            <div className="flex items-center gap-1">
              <Clock className="h-3 w-3" />
              <span>{candidate.days_in_stage}d</span>
            </div>
            {candidate.source && (
              <Badge variant="outline" className="text-xs py-0 h-5">
                {candidate.source}
              </Badge>
            )}
            {(candidate.recruiter_rating || candidate.hiring_manager_rating) && (
              <div className="flex items-center gap-1">
                <Star className="h-3 w-3 fill-yellow-400 text-yellow-400" />
                <span>
                  {candidate.recruiter_rating || candidate.hiring_manager_rating}
                </span>
              </div>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

function CandidateCardOverlay({ candidate }: { candidate: PipelineCandidate }) {
  const initials = candidate.candidate_name
    .split(" ")
    .map((n) => n[0])
    .join("")
    .toUpperCase();

  return (
    <Card className="mb-2 shadow-lg rotate-3">
      <CardContent className="p-3">
        <div className="flex items-start gap-3">
          <Avatar className="h-8 w-8">
            <AvatarFallback className="text-xs">{initials}</AvatarFallback>
          </Avatar>
          <div className="flex-1 min-w-0">
            <p className="font-medium text-sm truncate">
              {candidate.candidate_name}
            </p>
            <p className="text-xs text-muted-foreground truncate">
              {candidate.candidate_email}
            </p>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

export function CandidatePipeline({ pipeline }: CandidatePipelineProps) {
  const queryClient = useQueryClient();
  const { toast } = useToast();
  const [activeCandidate, setActiveCandidate] = useState<PipelineCandidate | null>(null);

  const sensors = useSensors(
    useSensor(PointerSensor, {
      activationConstraint: {
        distance: 8,
      },
    }),
    useSensor(KeyboardSensor)
  );

  const moveCandidate = useMutation({
    mutationFn: async ({
      applicationId,
      stageId,
      stageName,
    }: {
      applicationId: string;
      stageId: string;
      stageName: string;
    }) => {
      return api.post(`/api/v1/recruiting/applications/${applicationId}/stage`, {
        stage: stageName,
        stage_id: stageId,
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["pipeline"] });
      toast({
        title: "Candidate moved",
        description: "The candidate has been moved to the new stage.",
      });
    },
    onError: () => {
      toast({
        title: "Error",
        description: "Failed to move candidate. Please try again.",
        variant: "destructive",
      });
    },
  });

  // Find candidate by application ID across all stages
  const findCandidate = (applicationId: string): PipelineCandidate | null => {
    for (const stage of pipeline.stages) {
      const candidate = stage.candidates.find(
        (c) => c.application_id === applicationId
      );
      if (candidate) return candidate;
    }
    return null;
  };

  // Find which stage contains a candidate
  const findStageByCandidate = (applicationId: string) => {
    return pipeline.stages.find((stage) =>
      stage.candidates.some((c) => c.application_id === applicationId)
    );
  };

  const handleDragStart = (event: DragStartEvent) => {
    const candidate = findCandidate(event.active.id as string);
    setActiveCandidate(candidate);
  };

  const handleDragEnd = (event: DragEndEvent) => {
    const { active, over } = event;
    setActiveCandidate(null);

    if (!over) return;

    const activeId = active.id as string;
    const overId = over.id as string;

    // Find source stage
    const sourceStage = findStageByCandidate(activeId);
    if (!sourceStage) return;

    // Determine target stage - could be dropping on a stage or another candidate
    let targetStage = pipeline.stages.find((s) => s.id === overId);
    if (!targetStage) {
      // Maybe dropped on another candidate - find their stage
      targetStage = findStageByCandidate(overId);
    }

    if (!targetStage || sourceStage.id === targetStage.id) return;

    // Move the candidate
    moveCandidate.mutate({
      applicationId: activeId,
      stageId: targetStage.id,
      stageName: targetStage.name,
    });
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <p className="text-sm text-muted-foreground">
          {pipeline.total_candidates} total candidates
        </p>
      </div>

      <DndContext
        sensors={sensors}
        collisionDetection={closestCorners}
        onDragStart={handleDragStart}
        onDragEnd={handleDragEnd}
      >
        <ScrollArea className="w-full">
          <div className="flex gap-4 pb-4">
            {pipeline.stages.map((stage) => (
              <div key={stage.id} className="flex-shrink-0 w-72">
                <Card className="h-full">
                  <CardHeader className="pb-2">
                    <div className="flex items-center justify-between">
                      <CardTitle className="text-sm font-medium">
                        {stage.name}
                      </CardTitle>
                      <Badge variant="secondary" className="text-xs">
                        {stage.candidate_count}
                      </Badge>
                    </div>
                  </CardHeader>
                  <CardContent className="pt-0">
                    <SortableContext
                      items={stage.candidates.map((c) => c.application_id)}
                      strategy={verticalListSortingStrategy}
                      id={stage.id}
                    >
                      <div className="min-h-[200px] space-y-0">
                        {stage.candidates.length === 0 ? (
                          <div className="flex items-center justify-center h-20 border-2 border-dashed rounded-lg">
                            <p className="text-xs text-muted-foreground">
                              No candidates
                            </p>
                          </div>
                        ) : (
                          stage.candidates.map((candidate) => (
                            <SortableCandidateCard
                              key={candidate.application_id}
                              candidate={candidate}
                            />
                          ))
                        )}
                      </div>
                    </SortableContext>
                  </CardContent>
                </Card>
              </div>
            ))}
          </div>
          <ScrollBar orientation="horizontal" />
        </ScrollArea>

        <DragOverlay>
          {activeCandidate ? (
            <CandidateCardOverlay candidate={activeCandidate} />
          ) : null}
        </DragOverlay>
      </DndContext>
    </div>
  );
}
