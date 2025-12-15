"use client";

import { useState, useMemo } from "react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import {
  Plus,
  Search,
  Filter,
  Mail,
  Phone,
  Linkedin,
  ChevronDown,
  ChevronRight,
  Clock,
  FileText,
  AlertTriangle,
  CheckCircle2,
  Info,
  Eye,
  Briefcase,
  GraduationCap,
  ExternalLink,
  Sparkles,
  Users,
  Brain,
} from "lucide-react";
import {
  mockCandidates,
  mockObservations,
  mockJobMatches,
  mockDuplicateCandidates,
  mockActivityEvents,
  getConfidenceLabel,
  getConfidenceLabelColor,
  formatEventType,
  getEventIconClass,
  type MockCandidate,
  type MockObservation,
  type DuplicateCandidate,
} from "@/lib/mock-data/recruiting";

// Format relative time
function formatRelativeTime(dateString: string): string {
  const date = new Date(dateString);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMs / 3600000);
  const diffDays = Math.floor(diffMs / 86400000);

  if (diffMins < 1) return "Just now";
  if (diffMins < 60) return `${diffMins}m ago`;
  if (diffHours < 24) return `${diffHours}h ago`;
  if (diffDays < 7) return `${diffDays}d ago`;
  return date.toLocaleDateString();
}

// Candidate card with expandable observations
function CandidateCard({
  candidate,
  observations,
  jobMatches,
  duplicates,
}: {
  candidate: MockCandidate;
  observations?: MockObservation[];
  jobMatches?: { job_id: string; job_title: string; match_score: number }[];
  duplicates?: DuplicateCandidate[];
}) {
  const [expanded, setExpanded] = useState(false);
  const initials = `${candidate.firstName[0]}${candidate.lastName[0]}`.toUpperCase();

  // Group observations by field type
  const groupedObservations = useMemo(() => {
    if (!observations) return {};
    return observations.reduce((acc, obs) => {
      const group = obs.fieldName.includes("skill")
        ? "skills"
        : obs.fieldName.includes("education")
        ? "education"
        : obs.fieldName.includes("experience") || obs.fieldName.includes("title")
        ? "experience"
        : "other";
      if (!acc[group]) acc[group] = [];
      acc[group].push(obs);
      return acc;
    }, {} as Record<string, MockObservation[]>);
  }, [observations]);

  // Get highest confidence observations for summary
  const topObservations = useMemo(() => {
    if (!observations) return [];
    return observations
      .filter((o) => o.isCurrent && o.confidence >= 0.8)
      .slice(0, 3);
  }, [observations]);

  return (
    <Card className="hover:shadow-md transition-shadow">
      <CardContent className="p-4">
        {/* Duplicate Warning Banner */}
        {duplicates && duplicates.length > 0 && (
          <div className="mb-3 p-2 bg-yellow-50 border border-yellow-200 rounded-md">
            <div className="flex items-start gap-2">
              <AlertTriangle className="h-4 w-4 text-yellow-600 mt-0.5" />
              <div className="flex-1 min-w-0">
                <p className="text-xs font-medium text-yellow-800">
                  Potential Duplicate Detected
                </p>
                <p className="text-xs text-yellow-700 mt-0.5">
                  {duplicates[0].reasons
                    .map((r) => r.detail || r.type.replace("_", " "))
                    .join(" • ")}
                </p>
                <Link
                  href={`/recruiting/merge-queue?candidate=${candidate.id}`}
                  className="text-xs text-yellow-800 font-medium hover:underline inline-flex items-center gap-1 mt-1"
                >
                  Review in Merge Queue
                  <ExternalLink className="h-3 w-3" />
                </Link>
              </div>
            </div>
          </div>
        )}

        {/* Main Card Header */}
        <div className="flex items-start gap-3">
          <Avatar className="h-12 w-12">
            <AvatarFallback className="bg-primary/10 text-primary">
              {initials}
            </AvatarFallback>
          </Avatar>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2">
              <Link href={`/recruiting/candidates/${candidate.id}`}>
                <p className="font-semibold hover:underline">
                  {candidate.firstName} {candidate.lastName}
                </p>
              </Link>
              {topObservations.length > 0 && (
                <TooltipProvider>
                  <Tooltip>
                    <TooltipTrigger>
                      <Badge
                        variant="outline"
                        className="text-xs bg-green-50 text-green-700 border-green-200"
                      >
                        <Sparkles className="h-3 w-3 mr-1" />
                        AI Enriched
                      </Badge>
                    </TooltipTrigger>
                    <TooltipContent className="max-w-xs">
                      <p className="text-sm">
                        {topObservations.length} high-confidence observations
                        extracted from documents
                      </p>
                    </TooltipContent>
                  </Tooltip>
                </TooltipProvider>
              )}
            </div>

            {/* Current Role */}
            {candidate.currentTitle && (
              <p className="text-sm text-muted-foreground">
                {candidate.currentTitle}
                {candidate.currentCompany && (
                  <span> at {candidate.currentCompany}</span>
                )}
              </p>
            )}

            {/* Contact Info */}
            <div className="flex items-center gap-3 mt-1 text-xs text-muted-foreground">
              <span className="flex items-center gap-1">
                <Mail className="h-3 w-3" />
                <span className="truncate max-w-[150px]">{candidate.email}</span>
              </span>
              {candidate.phone && (
                <span className="flex items-center gap-1">
                  <Phone className="h-3 w-3" />
                  {candidate.phone}
                </span>
              )}
            </div>
          </div>

          {/* LinkedIn + Actions */}
          <div className="flex items-center gap-2">
            {candidate.linkedinUrl && (
              <a
                href={candidate.linkedinUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="text-muted-foreground hover:text-primary"
              >
                <Linkedin className="h-4 w-4" />
              </a>
            )}
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setExpanded(!expanded)}
            >
              {expanded ? (
                <ChevronDown className="h-4 w-4" />
              ) : (
                <ChevronRight className="h-4 w-4" />
              )}
            </Button>
          </div>
        </div>

        {/* Skills Summary */}
        {candidate.topSkills.length > 0 && (
          <div className="mt-3 flex flex-wrap gap-1">
            {candidate.topSkills.slice(0, 4).map((skill) => (
              <Badge key={skill} variant="secondary" className="text-xs">
                {skill}
              </Badge>
            ))}
            {candidate.topSkills.length > 4 && (
              <Badge variant="outline" className="text-xs">
                +{candidate.topSkills.length - 4}
              </Badge>
            )}
          </div>
        )}

        {/* Job Match Score */}
        {jobMatches && jobMatches.length > 0 && (
          <div className="mt-3 flex items-center gap-2 text-xs">
            <Briefcase className="h-3 w-3 text-muted-foreground" />
            <span className="text-muted-foreground">Best Match:</span>
            <Badge
              variant="outline"
              className={
                jobMatches[0].match_score >= 0.85
                  ? "bg-green-50 text-green-700 border-green-200"
                  : jobMatches[0].match_score >= 0.7
                  ? "bg-blue-50 text-blue-700 border-blue-200"
                  : "bg-gray-50 text-gray-700 border-gray-200"
              }
            >
              {jobMatches[0].job_title} ({Math.round(jobMatches[0].match_score * 100)}%)
            </Badge>
          </div>
        )}

        {/* Footer */}
        <div className="mt-3 flex items-center justify-between text-xs text-muted-foreground">
          <span className="flex items-center gap-1">
            <Clock className="h-3 w-3" />
            Added {formatRelativeTime(candidate.createdAt)}
          </span>
          <span>Source: {candidate.source}</span>
        </div>

        {/* Expanded Observations Section */}
        {expanded && observations && observations.length > 0 && (
          <div className="mt-4 pt-4 border-t">
            <h4 className="text-sm font-medium mb-3 flex items-center gap-2">
              <Brain className="h-4 w-4 text-primary" />
              Extracted Observations
            </h4>

            <Tabs defaultValue="all" className="w-full">
              <TabsList className="grid grid-cols-4 h-8">
                <TabsTrigger value="all" className="text-xs">
                  All
                </TabsTrigger>
                <TabsTrigger value="skills" className="text-xs">
                  Skills
                </TabsTrigger>
                <TabsTrigger value="experience" className="text-xs">
                  Experience
                </TabsTrigger>
                <TabsTrigger value="education" className="text-xs">
                  Education
                </TabsTrigger>
              </TabsList>

              <TabsContent value="all" className="mt-3 space-y-2">
                {observations.slice(0, 5).map((obs) => (
                  <ObservationRow key={obs.id} observation={obs} />
                ))}
                {observations.length > 5 && (
                  <Link
                    href={`/recruiting/candidates/${candidate.id}`}
                    className="text-xs text-primary hover:underline flex items-center gap-1"
                  >
                    View all {observations.length} observations
                    <ExternalLink className="h-3 w-3" />
                  </Link>
                )}
              </TabsContent>

              <TabsContent value="skills" className="mt-3 space-y-2">
                {groupedObservations.skills?.map((obs) => (
                  <ObservationRow key={obs.id} observation={obs} />
                )) || (
                  <p className="text-xs text-muted-foreground">No skills extracted</p>
                )}
              </TabsContent>

              <TabsContent value="experience" className="mt-3 space-y-2">
                {groupedObservations.experience?.map((obs) => (
                  <ObservationRow key={obs.id} observation={obs} />
                )) || (
                  <p className="text-xs text-muted-foreground">
                    No experience extracted
                  </p>
                )}
              </TabsContent>

              <TabsContent value="education" className="mt-3 space-y-2">
                {groupedObservations.education?.map((obs) => (
                  <ObservationRow key={obs.id} observation={obs} />
                )) || (
                  <p className="text-xs text-muted-foreground">
                    No education extracted
                  </p>
                )}
              </TabsContent>
            </Tabs>
          </div>
        )}

        {expanded && (!observations || observations.length === 0) && (
          <div className="mt-4 pt-4 border-t">
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <Info className="h-4 w-4" />
              <span>No observations extracted yet. Upload a resume to extract data.</span>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

// Observation row with confidence label
function ObservationRow({ observation }: { observation: MockObservation }) {
  const confidenceColor = getConfidenceLabelColor(observation.confidenceLabel);

  return (
    <div className="flex items-start justify-between gap-2 p-2 bg-muted/50 rounded-md">
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className="text-xs font-medium text-muted-foreground capitalize">
            {observation.fieldName.replace(/_/g, " ")}:
          </span>
          <span className="text-xs text-foreground truncate">
            {observation.fieldValue}
          </span>
        </div>
        <div className="flex items-center gap-2 mt-1">
          {/* Extraction Method */}
          <Badge variant="outline" className="text-[10px] px-1 py-0">
            {observation.extractionMethod === "llm"
              ? "AI"
              : observation.extractionMethod === "external_scrape"
              ? "Enriched"
              : observation.extractionMethod}
          </Badge>

          {/* Age Indicator */}
          {observation.ageDays > 365 && (
            <TooltipProvider>
              <Tooltip>
                <TooltipTrigger>
                  <Badge
                    variant="outline"
                    className={
                      observation.relevanceScore < 0.75
                        ? "text-[10px] px-1 py-0 bg-yellow-50 text-yellow-700 border-yellow-200"
                        : "text-[10px] px-1 py-0"
                    }
                  >
                    <Clock className="h-2 w-2 mr-0.5" />
                    {Math.floor(observation.ageDays / 365)}y old
                  </Badge>
                </TooltipTrigger>
                <TooltipContent>
                  <p className="text-xs">
                    Relevance: {Math.round(observation.relevanceScore * 100)}%
                    {observation.relevanceScore < 1 && " (decayed due to age)"}
                  </p>
                </TooltipContent>
              </Tooltip>
            </TooltipProvider>
          )}

          {/* Model Provenance */}
          {observation.modelName && (
            <TooltipProvider>
              <Tooltip>
                <TooltipTrigger>
                  <span className="text-[10px] text-muted-foreground">
                    via {observation.modelName}
                  </span>
                </TooltipTrigger>
                <TooltipContent>
                  <p className="text-xs">
                    Model: {observation.modelName} {observation.modelVersion}
                    <br />
                    Prompt: {observation.promptVersion}
                  </p>
                </TooltipContent>
              </Tooltip>
            </TooltipProvider>
          )}
        </div>
      </div>

      {/* Confidence Badge */}
      <TooltipProvider>
        <Tooltip>
          <TooltipTrigger>
            <Badge variant="outline" className={`text-[10px] ${confidenceColor}`}>
              {observation.confidenceLabel}
            </Badge>
          </TooltipTrigger>
          <TooltipContent className="max-w-xs">
            <p className="text-sm">
              <strong>Confidence: {Math.round(observation.confidence * 100)}%</strong>
              <br />
              {observation.confidenceLabel === "Explicit" &&
                "High certainty - explicitly stated in source document"}
              {observation.confidenceLabel === "Very Likely" &&
                "Good confidence - clearly implied or standard format"}
              {observation.confidenceLabel === "Inferred" &&
                "Moderate confidence - inferred from context"}
              {observation.confidenceLabel === "Uncertain" &&
                "Low confidence - may need verification"}
            </p>
          </TooltipContent>
        </Tooltip>
      </TooltipProvider>
    </div>
  );
}

export default function CandidatesPage() {
  const [search, setSearch] = useState("");
  const [viewMode, setViewMode] = useState<"grid" | "list">("grid");
  const [filterSource, setFilterSource] = useState<string | null>(null);

  // Filter candidates based on search and filters
  const filteredCandidates = useMemo(() => {
    return mockCandidates.filter((candidate) => {
      // Search filter
      if (search) {
        const searchLower = search.toLowerCase();
        const matchesSearch =
          candidate.firstName.toLowerCase().includes(searchLower) ||
          candidate.lastName.toLowerCase().includes(searchLower) ||
          candidate.email.toLowerCase().includes(searchLower) ||
          candidate.currentTitle?.toLowerCase().includes(searchLower) ||
          candidate.currentCompany?.toLowerCase().includes(searchLower) ||
          candidate.topSkills.some((s) => s.toLowerCase().includes(searchLower));
        if (!matchesSearch) return false;
      }

      // Source filter
      if (filterSource && candidate.source !== filterSource) {
        return false;
      }

      return true;
    });
  }, [search, filterSource]);

  // Get unique sources for filter
  const sources = useMemo(() => {
    const uniqueSources = new Set(mockCandidates.map((c) => c.source));
    return Array.from(uniqueSources);
  }, []);

  // Stats
  const stats = useMemo(() => {
    const withObservations = mockCandidates.filter(
      (c) => mockObservations[c.id]?.length > 0
    ).length;
    const withDuplicates = mockCandidates.filter(
      (c) => mockDuplicateCandidates[c.id]?.length > 0
    ).length;
    return {
      total: mockCandidates.length,
      withObservations,
      withDuplicates,
    };
  }, []);

  return (
    <TooltipProvider>
      <div className="space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold">Candidates</h1>
            <p className="text-muted-foreground">
              Manage your candidate pool with AI-extracted observations
            </p>
          </div>
          <div className="flex items-center gap-2">
            <Button variant="outline" asChild>
              <Link href="/recruiting/merge-queue">
                <Users className="mr-2 h-4 w-4" />
                Merge Queue ({stats.withDuplicates})
              </Link>
            </Button>
            <Button asChild>
              <Link href="/recruiting/candidates/new">
                <Plus className="mr-2 h-4 w-4" />
                Add Candidate
              </Link>
            </Button>
          </div>
        </div>

        {/* Stats Cards */}
        <div className="grid gap-4 md:grid-cols-4">
          <Card>
            <CardContent className="p-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-muted-foreground">
                    Total Candidates
                  </p>
                  <p className="text-2xl font-bold">{stats.total}</p>
                </div>
                <FileText className="h-8 w-8 text-muted-foreground/50" />
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="p-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-muted-foreground">
                    AI Enriched
                  </p>
                  <p className="text-2xl font-bold">{stats.withObservations}</p>
                </div>
                <Brain className="h-8 w-8 text-green-500/50" />
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="p-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-muted-foreground">
                    Pending Review
                  </p>
                  <p className="text-2xl font-bold">{stats.withDuplicates}</p>
                </div>
                <AlertTriangle className="h-8 w-8 text-yellow-500/50" />
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="p-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-muted-foreground">
                    This Week
                  </p>
                  <p className="text-2xl font-bold">
                    {
                      mockCandidates.filter((c) => {
                        const created = new Date(c.createdAt);
                        const weekAgo = new Date();
                        weekAgo.setDate(weekAgo.getDate() - 7);
                        return created >= weekAgo;
                      }).length
                    }
                  </p>
                </div>
                <Clock className="h-8 w-8 text-blue-500/50" />
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Search and Filters */}
        <div className="flex items-center gap-4">
          <div className="relative flex-1 max-w-md">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              placeholder="Search by name, email, skills, title..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="pl-9"
            />
          </div>

          {/* Source Filter */}
          <div className="flex items-center gap-2">
            <span className="text-sm text-muted-foreground">Source:</span>
            <div className="flex gap-1">
              <Button
                variant={filterSource === null ? "default" : "outline"}
                size="sm"
                onClick={() => setFilterSource(null)}
              >
                All
              </Button>
              {sources.map((source) => (
                <Button
                  key={source}
                  variant={filterSource === source ? "default" : "outline"}
                  size="sm"
                  onClick={() => setFilterSource(source)}
                >
                  {source}
                </Button>
              ))}
            </div>
          </div>

          <Button variant="outline">
            <Filter className="mr-2 h-4 w-4" />
            More Filters
          </Button>
        </div>

        {/* Confidence Legend */}
        <Card className="bg-muted/30">
          <CardContent className="p-3">
            <div className="flex items-center gap-4 text-xs">
              <span className="font-medium text-muted-foreground">
                Confidence Labels:
              </span>
              <div className="flex items-center gap-1">
                <Badge
                  variant="outline"
                  className="bg-green-100 text-green-800 border-green-200"
                >
                  Explicit
                </Badge>
                <span className="text-muted-foreground">95%+</span>
              </div>
              <div className="flex items-center gap-1">
                <Badge
                  variant="outline"
                  className="bg-blue-100 text-blue-800 border-blue-200"
                >
                  Very Likely
                </Badge>
                <span className="text-muted-foreground">80-94%</span>
              </div>
              <div className="flex items-center gap-1">
                <Badge
                  variant="outline"
                  className="bg-yellow-100 text-yellow-800 border-yellow-200"
                >
                  Inferred
                </Badge>
                <span className="text-muted-foreground">65-79%</span>
              </div>
              <div className="flex items-center gap-1">
                <Badge
                  variant="outline"
                  className="bg-red-100 text-red-800 border-red-200"
                >
                  Uncertain
                </Badge>
                <span className="text-muted-foreground">&lt;65%</span>
              </div>
              <Tooltip>
                <TooltipTrigger>
                  <Info className="h-3 w-3 text-muted-foreground" />
                </TooltipTrigger>
                <TooltipContent className="max-w-xs">
                  <p className="text-xs">
                    Confidence labels help recruiters understand how reliable
                    AI-extracted data is. Higher confidence means the data was
                    explicitly stated in source documents.
                  </p>
                </TooltipContent>
              </Tooltip>
            </div>
          </CardContent>
        </Card>

        {/* Candidates Grid */}
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-2">
          {filteredCandidates.map((candidate) => (
            <CandidateCard
              key={candidate.id}
              candidate={candidate}
              observations={mockObservations[candidate.id]}
              jobMatches={mockJobMatches[candidate.id]}
              duplicates={mockDuplicateCandidates[candidate.id]}
            />
          ))}

          {filteredCandidates.length === 0 && (
            <Card className="col-span-full">
              <CardContent className="py-8 text-center">
                <p className="text-muted-foreground">No candidates found</p>
                {search && (
                  <p className="text-sm text-muted-foreground mt-1">
                    Try adjusting your search or filters
                  </p>
                )}
                <Button asChild className="mt-4">
                  <Link href="/recruiting/candidates/new">
                    Add your first candidate
                  </Link>
                </Button>
              </CardContent>
            </Card>
          )}
        </div>

        {/* Info Footer */}
        <Card className="bg-blue-50/50 border-blue-200">
          <CardContent className="p-4">
            <div className="flex items-start gap-3">
              <Info className="h-5 w-5 text-blue-600 mt-0.5" />
              <div>
                <h4 className="font-medium text-blue-900">
                  About Candidate Observations
                </h4>
                <p className="text-sm text-blue-800 mt-1">
                  Observations are facts extracted from resumes, LinkedIn profiles, and
                  other sources using AI. Each observation shows:
                </p>
                <ul className="text-sm text-blue-800 mt-2 space-y-1 list-disc list-inside">
                  <li>
                    <strong>Confidence Level</strong> - How certain the AI is about
                    the extracted data
                  </li>
                  <li>
                    <strong>Extraction Method</strong> - Whether it came from AI
                    parsing, manual entry, or external enrichment
                  </li>
                  <li>
                    <strong>Age & Relevance</strong> - Skills older than 3 years are
                    weighted at 75%, 5+ years at 50%
                  </li>
                  <li>
                    <strong>Model Provenance</strong> - Which AI model and prompt
                    version extracted the data (for debugging)
                  </li>
                </ul>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    </TooltipProvider>
  );
}
