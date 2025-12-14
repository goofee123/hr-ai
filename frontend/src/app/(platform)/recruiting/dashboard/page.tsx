"use client";

import { useState } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Progress } from "@/components/ui/progress";
import {
  mockCandidates,
  mockJobs,
  mockAlerts,
  mockActivityEvents,
  mockJobMatches,
  mockMatchingConfig,
  getConfidenceLabel,
  getConfidenceLabelColor,
  type MockAlert,
  type MockCandidate,
  type MockJob,
} from "@/lib/mock-data/recruiting";
import Link from "next/link";

// Alert type icons and colors
const alertConfig: Record<string, { icon: string; color: string; bgColor: string }> = {
  new_match: { icon: "🎯", color: "text-green-600", bgColor: "bg-green-50 border-green-200" },
  sla_warning: { icon: "⚠️", color: "text-amber-600", bgColor: "bg-amber-50 border-amber-200" },
  duplicate_detected: { icon: "👥", color: "text-blue-600", bgColor: "bg-blue-50 border-blue-200" },
  dayforce_sync: { icon: "🔄", color: "text-purple-600", bgColor: "bg-purple-50 border-purple-200" },
  high_match: { icon: "⭐", color: "text-yellow-600", bgColor: "bg-yellow-50 border-yellow-200" },
  candidate_activity: { icon: "📝", color: "text-gray-600", bgColor: "bg-gray-50 border-gray-200" },
};

// Simulated two-way matching results
interface MatchResult {
  type: "candidate_to_jobs" | "job_to_candidates";
  sourceId: string;
  sourceName: string;
  matches: Array<{
    id: string;
    name: string;
    score: number;
    topReasons: string[];
  }>;
  timestamp: string;
}

const recentMatchResults: MatchResult[] = [
  {
    type: "candidate_to_jobs",
    sourceId: "c1",
    sourceName: "Sarah Chen",
    matches: [
      { id: "j1", name: "Senior Software Engineer", score: 94, topReasons: ["Python match", "ML experience", "5+ years"] },
      { id: "j4", name: "Tech Lead", score: 78, topReasons: ["Technical skills", "Leadership potential"] },
    ],
    timestamp: "2024-01-15T10:30:00Z",
  },
  {
    type: "job_to_candidates",
    sourceId: "j2",
    sourceName: "Product Manager",
    matches: [
      { id: "c3", name: "Emily Rodriguez", score: 91, topReasons: ["PM experience", "Tech background", "Agile certified"] },
      { id: "c1", name: "Sarah Chen", score: 72, topReasons: ["Technical skills", "Project leadership"] },
    ],
    timestamp: "2024-01-15T09:15:00Z",
  },
  {
    type: "candidate_to_jobs",
    sourceId: "c2",
    sourceName: "Michael Thompson",
    matches: [
      { id: "j3", name: "DevOps Engineer", score: 88, topReasons: ["AWS certified", "Kubernetes", "CI/CD"] },
      { id: "j1", name: "Senior Software Engineer", score: 75, topReasons: ["Backend experience", "Python"] },
    ],
    timestamp: "2024-01-14T16:45:00Z",
  },
];

// Alert Card Component
function AlertCard({ alert, onDismiss }: { alert: MockAlert; onDismiss: (id: string) => void }) {
  const config = alertConfig[alert.type] || alertConfig.candidate_activity;

  return (
    <div className={`p-4 rounded-lg border ${config.bgColor} transition-all hover:shadow-md`}>
      <div className="flex items-start justify-between">
        <div className="flex items-start gap-3">
          <span className="text-2xl">{config.icon}</span>
          <div>
            <h4 className={`font-medium ${config.color}`}>{alert.title}</h4>
            <p className="text-sm text-gray-600 mt-1">{alert.message}</p>
            <p className="text-xs text-gray-400 mt-2">
              {new Date(alert.timestamp).toLocaleString()}
            </p>
          </div>
        </div>
        <div className="flex gap-2">
          {alert.actionUrl && (
            <Link href={alert.actionUrl}>
              <Button size="sm" variant="outline">View</Button>
            </Link>
          )}
          <Button size="sm" variant="ghost" onClick={() => onDismiss(alert.id)}>
            Dismiss
          </Button>
        </div>
      </div>
    </div>
  );
}

// Match Result Card
function MatchResultCard({ result }: { result: MatchResult }) {
  const isCandiateToJobs = result.type === "candidate_to_jobs";

  return (
    <Card className="mb-4">
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Badge variant={isCandiateToJobs ? "default" : "secondary"}>
              {isCandiateToJobs ? "New Candidate" : "New Opening"}
            </Badge>
            <span className="font-medium">{result.sourceName}</span>
          </div>
          <span className="text-xs text-gray-500">
            {new Date(result.timestamp).toLocaleString()}
          </span>
        </div>
        <CardDescription>
          {isCandiateToJobs
            ? "Matched against open positions"
            : "Matched against candidate pool"}
        </CardDescription>
      </CardHeader>
      <CardContent>
        <div className="space-y-3">
          {result.matches.map((match) => (
            <div
              key={match.id}
              className="flex items-center justify-between p-3 bg-gray-50 rounded-lg"
            >
              <div className="flex-1">
                <div className="flex items-center gap-2">
                  <span className="font-medium">{match.name}</span>
                  <Badge
                    variant={match.score >= 85 ? "default" : "secondary"}
                    className={match.score >= 85 ? "bg-green-600" : ""}
                  >
                    {match.score}% match
                  </Badge>
                </div>
                <div className="flex flex-wrap gap-1 mt-1">
                  {match.topReasons.map((reason, i) => (
                    <span key={i} className="text-xs text-gray-500 bg-gray-200 px-2 py-0.5 rounded">
                      {reason}
                    </span>
                  ))}
                </div>
              </div>
              <Button size="sm" variant="outline">
                View Details
              </Button>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}

// Stats Card
function StatsCard({ title, value, subtitle, trend }: { title: string; value: string | number; subtitle: string; trend?: { value: number; isPositive: boolean } }) {
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardDescription>{title}</CardDescription>
      </CardHeader>
      <CardContent>
        <div className="flex items-baseline justify-between">
          <span className="text-3xl font-bold">{value}</span>
          {trend && (
            <span className={`text-sm ${trend.isPositive ? "text-green-600" : "text-red-600"}`}>
              {trend.isPositive ? "↑" : "↓"} {Math.abs(trend.value)}%
            </span>
          )}
        </div>
        <p className="text-sm text-gray-500 mt-1">{subtitle}</p>
      </CardContent>
    </Card>
  );
}

// Job Card with Match Count
function JobCard({ job }: { job: MockJob }) {
  const matchCount = mockJobMatches.filter((m) => m.jobId === job.id).length;
  const topMatch = mockJobMatches.find((m) => m.jobId === job.id);

  return (
    <div className="p-4 border rounded-lg hover:shadow-md transition-all">
      <div className="flex items-start justify-between">
        <div>
          <h4 className="font-medium">{job.title}</h4>
          <p className="text-sm text-gray-500">{job.department} • {job.location}</p>
        </div>
        <Badge
          variant={job.status === "open" ? "default" : "secondary"}
          className={job.status === "open" ? "bg-green-600" : ""}
        >
          {job.status}
        </Badge>
      </div>
      <div className="mt-3 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium">{matchCount} matches</span>
          {topMatch && (
            <span className="text-xs text-gray-500">
              (top: {topMatch.overallScore}%)
            </span>
          )}
        </div>
        <div className="flex items-center gap-2 text-xs text-gray-500">
          <span>{job.applicantCount} applicants</span>
          <span>•</span>
          <span>SLA: {job.slaDaysRemaining}d left</span>
        </div>
      </div>
      <div className="mt-2">
        <Progress value={(30 - job.slaDaysRemaining) / 30 * 100} className="h-1" />
      </div>
    </div>
  );
}

// Candidate Quick View
function CandidateQuickView({ candidate }: { candidate: MockCandidate }) {
  const match = mockJobMatches.find((m) => m.candidateId === candidate.id);

  return (
    <div className="p-4 border rounded-lg hover:shadow-md transition-all">
      <div className="flex items-start gap-3">
        <Avatar>
          <AvatarFallback>
            {candidate.firstName[0]}{candidate.lastName[0]}
          </AvatarFallback>
        </Avatar>
        <div className="flex-1">
          <div className="flex items-center justify-between">
            <h4 className="font-medium">{candidate.firstName} {candidate.lastName}</h4>
            {match && (
              <Badge className="bg-green-600">{match.overallScore}% match</Badge>
            )}
          </div>
          <p className="text-sm text-gray-500">{candidate.currentTitle}</p>
          <p className="text-xs text-gray-400">{candidate.currentCompany}</p>
          <div className="flex flex-wrap gap-1 mt-2">
            {candidate.topSkills.slice(0, 3).map((skill, i) => (
              <Badge key={i} variant="outline" className="text-xs">
                {skill}
              </Badge>
            ))}
          </div>
        </div>
      </div>
      <div className="mt-3 flex justify-between items-center">
        <span className="text-xs text-gray-500">
          Added {new Date(candidate.createdAt).toLocaleDateString()}
        </span>
        <Link href={`/recruiting/candidates/${candidate.id}`}>
          <Button size="sm" variant="outline">View Profile</Button>
        </Link>
      </div>
    </div>
  );
}

// Recent Activity Item
function ActivityItem({ event }: { event: typeof mockActivityEvents[0] }) {
  const eventIcons: Record<string, string> = {
    profile_viewed: "👁️",
    resume_uploaded: "📄",
    stage_changed: "➡️",
    note_added: "📝",
    interview_scheduled: "📅",
    email_sent: "✉️",
  };

  return (
    <div className="flex items-start gap-3 py-3 border-b last:border-0">
      <span className="text-lg">{eventIcons[event.eventType] || "📌"}</span>
      <div className="flex-1">
        <p className="text-sm">
          <span className="font-medium">{event.eventType.replace(/_/g, " ")}</span>
        </p>
        {event.eventData && (
          <p className="text-xs text-gray-500 mt-0.5">
            {JSON.stringify(event.eventData).slice(0, 60)}...
          </p>
        )}
        <p className="text-xs text-gray-400 mt-1">
          {new Date(event.createdAt).toLocaleString()}
        </p>
      </div>
    </div>
  );
}

export default function RecruiterDashboardPage() {
  const [alerts, setAlerts] = useState(mockAlerts);
  const [activeTab, setActiveTab] = useState("overview");

  const dismissAlert = (id: string) => {
    setAlerts((prev) => prev.filter((a) => a.id !== id));
  };

  const openJobs = mockJobs.filter((j) => j.status === "open");
  const urgentAlerts = alerts.filter((a) => a.priority === "high");
  const recentCandidates = [...mockCandidates].sort(
    (a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime()
  );

  return (
    <div className="container mx-auto py-6 px-4">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-3xl font-bold">Recruiter Dashboard</h1>
          <p className="text-gray-500">
            Welcome back! Here&apos;s what&apos;s happening with your talent pipeline.
          </p>
        </div>
        <div className="flex gap-2">
          <Link href="/recruiting/candidates/new">
            <Button variant="outline">Add Candidate</Button>
          </Link>
          <Link href="/recruiting/jobs/new">
            <Button>Post New Job</Button>
          </Link>
        </div>
      </div>

      {/* Urgent Alerts Banner */}
      {urgentAlerts.length > 0 && (
        <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-lg">
          <div className="flex items-center gap-2 mb-2">
            <span className="text-xl">🚨</span>
            <h3 className="font-semibold text-red-800">
              {urgentAlerts.length} Urgent Alert{urgentAlerts.length > 1 ? "s" : ""}
            </h3>
          </div>
          <div className="space-y-2">
            {urgentAlerts.map((alert) => (
              <div key={alert.id} className="flex items-center justify-between">
                <span className="text-sm text-red-700">{alert.message}</span>
                <Button size="sm" variant="outline" className="text-red-700 border-red-300">
                  Take Action
                </Button>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Stats Overview */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        <StatsCard
          title="Open Positions"
          value={openJobs.length}
          subtitle="Active job requisitions"
          trend={{ value: 12, isPositive: true }}
        />
        <StatsCard
          title="Candidate Pool"
          value={mockCandidates.length}
          subtitle="Total candidates"
          trend={{ value: 8, isPositive: true }}
        />
        <StatsCard
          title="Pending Matches"
          value={mockJobMatches.length}
          subtitle="High-score matches to review"
        />
        <StatsCard
          title="Avg. Time to Fill"
          value="24d"
          subtitle="Last 30 days"
          trend={{ value: 3, isPositive: false }}
        />
      </div>

      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList className="mb-4">
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="matches">Two-Way Matching</TabsTrigger>
          <TabsTrigger value="alerts">
            Alerts
            {alerts.length > 0 && (
              <Badge variant="destructive" className="ml-2">
                {alerts.length}
              </Badge>
            )}
          </TabsTrigger>
          <TabsTrigger value="activity">Recent Activity</TabsTrigger>
        </TabsList>

        <TabsContent value="overview">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Open Jobs */}
            <Card>
              <CardHeader>
                <CardTitle>Open Positions</CardTitle>
                <CardDescription>
                  Jobs actively seeking candidates
                </CardDescription>
              </CardHeader>
              <CardContent>
                <ScrollArea className="h-[400px]">
                  <div className="space-y-3">
                    {openJobs.map((job) => (
                      <JobCard key={job.id} job={job} />
                    ))}
                  </div>
                </ScrollArea>
              </CardContent>
            </Card>

            {/* Recent Candidates */}
            <Card>
              <CardHeader>
                <CardTitle>Recent Candidates</CardTitle>
                <CardDescription>
                  Latest additions to your talent pool
                </CardDescription>
              </CardHeader>
              <CardContent>
                <ScrollArea className="h-[400px]">
                  <div className="space-y-3">
                    {recentCandidates.map((candidate) => (
                      <CandidateQuickView key={candidate.id} candidate={candidate} />
                    ))}
                  </div>
                </ScrollArea>
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        <TabsContent value="matches">
          <div className="mb-4 p-4 bg-blue-50 border border-blue-200 rounded-lg">
            <h3 className="font-semibold text-blue-800 flex items-center gap-2">
              <span>🔄</span> Two-Way Matching Engine
            </h3>
            <p className="text-sm text-blue-700 mt-1">
              Automatically matches new candidates against open positions AND new job openings against your existing candidate pool.
            </p>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Candidate → Jobs */}
            <div>
              <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
                <span>👤→📋</span> New Candidates Matched to Jobs
              </h3>
              {recentMatchResults
                .filter((r) => r.type === "candidate_to_jobs")
                .map((result, i) => (
                  <MatchResultCard key={i} result={result} />
                ))}
            </div>

            {/* Jobs → Candidates */}
            <div>
              <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
                <span>📋→👥</span> New Jobs Matched to Pool
              </h3>
              {recentMatchResults
                .filter((r) => r.type === "job_to_candidates")
                .map((result, i) => (
                  <MatchResultCard key={i} result={result} />
                ))}
            </div>
          </div>

          {/* Matching Configuration (Read-Only) */}
          <Card className="mt-6">
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle className="flex items-center gap-2">
                    Matching Configuration
                    <Badge variant="outline" className="border-gray-400 text-gray-500 font-normal">
                      Read Only
                    </Badge>
                  </CardTitle>
                  <CardDescription>
                    Current tenant-level matching weights (admin-configurable only)
                  </CardDescription>
                </div>
                <div className="flex items-center gap-2 text-xs text-gray-500">
                  <span>Model: {mockMatchingConfig.modelName}</span>
                  <span>•</span>
                  <span>v{mockMatchingConfig.modelVersion}</span>
                  <span>•</span>
                  <span>Updated: {new Date(mockMatchingConfig.lastUpdated).toLocaleDateString()}</span>
                </div>
              </div>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                {mockMatchingConfig.weights.map((weight) => (
                  <div key={weight.factor} className="p-4 bg-gray-50 rounded-lg border border-gray-100">
                    <div className="flex items-center justify-between mb-2">
                      <h4 className="font-medium capitalize">{weight.factor.replace("_", " ")} Weight</h4>
                      <span className="text-xs text-gray-400">locked</span>
                    </div>
                    <Progress value={weight.weight * 100} className="h-2 mb-1" />
                    <div className="flex items-center justify-between">
                      <span className="text-sm font-medium text-gray-700">{Math.round(weight.weight * 100)}%</span>
                      <span className="text-xs text-gray-500">{weight.description}</span>
                    </div>
                  </div>
                ))}
              </div>

              {/* Relevance Decay Info */}
              <div className="mt-4 p-4 bg-blue-50 border border-blue-200 rounded-lg">
                <div className="flex items-center justify-between mb-2">
                  <h4 className="font-medium text-blue-800">Relevance Decay Policy</h4>
                  <Badge variant="outline" className="border-blue-300 text-blue-600 text-xs">
                    Active
                  </Badge>
                </div>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mt-3">
                  {mockMatchingConfig.relevanceDecay.map((decay) => (
                    <div key={decay.ageRange} className="text-center p-2 bg-white/50 rounded">
                      <p className="text-xs text-blue-600 font-medium">{decay.ageRange}</p>
                      <p className="text-lg font-bold text-blue-800">{Math.round(decay.factor * 100)}%</p>
                    </div>
                  ))}
                </div>
                <p className="text-sm text-blue-700 mt-3">
                  Skills and certifications are weighted based on their age. Contact admin to adjust thresholds.
                </p>
              </div>

              {/* Admin Notice */}
              <div className="mt-4 p-3 bg-gray-100 border border-gray-200 rounded-lg flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="text-gray-500">🔒</span>
                  <span className="text-sm text-gray-600">
                    These weights are tenant-level defaults. Contact your administrator to request changes.
                  </span>
                </div>
                <Link href="/admin/matching-config">
                  <Button variant="ghost" size="sm" className="text-gray-500">
                    Admin Settings
                  </Button>
                </Link>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="alerts">
          <div className="space-y-4">
            {alerts.length === 0 ? (
              <Card>
                <CardContent className="py-12 text-center">
                  <span className="text-4xl">✅</span>
                  <h3 className="text-lg font-medium mt-4">All caught up!</h3>
                  <p className="text-gray-500">No pending alerts at this time.</p>
                </CardContent>
              </Card>
            ) : (
              alerts.map((alert) => (
                <AlertCard key={alert.id} alert={alert} onDismiss={dismissAlert} />
              ))
            )}
          </div>
        </TabsContent>

        <TabsContent value="activity">
          <Card>
            <CardHeader>
              <CardTitle>Recent Activity</CardTitle>
              <CardDescription>
                Your recent interactions with candidates
              </CardDescription>
            </CardHeader>
            <CardContent>
              <ScrollArea className="h-[500px]">
                {mockActivityEvents.map((event, i) => (
                  <ActivityItem key={i} event={event} />
                ))}
              </ScrollArea>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      {/* Quick Actions Footer */}
      <Card className="mt-6">
        <CardHeader>
          <CardTitle>Quick Actions</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap gap-3">
            <Button variant="outline">
              <span className="mr-2">📄</span> Upload Resumes
            </Button>
            <Button variant="outline">
              <span className="mr-2">🔄</span> Sync from Dayforce
            </Button>
            <Button variant="outline">
              <span className="mr-2">🔍</span> Run Pool Match
            </Button>
            <Button variant="outline">
              <span className="mr-2">📊</span> Generate Report
            </Button>
            <Button variant="outline">
              <span className="mr-2">👥</span> Review Duplicates
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
