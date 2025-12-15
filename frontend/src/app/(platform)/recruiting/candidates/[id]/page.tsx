"use client";

import { useState, useMemo } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Progress } from "@/components/ui/progress";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import {
  ArrowLeft,
  Mail,
  Phone,
  Linkedin,
  FileText,
  Clock,
  Target,
  Activity,
  AlertTriangle,
  CheckCircle,
  Upload,
  Eye,
  MessageSquare,
  ArrowRightLeft,
  Sparkles,
  Brain,
  Info,
  Download,
  ExternalLink,
  Users,
} from "lucide-react";
import {
  mockCandidates,
  mockObservations,
  mockActivityEvents,
  mockResumes,
  mockJobMatches,
  mockDuplicateCandidates,
  formatEventType,
  getEventIconClass,
  getConfidenceLabel,
  getConfidenceLabelColor,
  type MockObservation,
  type ConfidenceLabel,
} from "@/lib/mock-data/recruiting";

function formatDate(dateString: string) {
  return new Date(dateString).toLocaleDateString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

function formatDateTime(dateString: string) {
  return new Date(dateString).toLocaleString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function RelevanceIndicator({ score }: { score: number }) {
  const color =
    score >= 0.9
      ? "bg-green-500"
      : score >= 0.75
      ? "bg-yellow-500"
      : score >= 0.5
      ? "bg-orange-500"
      : "bg-red-500";

  const label =
    score >= 0.9
      ? "Current"
      : score >= 0.75
      ? "Recent"
      : score >= 0.5
      ? "Aging"
      : "Outdated";

  return (
    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger>
          <div className="flex items-center gap-2">
            <div className={`w-2 h-2 rounded-full ${color}`} />
            <span className="text-xs text-muted-foreground">{label}</span>
          </div>
        </TooltipTrigger>
        <TooltipContent>
          <p className="text-xs">
            Relevance: {Math.round(score * 100)}%
            {score < 1 && " (skill age decay applied)"}
          </p>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}

function ConfidenceBadge({ confidence, label }: { confidence: number; label: ConfidenceLabel }) {
  const color = getConfidenceLabelColor(label);

  return (
    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger>
          <Badge variant="outline" className={`text-xs ${color}`}>
            {label}
          </Badge>
        </TooltipTrigger>
        <TooltipContent className="max-w-xs">
          <p className="text-sm">
            <strong>Confidence: {Math.round(confidence * 100)}%</strong>
            <br />
            {label === "Explicit" && "High certainty - explicitly stated in source document"}
            {label === "Very Likely" && "Good confidence - clearly implied or standard format"}
            {label === "Inferred" && "Moderate confidence - inferred from context"}
            {label === "Uncertain" && "Low confidence - may need verification"}
          </p>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}

function EventIcon({ eventType }: { eventType: string }) {
  const iconClass = getEventIconClass(eventType);
  switch (eventType) {
    case "resume_uploaded":
      return <Upload className={`h-4 w-4 ${iconClass}`} />;
    case "profile_viewed":
      return <Eye className={`h-4 w-4 ${iconClass}`} />;
    case "job_match_found":
      return <Target className={`h-4 w-4 ${iconClass}`} />;
    case "note_added":
      return <MessageSquare className={`h-4 w-4 ${iconClass}`} />;
    case "stage_changed":
      return <ArrowRightLeft className={`h-4 w-4 ${iconClass}`} />;
    case "observation_updated":
      return <Sparkles className={`h-4 w-4 ${iconClass}`} />;
    case "application_submitted":
      return <FileText className={`h-4 w-4 ${iconClass}`} />;
    default:
      return <Activity className={`h-4 w-4 ${iconClass}`} />;
  }
}

export default function CandidateDetailPage() {
  const params = useParams();
  const candidateId = params.id as string;
  const [activeTab, setActiveTab] = useState("overview");

  // Use mock data - in production this would come from API
  const candidate = mockCandidates.find((c) => c.id === candidateId);
  const observations = mockObservations[candidateId] || [];
  const activityEvents = mockActivityEvents[candidateId] || [];
  const resumes = mockResumes[candidateId] || [];
  const jobMatches = mockJobMatches[candidateId] || [];
  const duplicates = mockDuplicateCandidates[candidateId] || [];

  // Group observations by category
  const groupedObservations = useMemo(() => {
    return observations.reduce((acc, obs) => {
      let group = "other";
      if (obs.fieldName.includes("skill") || obs.fieldName.includes("certification")) {
        group = "skills";
      } else if (obs.fieldName.includes("education") || obs.fieldName.includes("degree")) {
        group = "education";
      } else if (
        obs.fieldName.includes("experience") ||
        obs.fieldName.includes("title") ||
        obs.fieldName.includes("company")
      ) {
        group = "experience";
      }
      if (!acc[group]) acc[group] = [];
      acc[group].push(obs);
      return acc;
    }, {} as Record<string, MockObservation[]>);
  }, [observations]);

  // Get confidence stats
  const confidenceStats = useMemo(() => {
    const stats: Record<ConfidenceLabel, number> = {
      Explicit: 0,
      "Very Likely": 0,
      Inferred: 0,
      Uncertain: 0,
    };
    observations.forEach((obs) => {
      stats[obs.confidenceLabel]++;
    });
    return stats;
  }, [observations]);

  if (!candidate) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[400px]">
        <AlertTriangle className="h-12 w-12 text-yellow-500 mb-4" />
        <p className="text-lg font-medium">Candidate not found</p>
        <p className="text-muted-foreground mb-4">The candidate ID does not exist in the system.</p>
        <Button asChild className="mt-4">
          <Link href="/recruiting/candidates">
            <ArrowLeft className="mr-2 h-4 w-4" />
            Back to Candidates
          </Link>
        </Button>
      </div>
    );
  }

  const initials = `${candidate.firstName[0]}${candidate.lastName[0]}`.toUpperCase();

  return (
    <TooltipProvider>
      <div className="space-y-6">
        {/* Back Button */}
        <Button variant="ghost" size="sm" asChild>
          <Link href="/recruiting/candidates">
            <ArrowLeft className="mr-2 h-4 w-4" />
            Back to Candidates
          </Link>
        </Button>

        {/* Duplicate Warning */}
        {duplicates.length > 0 && (
          <Card className="bg-yellow-50 border-yellow-200">
            <CardContent className="p-4">
              <div className="flex items-start gap-3">
                <AlertTriangle className="h-5 w-5 text-yellow-600 mt-0.5" />
                <div className="flex-1">
                  <h4 className="font-medium text-yellow-900">
                    Potential Duplicate Candidates Detected
                  </h4>
                  <div className="mt-2 space-y-2">
                    {duplicates.map((dup) => (
                      <div
                        key={dup.candidate_id}
                        className="flex items-center justify-between bg-white/50 p-2 rounded-md"
                      >
                        <div>
                          <span className="font-medium">{dup.candidate_name}</span>
                          <span className="text-sm text-yellow-800 ml-2">
                            ({Math.round(dup.match_score * 100)}% match)
                          </span>
                          <div className="text-xs text-yellow-700 mt-0.5">
                            {dup.reasons.map((r) => r.detail || r.type.replace("_", " ")).join(" • ")}
                          </div>
                        </div>
                        <Badge
                          variant="outline"
                          className={
                            dup.match_type === "hard"
                              ? "bg-red-100 text-red-800 border-red-200"
                              : dup.match_type === "strong"
                              ? "bg-orange-100 text-orange-800 border-orange-200"
                              : "bg-yellow-100 text-yellow-800 border-yellow-200"
                          }
                        >
                          {dup.match_type === "hard"
                            ? "Hard Match"
                            : dup.match_type === "strong"
                            ? "Strong Match"
                            : "Review Needed"}
                        </Badge>
                      </div>
                    ))}
                  </div>
                  <Button variant="outline" size="sm" className="mt-3 bg-white" asChild>
                    <Link href={`/recruiting/merge-queue?candidate=${candidateId}`}>
                      <Users className="mr-2 h-4 w-4" />
                      Review in Merge Queue
                    </Link>
                  </Button>
                </div>
              </div>
            </CardContent>
          </Card>
        )}

        {/* Header */}
        <div className="flex items-start gap-4">
          <Avatar className="h-16 w-16">
            <AvatarFallback className="text-xl bg-primary/10 text-primary">
              {initials}
            </AvatarFallback>
          </Avatar>

          <div className="flex-1">
            <div className="flex items-center gap-3">
              <h1 className="text-2xl font-bold">
                {candidate.firstName} {candidate.lastName}
              </h1>
              {observations.length > 0 && (
                <Badge variant="outline" className="bg-green-50 text-green-700 border-green-200">
                  <Sparkles className="h-3 w-3 mr-1" />
                  AI Enriched
                </Badge>
              )}
            </div>
            <p className="text-muted-foreground">
              {candidate.currentTitle} at {candidate.currentCompany}
            </p>
            <div className="flex items-center gap-4 mt-2 text-sm text-muted-foreground flex-wrap">
              <span className="flex items-center gap-1">
                <Mail className="h-3 w-3" />
                {candidate.email}
              </span>
              <span className="flex items-center gap-1">
                <Phone className="h-3 w-3" />
                {candidate.phone}
              </span>
              {candidate.linkedinUrl && (
                <a
                  href={candidate.linkedinUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center gap-1 hover:text-primary"
                >
                  <Linkedin className="h-3 w-3" />
                  LinkedIn
                  <ExternalLink className="h-3 w-3" />
                </a>
              )}
            </div>
          </div>

          <div className="flex gap-2">
            <Button variant="outline">Add Note</Button>
            <Button>Add to Job</Button>
          </div>
        </div>

        {/* Tabs */}
        <Tabs value={activeTab} onValueChange={setActiveTab}>
          <TabsList>
            <TabsTrigger value="overview">Overview</TabsTrigger>
            <TabsTrigger value="observations">
              <Brain className="mr-1 h-3 w-3" />
              Observations ({observations.length})
            </TabsTrigger>
            <TabsTrigger value="activity">
              <Activity className="mr-1 h-3 w-3" />
              Activity ({activityEvents.length})
            </TabsTrigger>
            <TabsTrigger value="documents">
              <FileText className="mr-1 h-3 w-3" />
              Documents ({resumes.length})
            </TabsTrigger>
            <TabsTrigger value="matches">
              <Target className="mr-1 h-3 w-3" />
              Job Matches ({jobMatches.length})
            </TabsTrigger>
          </TabsList>

          {/* Overview Tab */}
          <TabsContent value="overview" className="space-y-6">
            <div className="grid gap-6 md:grid-cols-2">
              {/* Quick Stats */}
              <Card>
                <CardHeader>
                  <CardTitle className="text-sm">Candidate Summary</CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Experience</span>
                    <span className="font-medium">{candidate.yearsExperience} years</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Source</span>
                    <Badge variant="secondary">{candidate.source}</Badge>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Added</span>
                    <span>{formatDate(candidate.createdAt)}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Last Updated</span>
                    <span>{formatDate(candidate.updatedAt)}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Observations</span>
                    <span className="font-medium">{observations.length}</span>
                  </div>
                </CardContent>
              </Card>

              {/* Top Skills */}
              <Card>
                <CardHeader>
                  <CardTitle className="text-sm">Skills</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="flex flex-wrap gap-2">
                    {candidate.topSkills.map((skill) => (
                      <Badge key={skill} variant="secondary">
                        {skill}
                      </Badge>
                    ))}
                  </div>
                </CardContent>
              </Card>

              {/* Confidence Summary */}
              {observations.length > 0 && (
                <Card>
                  <CardHeader>
                    <CardTitle className="text-sm flex items-center gap-2">
                      <Brain className="h-4 w-4" />
                      Observation Confidence
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="space-y-2">
                      {(["Explicit", "Very Likely", "Inferred", "Uncertain"] as ConfidenceLabel[]).map(
                        (label) => {
                          const count = confidenceStats[label];
                          const color = getConfidenceLabelColor(label);
                          return (
                            <div key={label} className="flex items-center justify-between">
                              <Badge variant="outline" className={color}>
                                {label}
                              </Badge>
                              <span className="text-sm font-medium">{count}</span>
                            </div>
                          );
                        }
                      )}
                    </div>
                  </CardContent>
                </Card>
              )}

              {/* Job Matches */}
              <Card className={observations.length > 0 ? "" : "md:col-span-2"}>
                <CardHeader>
                  <CardTitle className="text-sm">Matching Jobs</CardTitle>
                </CardHeader>
                <CardContent>
                  {jobMatches.length > 0 ? (
                    <div className="space-y-3">
                      {jobMatches.map((match) => (
                        <div
                          key={match.job_id}
                          className="flex items-center justify-between p-3 border rounded-lg"
                        >
                          <div>
                            <p className="font-medium">{match.job_title}</p>
                            <p className="text-sm text-muted-foreground">{match.department}</p>
                          </div>
                          <div className="flex items-center gap-4">
                            <Badge
                              variant="outline"
                              className={
                                match.match_score >= 0.85
                                  ? "bg-green-50 text-green-700 border-green-200"
                                  : match.match_score >= 0.7
                                  ? "bg-blue-50 text-blue-700 border-blue-200"
                                  : ""
                              }
                            >
                              {Math.round(match.match_score * 100)}%
                            </Badge>
                            <Button size="sm">View Job</Button>
                          </div>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p className="text-muted-foreground">No job matches yet</p>
                  )}
                </CardContent>
              </Card>
            </div>
          </TabsContent>

          {/* Observations Tab */}
          <TabsContent value="observations" className="space-y-6">
            <div className="grid gap-6 md:grid-cols-3">
              <Card className="md:col-span-2">
                <CardHeader>
                  <CardTitle className="text-sm flex items-center gap-2">
                    <Brain className="h-4 w-4" />
                    Extracted Facts with Confidence & Model Provenance
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  {observations.length > 0 ? (
                    <div className="space-y-6">
                      {/* Skills Section */}
                      {groupedObservations.skills && groupedObservations.skills.length > 0 && (
                        <div>
                          <h4 className="font-medium mb-3">Skills & Certifications</h4>
                          <div className="space-y-2">
                            {groupedObservations.skills.map((obs) => (
                              <div
                                key={obs.id}
                                className={`flex items-start justify-between p-3 border rounded-lg ${
                                  obs.relevanceScore < 0.75 ? "opacity-70 bg-muted/50" : ""
                                }`}
                              >
                                <div className="flex-1">
                                  <p className="font-medium">{obs.fieldValue}</p>
                                  <div className="flex items-center gap-2 mt-1 text-xs text-muted-foreground flex-wrap">
                                    <Badge variant="outline" className="text-[10px]">
                                      {obs.extractionMethod === "llm"
                                        ? "AI"
                                        : obs.extractionMethod === "external_scrape"
                                        ? "Enriched"
                                        : obs.extractionMethod}
                                    </Badge>
                                    <span>Extracted {formatDate(obs.extractedAt)}</span>
                                    {obs.modelName && (
                                      <Tooltip>
                                        <TooltipTrigger>
                                          <span className="flex items-center gap-1">
                                            <Brain className="h-3 w-3" />
                                            {obs.modelName}
                                          </span>
                                        </TooltipTrigger>
                                        <TooltipContent>
                                          <p className="text-xs">
                                            Model: {obs.modelName} {obs.modelVersion}
                                            <br />
                                            Prompt: {obs.promptVersion}
                                          </p>
                                        </TooltipContent>
                                      </Tooltip>
                                    )}
                                  </div>
                                </div>
                                <div className="flex items-center gap-3">
                                  <RelevanceIndicator score={obs.relevanceScore} />
                                  <ConfidenceBadge
                                    confidence={obs.confidence}
                                    label={obs.confidenceLabel}
                                  />
                                </div>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}

                      {/* Experience Section */}
                      {groupedObservations.experience && groupedObservations.experience.length > 0 && (
                        <div>
                          <h4 className="font-medium mb-3">Experience</h4>
                          <div className="space-y-2">
                            {groupedObservations.experience.map((obs) => (
                              <div
                                key={obs.id}
                                className="flex items-start justify-between p-3 border rounded-lg"
                              >
                                <div className="flex-1">
                                  <p className="text-sm text-muted-foreground capitalize">
                                    {obs.fieldName.replace(/_/g, " ")}
                                  </p>
                                  <p className="font-medium">{obs.fieldValue}</p>
                                  {obs.modelName && (
                                    <p className="text-xs text-muted-foreground mt-1">
                                      via {obs.modelName} • {obs.promptVersion}
                                    </p>
                                  )}
                                </div>
                                <ConfidenceBadge
                                  confidence={obs.confidence}
                                  label={obs.confidenceLabel}
                                />
                              </div>
                            ))}
                          </div>
                        </div>
                      )}

                      {/* Other Observations */}
                      {groupedObservations.other && groupedObservations.other.length > 0 && (
                        <div>
                          <h4 className="font-medium mb-3">Other Information</h4>
                          <div className="space-y-2">
                            {groupedObservations.other.map((obs) => (
                              <div
                                key={obs.id}
                                className="flex items-start justify-between p-3 border rounded-lg"
                              >
                                <div className="flex-1">
                                  <p className="text-sm text-muted-foreground capitalize">
                                    {obs.fieldName.replace(/_/g, " ")}
                                  </p>
                                  <p className="font-medium">{obs.fieldValue}</p>
                                  {obs.sourceUrl && (
                                    <a
                                      href={obs.sourceUrl}
                                      target="_blank"
                                      rel="noopener noreferrer"
                                      className="text-xs text-primary hover:underline flex items-center gap-1 mt-1"
                                    >
                                      Source
                                      <ExternalLink className="h-3 w-3" />
                                    </a>
                                  )}
                                </div>
                                <ConfidenceBadge
                                  confidence={obs.confidence}
                                  label={obs.confidenceLabel}
                                />
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  ) : (
                    <div className="text-center py-8">
                      <Brain className="h-12 w-12 mx-auto text-muted-foreground/50 mb-4" />
                      <p className="text-muted-foreground">No observations extracted yet</p>
                      <p className="text-sm text-muted-foreground mt-1">
                        Upload a resume to extract facts automatically
                      </p>
                    </div>
                  )}
                </CardContent>
              </Card>

              {/* Sidebar */}
              <div className="space-y-4">
                {/* Confidence Legend */}
                <Card>
                  <CardHeader>
                    <CardTitle className="text-sm">Confidence Labels</CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-2">
                    {(["Explicit", "Very Likely", "Inferred", "Uncertain"] as ConfidenceLabel[]).map(
                      (label) => {
                        const color = getConfidenceLabelColor(label);
                        const description = {
                          Explicit: "95%+ - explicitly stated",
                          "Very Likely": "80-94% - clearly implied",
                          Inferred: "65-79% - inferred from context",
                          Uncertain: "<65% - needs verification",
                        };
                        return (
                          <div key={label} className="flex items-center justify-between text-xs">
                            <Badge variant="outline" className={color}>
                              {label}
                            </Badge>
                            <span className="text-muted-foreground">
                              {description[label]}
                            </span>
                          </div>
                        );
                      }
                    )}
                  </CardContent>
                </Card>

                {/* Relevance Legend */}
                <Card>
                  <CardHeader>
                    <CardTitle className="text-sm">Relevance Decay</CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-2">
                    <div className="flex items-center gap-2 text-xs">
                      <div className="w-2 h-2 rounded-full bg-green-500" />
                      <span>Current (&lt;1 year) - 100%</span>
                    </div>
                    <div className="flex items-center gap-2 text-xs">
                      <div className="w-2 h-2 rounded-full bg-yellow-500" />
                      <span>Recent (1-3 years) - 90%</span>
                    </div>
                    <div className="flex items-center gap-2 text-xs">
                      <div className="w-2 h-2 rounded-full bg-orange-500" />
                      <span>Aging (3-5 years) - 75%</span>
                    </div>
                    <div className="flex items-center gap-2 text-xs">
                      <div className="w-2 h-2 rounded-full bg-red-500" />
                      <span>Outdated (&gt;5 years) - 50%</span>
                    </div>
                  </CardContent>
                </Card>

                <Card className="bg-blue-50/50 border-blue-200">
                  <CardContent className="p-4">
                    <div className="flex items-start gap-2">
                      <Info className="h-4 w-4 text-blue-600 mt-0.5" />
                      <div className="text-xs text-blue-800">
                        <p className="font-medium mb-1">About Model Provenance</p>
                        <p>
                          Each observation shows which AI model and prompt version was used,
                          enabling debugging and legal traceability.
                        </p>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              </div>
            </div>
          </TabsContent>

          {/* Activity Tab */}
          <TabsContent value="activity">
            <Card>
              <CardHeader>
                <CardTitle className="text-sm flex items-center gap-2">
                  <Activity className="h-4 w-4" />
                  Complete Activity History
                </CardTitle>
              </CardHeader>
              <CardContent>
                <ScrollArea className="h-[500px] pr-4">
                  <div className="relative">
                    {/* Timeline line */}
                    <div className="absolute left-4 top-0 bottom-0 w-px bg-border" />

                    <div className="space-y-6">
                      {activityEvents
                        .sort(
                          (a, b) =>
                            new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
                        )
                        .map((event) => (
                          <div key={event.id} className="relative pl-10">
                            {/* Timeline dot */}
                            <div className="absolute left-2 top-1 w-4 h-4 rounded-full bg-background border-2 border-primary flex items-center justify-center">
                              <EventIcon eventType={event.event_type} />
                            </div>

                            <div className="border rounded-lg p-4">
                              <div className="flex items-start justify-between">
                                <div>
                                  <p className="font-medium">{formatEventType(event.event_type)}</p>
                                  <p className="text-sm text-muted-foreground">
                                    by {event.user_name}
                                  </p>
                                </div>
                                <span className="text-xs text-muted-foreground">
                                  {formatDateTime(event.created_at)}
                                </span>
                              </div>

                              {/* Event-specific details */}
                              {event.event_type === "observation_updated" &&
                                (event.event_data as { delta?: string }).delta && (
                                  <div className="mt-2 p-2 bg-muted rounded text-sm">
                                    <p className="text-muted-foreground">
                                      {(event.event_data as { old_value?: string }).old_value} →{" "}
                                      <span className="font-medium">
                                        {(event.event_data as { new_value?: string }).new_value}
                                      </span>
                                    </p>
                                    <p className="text-xs text-green-600">
                                      {(event.event_data as { delta?: string }).delta}
                                    </p>
                                  </div>
                                )}

                              {event.event_type === "stage_changed" && (
                                <div className="mt-2 flex items-center gap-2 text-sm">
                                  <Badge variant="outline">
                                    {(event.event_data as { from_stage?: string }).from_stage}
                                  </Badge>
                                  <ArrowRightLeft className="h-3 w-3" />
                                  <Badge>
                                    {(event.event_data as { to_stage?: string }).to_stage}
                                  </Badge>
                                </div>
                              )}

                              {event.event_type === "job_match_found" && (
                                <div className="mt-2 flex items-center gap-2 text-sm">
                                  <Target className="h-4 w-4 text-green-500" />
                                  <span>
                                    {(event.event_data as { job_title?: string }).job_title}
                                  </span>
                                  <Badge variant="secondary">
                                    {Math.round(
                                      ((event.event_data as { match_score?: number }).match_score ||
                                        0) * 100
                                    )}
                                    % match
                                  </Badge>
                                </div>
                              )}

                              {event.event_type === "note_added" && (
                                <p className="mt-2 text-sm italic">
                                  &quot;{(event.event_data as { note?: string }).note}&quot;
                                </p>
                              )}

                              {event.event_type === "resume_uploaded" && (
                                <div className="mt-2 flex items-center gap-2 text-sm">
                                  <FileText className="h-4 w-4" />
                                  <span>
                                    {(event.event_data as { file_name?: string }).file_name}
                                  </span>
                                  <Badge variant="outline" className="text-xs">
                                    {(event.event_data as { source?: string }).source}
                                  </Badge>
                                </div>
                              )}
                            </div>
                          </div>
                        ))}
                    </div>
                  </div>
                </ScrollArea>
              </CardContent>
            </Card>
          </TabsContent>

          {/* Documents Tab */}
          <TabsContent value="documents">
            <Card>
              <CardHeader className="flex flex-row items-center justify-between">
                <CardTitle className="text-sm flex items-center gap-2">
                  <FileText className="h-4 w-4" />
                  Resume History
                </CardTitle>
                <Button size="sm">
                  <Upload className="h-4 w-4 mr-2" />
                  Upload Resume
                </Button>
              </CardHeader>
              <CardContent>
                {resumes.length > 0 ? (
                  <div className="space-y-4">
                    {resumes.map((resume) => (
                      <div
                        key={resume.id}
                        className={`flex items-center justify-between p-4 border rounded-lg ${
                          resume.is_primary ? "border-primary bg-primary/5" : ""
                        }`}
                      >
                        <div className="flex items-center gap-3">
                          <FileText className="h-8 w-8 text-muted-foreground" />
                          <div>
                            <div className="flex items-center gap-2">
                              <p className="font-medium">{resume.file_name}</p>
                              {resume.is_primary && (
                                <Badge variant="default" className="text-xs">
                                  Primary
                                </Badge>
                              )}
                            </div>
                            <p className="text-sm text-muted-foreground">
                              Uploaded {formatDateTime(resume.uploaded_at)} via {resume.source}
                            </p>
                          </div>
                        </div>
                        <div className="flex items-center gap-2">
                          <Badge
                            variant={
                              resume.extraction_status === "completed" ? "secondary" : "outline"
                            }
                          >
                            {resume.extraction_status === "completed" ? (
                              <CheckCircle className="h-3 w-3 mr-1" />
                            ) : (
                              <Clock className="h-3 w-3 mr-1" />
                            )}
                            {resume.extraction_status}
                          </Badge>
                          <Button variant="outline" size="sm">
                            <Download className="h-4 w-4" />
                          </Button>
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="text-center py-8">
                    <FileText className="h-12 w-12 mx-auto text-muted-foreground/50 mb-4" />
                    <p className="text-muted-foreground">No documents uploaded yet</p>
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>

          {/* Job Matches Tab */}
          <TabsContent value="matches">
            <Card>
              <CardHeader>
                <CardTitle className="text-sm flex items-center gap-2">
                  <Target className="h-4 w-4" />
                  Job Match Analysis
                </CardTitle>
              </CardHeader>
              <CardContent>
                {jobMatches.length > 0 ? (
                  <div className="space-y-6">
                    {jobMatches.map((match) => (
                      <div key={match.job_id} className="border rounded-lg p-4">
                        <div className="flex items-start justify-between mb-4">
                          <div>
                            <h4 className="font-medium text-lg">{match.job_title}</h4>
                            <p className="text-muted-foreground">{match.department}</p>
                          </div>
                          <div className="text-right">
                            <p className="text-3xl font-bold text-primary">
                              {Math.round(match.match_score * 100)}%
                            </p>
                            <p className="text-xs text-muted-foreground">Overall Match</p>
                          </div>
                        </div>

                        <div className="space-y-3">
                          <div>
                            <div className="flex justify-between text-sm mb-1">
                              <span>Skills Match</span>
                              <span>{Math.round(match.match_breakdown.skills * 100)}%</span>
                            </div>
                            <Progress value={match.match_breakdown.skills * 100} />
                          </div>
                          <div>
                            <div className="flex justify-between text-sm mb-1">
                              <span>Experience Match</span>
                              <span>{Math.round(match.match_breakdown.experience * 100)}%</span>
                            </div>
                            <Progress value={match.match_breakdown.experience * 100} />
                          </div>
                          <div>
                            <div className="flex justify-between text-sm mb-1">
                              <span>Location Match</span>
                              <span>{Math.round(match.match_breakdown.location * 100)}%</span>
                            </div>
                            <Progress value={match.match_breakdown.location * 100} />
                          </div>
                        </div>

                        <div className="mt-4 flex gap-2">
                          <Button className="flex-1">Apply to This Job</Button>
                          <Button variant="outline">View Job Details</Button>
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="text-center py-8">
                    <Target className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
                    <p className="text-muted-foreground">No job matches found</p>
                    <p className="text-sm text-muted-foreground">
                      Matches will appear when this candidate&apos;s profile matches open positions
                    </p>
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>
      </div>
    </TooltipProvider>
  );
}
