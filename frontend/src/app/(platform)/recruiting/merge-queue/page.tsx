"use client";

import { useState, useMemo } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import {
  AlertTriangle,
  Check,
  X,
  ArrowRight,
  Link2,
  Mail,
  Phone,
  Building2,
  FileText,
  ChevronLeft,
  ChevronRight,
  Eye,
  ExternalLink,
  GitMerge,
  Users,
  Info,
} from "lucide-react";

import {
  mockCandidates,
  mockDuplicateCandidates,
  mockObservations,
  getConfidenceLabel,
  getConfidenceLabelColor,
  type MockCandidate,
  type DuplicateCandidate,
  type DuplicateMatchReason,
  type MockObservation,
} from "@/lib/mock-data/recruiting";

// Extended mock data for merge queue - candidates that have duplicates
interface MergeQueueItem {
  primaryCandidate: MockCandidate;
  duplicates: DuplicateCandidate[];
  status: "pending" | "merged" | "rejected" | "deferred";
  createdAt: string;
}

// Build merge queue from mock data
function buildMergeQueue(): MergeQueueItem[] {
  const queue: MergeQueueItem[] = [];

  for (const [candidateId, duplicates] of Object.entries(
    mockDuplicateCandidates
  )) {
    const primary = mockCandidates.find((c) => c.id === candidateId);
    if (primary && duplicates.length > 0) {
      queue.push({
        primaryCandidate: primary,
        duplicates: duplicates,
        status: "pending",
        createdAt: new Date(Date.now() - Math.random() * 7 * 24 * 60 * 60 * 1000).toISOString(),
      });
    }
  }

  return queue;
}

// Additional mock duplicate candidates for full demo
const additionalDuplicates: Record<string, MockCandidate> = {
  "c5-johnny-smith": {
    id: "c5-johnny-smith",
    firstName: "Johnny",
    lastName: "Smith",
    email: "johnny.s@webscale.io",
    phone: "+1-555-234-5679",
    linkedinUrl: "https://linkedin.com/in/johnnysmith",
    topSkills: ["React", "TypeScript", "Node.js", "AWS"],
    source: "Indeed",
    currentTitle: "Senior Frontend Developer",
    currentCompany: "WebScale Inc",
    yearsExperience: 9,
    createdAt: "2024-05-10T08:00:00Z",
    updatedAt: "2025-12-11T10:00:00Z",
  },
  "c6-jane-m-doe": {
    id: "c6-jane-m-doe",
    firstName: "Jane",
    lastName: "M. Doe",
    email: "jane.doe@email.com",
    phone: "+1-555-123-4567",
    linkedinUrl: "https://linkedin.com/in/janemdoe",
    topSkills: ["Python", "Machine Learning", "AWS", "SQL"],
    source: "Direct Apply",
    currentTitle: "ML Engineer",
    currentCompany: "AI Startup",
    yearsExperience: 6,
    createdAt: "2024-02-01T10:00:00Z",
    updatedAt: "2025-11-15T14:00:00Z",
  },
  "c7-janet-doe": {
    id: "c7-janet-doe",
    firstName: "Janet",
    lastName: "Doe",
    email: "janet.doe@different.com",
    phone: "+1-555-123-4567",
    linkedinUrl: "",
    topSkills: ["Python", "Data Analysis", "SQL"],
    source: "Referral",
    currentTitle: "Data Analyst",
    currentCompany: "Analytics Co",
    yearsExperience: 4,
    createdAt: "2024-08-15T09:00:00Z",
    updatedAt: "2025-12-05T11:00:00Z",
  },
};

// Match type badge colors
function getMatchTypeBadge(
  matchType: DuplicateCandidate["match_type"]
): { color: string; label: string; description: string } {
  switch (matchType) {
    case "hard":
      return {
        color: "bg-red-100 text-red-800 border-red-200",
        label: "Hard Match",
        description: "Definite duplicate - same email/LinkedIn (auto-merge recommended)",
      };
    case "strong":
      return {
        color: "bg-orange-100 text-orange-800 border-orange-200",
        label: "Strong Match",
        description: "95%+ confidence - very likely same person",
      };
    case "fuzzy":
      return {
        color: "bg-yellow-100 text-yellow-800 border-yellow-200",
        label: "Fuzzy Match",
        description: "80-95% confidence - similar profiles",
      };
    case "review":
      return {
        color: "bg-blue-100 text-blue-800 border-blue-200",
        label: "Needs Review",
        description: "60-80% confidence - human review required",
      };
  }
}

// Reason type icons and labels
function getReasonLabel(reasonType: DuplicateMatchReason): {
  icon: React.ReactNode;
  label: string;
} {
  switch (reasonType) {
    case "email_match":
      return { icon: <Mail className="h-4 w-4" />, label: "Same Email" };
    case "linkedin_match":
      return { icon: <Link2 className="h-4 w-4" />, label: "Same LinkedIn" };
    case "name_similarity":
      return { icon: <Users className="h-4 w-4" />, label: "Similar Name" };
    case "resume_similarity":
      return { icon: <FileText className="h-4 w-4" />, label: "Similar Resume" };
    case "company_overlap":
      return { icon: <Building2 className="h-4 w-4" />, label: "Company Overlap" };
    case "phone_match":
      return { icon: <Phone className="h-4 w-4" />, label: "Same Phone" };
  }
}

// Candidate comparison card
function CandidateComparisonCard({
  candidate,
  isPrimary,
  observations,
}: {
  candidate: MockCandidate;
  isPrimary: boolean;
  observations?: MockObservation[];
}) {
  return (
    <Card className={isPrimary ? "border-green-300 bg-green-50/30" : "border-gray-200"}>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <div>
            <CardTitle className="text-lg">
              {candidate.firstName} {candidate.lastName}
            </CardTitle>
            <CardDescription>
              {candidate.currentTitle} at {candidate.currentCompany}
            </CardDescription>
          </div>
          {isPrimary && (
            <Badge variant="outline" className="bg-green-100 text-green-800 border-green-300">
              Primary
            </Badge>
          )}
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Contact Info */}
        <div className="grid grid-cols-1 gap-2 text-sm">
          <div className="flex items-center gap-2">
            <Mail className="h-4 w-4 text-gray-400" />
            <span className="font-mono text-xs">{candidate.email}</span>
          </div>
          <div className="flex items-center gap-2">
            <Phone className="h-4 w-4 text-gray-400" />
            <span className="font-mono text-xs">{candidate.phone}</span>
          </div>
          {candidate.linkedinUrl && (
            <div className="flex items-center gap-2">
              <Link2 className="h-4 w-4 text-gray-400" />
              <a
                href={candidate.linkedinUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="text-blue-600 hover:underline text-xs truncate"
              >
                {candidate.linkedinUrl.replace("https://linkedin.com/in/", "")}
              </a>
            </div>
          )}
        </div>

        {/* Skills */}
        <div>
          <div className="text-xs font-medium text-gray-500 mb-2">Top Skills</div>
          <div className="flex flex-wrap gap-1">
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
        </div>

        {/* Metadata */}
        <div className="flex items-center justify-between text-xs text-gray-500 pt-2 border-t">
          <span>Source: {candidate.source}</span>
          <span>{candidate.yearsExperience} yrs exp</span>
        </div>

        {/* Observations count if available */}
        {observations && observations.length > 0 && (
          <div className="text-xs text-gray-500">
            {observations.length} observations on file
          </div>
        )}

        {/* View profile link */}
        <Link href={`/recruiting/candidates/${candidate.id}`}>
          <Button variant="outline" size="sm" className="w-full">
            <Eye className="h-4 w-4 mr-2" />
            View Full Profile
          </Button>
        </Link>
      </CardContent>
    </Card>
  );
}

// Duplicate pair review component
function DuplicatePairReview({
  item,
  duplicate,
  duplicateCandidate,
  onMerge,
  onReject,
  onDefer,
}: {
  item: MergeQueueItem;
  duplicate: DuplicateCandidate;
  duplicateCandidate: MockCandidate | undefined;
  onMerge: () => void;
  onReject: () => void;
  onDefer: () => void;
}) {
  const matchBadge = getMatchTypeBadge(duplicate.match_type);

  if (!duplicateCandidate) {
    return (
      <Card className="border-dashed">
        <CardContent className="p-4 text-center text-gray-500">
          Duplicate candidate not found: {duplicate.candidate_id}
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-4">
      {/* Match header with reasons */}
      <Card className="bg-gray-50">
        <CardContent className="p-4">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <TooltipProvider>
                <Tooltip>
                  <TooltipTrigger>
                    <Badge className={matchBadge.color}>
                      {matchBadge.label}
                    </Badge>
                  </TooltipTrigger>
                  <TooltipContent>
                    <p className="max-w-xs">{matchBadge.description}</p>
                  </TooltipContent>
                </Tooltip>
              </TooltipProvider>
              <span className="text-sm text-gray-600">
                {Math.round(duplicate.match_score * 100)}% confidence
              </span>
            </div>
            <div className="flex items-center gap-1 text-xs text-gray-500">
              <Info className="h-3 w-3" />
              Always shows WHY
            </div>
          </div>

          {/* Match reasons with explicit WHY */}
          <div className="space-y-2">
            <div className="text-xs font-medium text-gray-700 mb-2">
              Why we think they&apos;re the same person:
            </div>
            {duplicate.reasons.map((reason, idx) => {
              const reasonInfo = getReasonLabel(reason.type);
              const confidenceLabel = getConfidenceLabel(reason.confidence);
              const confidenceColor = getConfidenceLabelColor(confidenceLabel);

              return (
                <div
                  key={idx}
                  className="flex items-start gap-2 p-2 bg-white rounded border"
                >
                  <div className="flex-shrink-0 mt-0.5">{reasonInfo.icon}</div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="font-medium text-sm">{reasonInfo.label}</span>
                      <Badge variant="outline" className={`text-xs ${confidenceColor}`}>
                        {Math.round(reason.confidence * 100)}%
                      </Badge>
                    </div>
                    {reason.detail && (
                      <p className="text-xs text-gray-600 mt-0.5 font-mono">
                        {reason.detail}
                      </p>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </CardContent>
      </Card>

      {/* Side by side comparison */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <CandidateComparisonCard
          candidate={item.primaryCandidate}
          isPrimary={true}
          observations={mockObservations[item.primaryCandidate.id]}
        />

        <div className="flex items-center justify-center">
          <div className="flex flex-col items-center gap-2">
            <GitMerge className="h-8 w-8 text-gray-400" />
            <ArrowRight className="h-6 w-6 text-gray-400 hidden lg:block" />
            <span className="text-xs text-gray-500">Merge?</span>
          </div>
        </div>

        <CandidateComparisonCard
          candidate={duplicateCandidate}
          isPrimary={false}
        />
      </div>

      {/* Action buttons */}
      <div className="flex items-center justify-center gap-3">
        <TooltipProvider>
          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                variant="default"
                className="bg-green-600 hover:bg-green-700"
                onClick={onMerge}
              >
                <Check className="h-4 w-4 mr-2" />
                Merge into Primary
              </Button>
            </TooltipTrigger>
            <TooltipContent>
              <p>Merge {duplicateCandidate.firstName}&apos;s data into {item.primaryCandidate.firstName}&apos;s profile</p>
            </TooltipContent>
          </Tooltip>
        </TooltipProvider>

        <TooltipProvider>
          <Tooltip>
            <TooltipTrigger asChild>
              <Button variant="outline" onClick={onDefer}>
                <ChevronRight className="h-4 w-4 mr-2" />
                Skip for Now
              </Button>
            </TooltipTrigger>
            <TooltipContent>
              <p>Move to end of queue, review later</p>
            </TooltipContent>
          </Tooltip>
        </TooltipProvider>

        <TooltipProvider>
          <Tooltip>
            <TooltipTrigger asChild>
              <Button variant="destructive" onClick={onReject}>
                <X className="h-4 w-4 mr-2" />
                Not a Duplicate
              </Button>
            </TooltipTrigger>
            <TooltipContent>
              <p>These are different people, don&apos;t merge</p>
            </TooltipContent>
          </Tooltip>
        </TooltipProvider>
      </div>
    </div>
  );
}

export default function MergeQueuePage() {
  const searchParams = useSearchParams();
  const focusCandidateId = searchParams.get("candidate");

  const [mergeQueue, setMergeQueue] = useState<MergeQueueItem[]>(buildMergeQueue);
  const [currentIndex, setCurrentIndex] = useState(() => {
    // If a candidate ID was passed, find their index
    if (focusCandidateId) {
      const idx = mergeQueue.findIndex(
        (item) => item.primaryCandidate.id === focusCandidateId
      );
      return idx >= 0 ? idx : 0;
    }
    return 0;
  });
  const [filter, setFilter] = useState<"all" | "hard" | "strong" | "fuzzy" | "review">(
    "all"
  );

  // Filter queue based on match type
  const filteredQueue = useMemo(() => {
    if (filter === "all") return mergeQueue.filter((item) => item.status === "pending");
    return mergeQueue.filter(
      (item) =>
        item.status === "pending" &&
        item.duplicates.some((d) => d.match_type === filter)
    );
  }, [mergeQueue, filter]);

  // Stats
  const stats = useMemo(() => {
    const pending = mergeQueue.filter((item) => item.status === "pending");
    return {
      total: pending.length,
      hard: pending.filter((item) =>
        item.duplicates.some((d) => d.match_type === "hard")
      ).length,
      strong: pending.filter((item) =>
        item.duplicates.some((d) => d.match_type === "strong")
      ).length,
      fuzzy: pending.filter((item) =>
        item.duplicates.some((d) => d.match_type === "fuzzy")
      ).length,
      review: pending.filter((item) =>
        item.duplicates.some((d) => d.match_type === "review")
      ).length,
    };
  }, [mergeQueue]);

  const currentItem = filteredQueue[currentIndex];
  const currentDuplicate = currentItem?.duplicates[0];

  const handleMerge = () => {
    if (!currentItem) return;
    setMergeQueue((prev) =>
      prev.map((item) =>
        item.primaryCandidate.id === currentItem.primaryCandidate.id
          ? { ...item, status: "merged" as const }
          : item
      )
    );
    // Move to next if available
    if (currentIndex >= filteredQueue.length - 1) {
      setCurrentIndex(Math.max(0, currentIndex - 1));
    }
  };

  const handleReject = () => {
    if (!currentItem) return;
    setMergeQueue((prev) =>
      prev.map((item) =>
        item.primaryCandidate.id === currentItem.primaryCandidate.id
          ? { ...item, status: "rejected" as const }
          : item
      )
    );
    if (currentIndex >= filteredQueue.length - 1) {
      setCurrentIndex(Math.max(0, currentIndex - 1));
    }
  };

  const handleDefer = () => {
    if (!currentItem) return;
    // Move to end of queue
    setMergeQueue((prev) => {
      const item = prev.find(
        (i) => i.primaryCandidate.id === currentItem.primaryCandidate.id
      );
      if (!item) return prev;
      const newQueue = prev.filter(
        (i) => i.primaryCandidate.id !== currentItem.primaryCandidate.id
      );
      return [...newQueue, { ...item, status: "deferred" as const }];
    });
  };

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <div className="flex items-center gap-2">
            <Link
              href="/recruiting/candidates"
              className="text-gray-500 hover:text-gray-700"
            >
              <ChevronLeft className="h-5 w-5" />
            </Link>
            <h1 className="text-2xl font-bold">Merge Review Queue</h1>
          </div>
          <p className="text-gray-600 mt-1">
            Review potential duplicate candidates and decide whether to merge
          </p>
        </div>

        <div className="flex items-center gap-2">
          {filteredQueue.length > 0 && (
            <span className="text-sm text-gray-500">
              {currentIndex + 1} of {filteredQueue.length}
            </span>
          )}
        </div>
      </div>

      {/* Stats cards */}
      <div className="grid grid-cols-5 gap-4">
        <Card
          className={`cursor-pointer transition ${
            filter === "all" ? "ring-2 ring-blue-500" : ""
          }`}
          onClick={() => setFilter("all")}
        >
          <CardContent className="p-4">
            <div className="text-2xl font-bold">{stats.total}</div>
            <div className="text-sm text-gray-500">Total Pending</div>
          </CardContent>
        </Card>
        <Card
          className={`cursor-pointer transition ${
            filter === "hard" ? "ring-2 ring-red-500" : ""
          }`}
          onClick={() => setFilter("hard")}
        >
          <CardContent className="p-4">
            <div className="text-2xl font-bold text-red-600">{stats.hard}</div>
            <div className="text-sm text-gray-500">Hard Matches</div>
          </CardContent>
        </Card>
        <Card
          className={`cursor-pointer transition ${
            filter === "strong" ? "ring-2 ring-orange-500" : ""
          }`}
          onClick={() => setFilter("strong")}
        >
          <CardContent className="p-4">
            <div className="text-2xl font-bold text-orange-600">{stats.strong}</div>
            <div className="text-sm text-gray-500">Strong Matches</div>
          </CardContent>
        </Card>
        <Card
          className={`cursor-pointer transition ${
            filter === "fuzzy" ? "ring-2 ring-yellow-500" : ""
          }`}
          onClick={() => setFilter("fuzzy")}
        >
          <CardContent className="p-4">
            <div className="text-2xl font-bold text-yellow-600">{stats.fuzzy}</div>
            <div className="text-sm text-gray-500">Fuzzy Matches</div>
          </CardContent>
        </Card>
        <Card
          className={`cursor-pointer transition ${
            filter === "review" ? "ring-2 ring-blue-500" : ""
          }`}
          onClick={() => setFilter("review")}
        >
          <CardContent className="p-4">
            <div className="text-2xl font-bold text-blue-600">{stats.review}</div>
            <div className="text-sm text-gray-500">Needs Review</div>
          </CardContent>
        </Card>
      </div>

      {/* Navigation */}
      {filteredQueue.length > 1 && (
        <div className="flex items-center justify-center gap-2">
          <Button
            variant="outline"
            size="sm"
            disabled={currentIndex === 0}
            onClick={() => setCurrentIndex((prev) => prev - 1)}
          >
            <ChevronLeft className="h-4 w-4" />
            Previous
          </Button>
          <span className="text-sm text-gray-500 mx-4">
            Reviewing: {currentItem?.primaryCandidate.firstName}{" "}
            {currentItem?.primaryCandidate.lastName}
          </span>
          <Button
            variant="outline"
            size="sm"
            disabled={currentIndex >= filteredQueue.length - 1}
            onClick={() => setCurrentIndex((prev) => prev + 1)}
          >
            Next
            <ChevronRight className="h-4 w-4" />
          </Button>
        </div>
      )}

      {/* Current review */}
      {filteredQueue.length === 0 ? (
        <Card>
          <CardContent className="p-12 text-center">
            <Check className="h-12 w-12 mx-auto text-green-500 mb-4" />
            <h3 className="text-lg font-medium">Queue is empty!</h3>
            <p className="text-gray-500 mt-2">
              No pending duplicates to review. New potential duplicates will appear here
              as candidates are added.
            </p>
            <Link href="/recruiting/candidates">
              <Button variant="outline" className="mt-4">
                <ChevronLeft className="h-4 w-4 mr-2" />
                Back to Candidates
              </Button>
            </Link>
          </CardContent>
        </Card>
      ) : currentItem && currentDuplicate ? (
        <DuplicatePairReview
          item={currentItem}
          duplicate={currentDuplicate}
          duplicateCandidate={
            additionalDuplicates[currentDuplicate.candidate_id] ||
            mockCandidates.find((c) => c.id === currentDuplicate.candidate_id)
          }
          onMerge={handleMerge}
          onReject={handleReject}
          onDefer={handleDefer}
        />
      ) : null}

      {/* Legend */}
      <Card className="bg-gray-50">
        <CardHeader className="pb-2">
          <CardTitle className="text-sm">Match Types Explained</CardTitle>
        </CardHeader>
        <CardContent className="grid grid-cols-2 lg:grid-cols-4 gap-4 text-sm">
          <div className="flex items-start gap-2">
            <Badge className="bg-red-100 text-red-800 border-red-200">Hard</Badge>
            <span className="text-gray-600">
              Same email/LinkedIn - auto-merge recommended
            </span>
          </div>
          <div className="flex items-start gap-2">
            <Badge className="bg-orange-100 text-orange-800 border-orange-200">
              Strong
            </Badge>
            <span className="text-gray-600">
              95%+ confidence - very likely same person
            </span>
          </div>
          <div className="flex items-start gap-2">
            <Badge className="bg-yellow-100 text-yellow-800 border-yellow-200">
              Fuzzy
            </Badge>
            <span className="text-gray-600">80-95% - similar profiles</span>
          </div>
          <div className="flex items-start gap-2">
            <Badge className="bg-blue-100 text-blue-800 border-blue-200">Review</Badge>
            <span className="text-gray-600">60-80% - human judgment required</span>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
