"use client";

import { useState } from "react";
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
} from "lucide-react";
import {
  mockCandidates,
  mockObservations,
  mockActivityEvents,
  mockResumes,
  mockJobMatches,
  formatEventType,
  getEventIconClass,
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
    <div className="flex items-center gap-2">
      <div className={`w-2 h-2 rounded-full ${color}`} />
      <span className="text-xs text-muted-foreground">{label}</span>
    </div>
  );
}

function ConfidenceBadge({ confidence }: { confidence: number }) {
  const pct = Math.round(confidence * 100);
  return (
    <Badge
      variant={pct >= 90 ? "default" : pct >= 70 ? "secondary" : "outline"}
      className="text-xs"
    >
      {pct}% confidence
    </Badge>
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

  if (!candidate) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[400px]">
        <p className="text-muted-foreground">Candidate not found</p>
        <Button asChild className="mt-4">
          <Link href="/recruiting/candidates">Back to Candidates</Link>
        </Button>
      </div>
    );
  }

  const initials = `${candidate.first_name[0]}${candidate.last_name[0]}`.toUpperCase();

  // Group observations by field type for display
  const skillObservations = observations.filter((o) =>
    o.field_name.toLowerCase().includes("skill")
  );
  const otherObservations = observations.filter(
    (o) => !o.field_name.toLowerCase().includes("skill")
  );

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start gap-4">
        <Button variant="ghost" size="icon" asChild>
          <Link href="/recruiting/candidates">
            <ArrowLeft className="h-4 w-4" />
          </Link>
        </Button>

        <Avatar className="h-16 w-16">
          <AvatarFallback className="text-xl">{initials}</AvatarFallback>
        </Avatar>

        <div className="flex-1">
          <h1 className="text-2xl font-bold">
            {candidate.first_name} {candidate.last_name}
          </h1>
          <p className="text-muted-foreground">
            {candidate.current_title} at {candidate.current_company}
          </p>
          <div className="flex items-center gap-4 mt-2 text-sm text-muted-foreground">
            <span className="flex items-center gap-1">
              <Mail className="h-3 w-3" />
              {candidate.email}
            </span>
            <span className="flex items-center gap-1">
              <Phone className="h-3 w-3" />
              {candidate.phone}
            </span>
            <a
              href={candidate.linkedin_url}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-1 hover:text-primary"
            >
              <Linkedin className="h-3 w-3" />
              LinkedIn
            </a>
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
            Observations ({observations.length})
          </TabsTrigger>
          <TabsTrigger value="activity">
            Activity ({activityEvents.length})
          </TabsTrigger>
          <TabsTrigger value="documents">
            Documents ({resumes.length})
          </TabsTrigger>
          <TabsTrigger value="matches">
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
                  <span className="font-medium">{candidate.years_experience} years</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Source</span>
                  <Badge variant="secondary">{candidate.source}</Badge>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Added</span>
                  <span>{formatDate(candidate.created_at)}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Last Updated</span>
                  <span>{formatDate(candidate.updated_at)}</span>
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
                  {candidate.skills.map((skill) => (
                    <Badge key={skill} variant="secondary">
                      {skill}
                    </Badge>
                  ))}
                </div>
              </CardContent>
            </Card>

            {/* Job Matches */}
            <Card className="md:col-span-2">
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
                          <p className="text-sm text-muted-foreground">
                            {match.department}
                          </p>
                        </div>
                        <div className="flex items-center gap-4">
                          <div className="text-right">
                            <p className="font-medium text-lg">
                              {Math.round(match.match_score * 100)}%
                            </p>
                            <p className="text-xs text-muted-foreground">Match</p>
                          </div>
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
          <Card>
            <CardHeader>
              <CardTitle className="text-sm flex items-center gap-2">
                <Sparkles className="h-4 w-4" />
                Extracted Facts (with Confidence & Relevance)
              </CardTitle>
            </CardHeader>
            <CardContent>
              {observations.length > 0 ? (
                <div className="space-y-6">
                  {/* Skills Section */}
                  {skillObservations.length > 0 && (
                    <div>
                      <h4 className="font-medium mb-3">Skills & Certifications</h4>
                      <div className="space-y-2">
                        {skillObservations.map((obs) => (
                          <div
                            key={obs.id}
                            className={`flex items-center justify-between p-3 border rounded-lg ${
                              obs.relevance_score < 0.75 ? "opacity-70" : ""
                            }`}
                          >
                            <div className="flex items-center gap-3">
                              <div>
                                <p className="font-medium">{obs.field_value}</p>
                                <p className="text-xs text-muted-foreground">
                                  Extracted {formatDate(obs.extracted_at)} via{" "}
                                  {obs.extraction_method}
                                </p>
                              </div>
                            </div>
                            <div className="flex items-center gap-4">
                              <RelevanceIndicator score={obs.relevance_score} />
                              <ConfidenceBadge confidence={obs.confidence} />
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Other Observations */}
                  {otherObservations.length > 0 && (
                    <div>
                      <h4 className="font-medium mb-3">Profile Information</h4>
                      <div className="space-y-2">
                        {otherObservations.map((obs) => (
                          <div
                            key={obs.id}
                            className="flex items-center justify-between p-3 border rounded-lg"
                          >
                            <div>
                              <p className="text-sm text-muted-foreground capitalize">
                                {obs.field_name.replace(/_/g, " ")}
                              </p>
                              <p className="font-medium">{obs.field_value}</p>
                            </div>
                            <div className="flex items-center gap-4">
                              <RelevanceIndicator score={obs.relevance_score} />
                              <ConfidenceBadge confidence={obs.confidence} />
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Relevance Legend */}
                  <div className="mt-6 p-4 bg-muted rounded-lg">
                    <p className="text-sm font-medium mb-2">Relevance Decay Legend</p>
                    <div className="flex gap-6 text-xs">
                      <span className="flex items-center gap-1">
                        <div className="w-2 h-2 rounded-full bg-green-500" />
                        Current (&lt;1 year)
                      </span>
                      <span className="flex items-center gap-1">
                        <div className="w-2 h-2 rounded-full bg-yellow-500" />
                        Recent (1-3 years)
                      </span>
                      <span className="flex items-center gap-1">
                        <div className="w-2 h-2 rounded-full bg-orange-500" />
                        Aging (3-5 years)
                      </span>
                      <span className="flex items-center gap-1">
                        <div className="w-2 h-2 rounded-full bg-red-500" />
                        Outdated (&gt;5 years)
                      </span>
                    </div>
                  </div>
                </div>
              ) : (
                <p className="text-muted-foreground">No observations extracted yet</p>
              )}
            </CardContent>
          </Card>
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
                    {activityEvents.map((event, index) => (
                      <div key={event.id} className="relative pl-10">
                        {/* Timeline dot */}
                        <div className="absolute left-2 top-1 w-4 h-4 rounded-full bg-background border-2 border-primary flex items-center justify-center">
                          <EventIcon eventType={event.event_type} />
                        </div>

                        <div className="border rounded-lg p-4">
                          <div className="flex items-start justify-between">
                            <div>
                              <p className="font-medium">
                                {formatEventType(event.event_type)}
                              </p>
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
                            event.event_data.delta && (
                              <div className="mt-2 p-2 bg-muted rounded text-sm">
                                <p className="text-muted-foreground">
                                  {event.event_data.old_value as string} →{" "}
                                  <span className="font-medium">
                                    {event.event_data.new_value as string}
                                  </span>
                                </p>
                                <p className="text-xs text-green-600">
                                  {event.event_data.delta as string}
                                </p>
                              </div>
                            )}

                          {event.event_type === "stage_changed" && (
                            <div className="mt-2 flex items-center gap-2 text-sm">
                              <Badge variant="outline">
                                {event.event_data.from_stage as string}
                              </Badge>
                              <ArrowRightLeft className="h-3 w-3" />
                              <Badge>
                                {event.event_data.to_stage as string}
                              </Badge>
                            </div>
                          )}

                          {event.event_type === "job_match_found" && (
                            <div className="mt-2 flex items-center gap-2 text-sm">
                              <Target className="h-4 w-4 text-green-500" />
                              <span>{event.event_data.job_title as string}</span>
                              <Badge variant="secondary">
                                {Math.round((event.event_data.match_score as number) * 100)}%
                                match
                              </Badge>
                            </div>
                          )}

                          {event.event_type === "note_added" && (
                            <p className="mt-2 text-sm italic">
                              &quot;{event.event_data.note as string}&quot;
                            </p>
                          )}

                          {event.event_type === "resume_uploaded" && (
                            <div className="mt-2 flex items-center gap-2 text-sm">
                              <FileText className="h-4 w-4" />
                              <span>{event.event_data.file_name as string}</span>
                              <Badge variant="outline" className="text-xs">
                                {event.event_data.source as string}
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
              <div className="space-y-4">
                {resumes.map((resume) => (
                  <div
                    key={resume.id}
                    className={`flex items-center justify-between p-4 border rounded-lg ${
                      resume.is_primary ? "border-primary" : ""
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
                          resume.extraction_status === "completed"
                            ? "secondary"
                            : "outline"
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
                        View
                      </Button>
                    </div>
                  </div>
                ))}
              </div>
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
                            <span>
                              {Math.round(match.match_breakdown.experience * 100)}%
                            </span>
                          </div>
                          <Progress value={match.match_breakdown.experience * 100} />
                        </div>
                        <div>
                          <div className="flex justify-between text-sm mb-1">
                            <span>Location Match</span>
                            <span>
                              {Math.round(match.match_breakdown.location * 100)}%
                            </span>
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
  );
}
