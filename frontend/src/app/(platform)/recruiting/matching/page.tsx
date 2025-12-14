"use client";

import { useState } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { mockCandidates, mockJobs, mockJobMatches, calculateRelevanceScore } from "@/lib/mock-data/recruiting";
import Link from "next/link";

// Extended match data for visualization
interface DetailedMatch {
  candidateId: string;
  candidateName: string;
  jobId: string;
  jobTitle: string;
  overallScore: number;
  breakdown: {
    skills: number;
    experience: number;
    location: number;
    education: number;
    embedding: number;
  };
  matchedSkills: string[];
  missingSkills: string[];
  strengths: string[];
  concerns: string[];
  llmRanking?: number;
  llmExplanation?: string;
}

// Generate detailed matches from mock data
const generateDetailedMatches = (): DetailedMatch[] => {
  return mockJobMatches.map((match) => {
    const candidate = mockCandidates.find((c) => c.id === match.candidateId);
    const job = mockJobs.find((j) => j.id === match.jobId);

    const candidateSkills = candidate?.topSkills || [];
    const jobRequiredSkills = ["Python", "JavaScript", "AWS", "React", "TypeScript", "Node.js"];
    const matchedSkills = candidateSkills.filter((s) =>
      jobRequiredSkills.some((rs) => rs.toLowerCase() === s.toLowerCase())
    );
    const missingSkills = jobRequiredSkills.filter(
      (s) => !candidateSkills.some((cs) => cs.toLowerCase() === s.toLowerCase())
    );

    return {
      candidateId: match.candidateId,
      candidateName: candidate ? `${candidate.firstName} ${candidate.lastName}` : "Unknown",
      jobId: match.jobId,
      jobTitle: job?.title || "Unknown Position",
      overallScore: match.overallScore,
      breakdown: match.breakdown,
      matchedSkills: matchedSkills.slice(0, 5),
      missingSkills: missingSkills.slice(0, 3),
      strengths: [
        match.breakdown.skills > 80 ? "Strong technical skills" : "",
        match.breakdown.experience > 80 ? "Relevant experience level" : "",
        match.breakdown.location > 90 ? "Location match" : "",
      ].filter(Boolean),
      concerns: [
        match.breakdown.skills < 60 ? "Skills gap" : "",
        match.breakdown.experience < 60 ? "Experience mismatch" : "",
        missingSkills.length > 2 ? `Missing ${missingSkills.length} key skills` : "",
      ].filter(Boolean),
      llmRanking: Math.floor(Math.random() * 5) + 1,
      llmExplanation: generateLLMExplanation(match.overallScore, matchedSkills.length),
    };
  });
};

const generateLLMExplanation = (score: number, matchedSkillsCount: number): string => {
  if (score >= 90) {
    return "Exceptional match. Candidate's experience and skills strongly align with role requirements. Recommend prioritizing for immediate interview.";
  } else if (score >= 80) {
    return "Strong candidate. Core competencies match well. Minor skill gaps could be addressed through onboarding.";
  } else if (score >= 70) {
    return "Good potential fit. Relevant background with transferable skills. May need assessment of specific technical areas.";
  } else {
    return "Partial match. Some relevant experience but significant skill gaps. Consider for junior roles or training programs.";
  }
};

// Simulated Dayforce job sync
interface DayforceJob {
  id: string;
  title: string;
  department: string;
  location: string;
  reqId: string;
  hiringManager: string;
  syncStatus: "new" | "updated" | "unchanged";
  matchCount: number;
}

const simulatedDayforceJobs: DayforceJob[] = [
  {
    id: "df-1",
    title: "Senior Data Engineer",
    department: "Data Platform",
    location: "San Francisco, CA",
    reqId: "REQ-2024-0156",
    hiringManager: "Lisa Wang",
    syncStatus: "new",
    matchCount: 12,
  },
  {
    id: "df-2",
    title: "Frontend Developer",
    department: "Product",
    location: "Remote",
    reqId: "REQ-2024-0157",
    hiringManager: "Mike Chen",
    syncStatus: "new",
    matchCount: 8,
  },
  {
    id: "df-3",
    title: "Cloud Architect",
    department: "Infrastructure",
    location: "Seattle, WA",
    reqId: "REQ-2024-0158",
    hiringManager: "Sarah Johnson",
    syncStatus: "updated",
    matchCount: 5,
  },
];

// Score breakdown bar
function ScoreBar({ label, value, color }: { label: string; value: number; color: string }) {
  return (
    <div className="space-y-1">
      <div className="flex justify-between text-sm">
        <span>{label}</span>
        <span className="font-medium">{value}%</span>
      </div>
      <div className="h-2 bg-gray-200 rounded-full overflow-hidden">
        <div className={`h-full ${color} rounded-full`} style={{ width: `${value}%` }} />
      </div>
    </div>
  );
}

// Match card component
function MatchCard({ match, showJob = true }: { match: DetailedMatch; showJob?: boolean }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <Card className="mb-4 hover:shadow-lg transition-all">
      <CardHeader className="pb-2">
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-3">
            <Avatar>
              <AvatarFallback>
                {match.candidateName.split(" ").map((n) => n[0]).join("")}
              </AvatarFallback>
            </Avatar>
            <div>
              <CardTitle className="text-lg">{match.candidateName}</CardTitle>
              {showJob && (
                <CardDescription>Matched to: {match.jobTitle}</CardDescription>
              )}
            </div>
          </div>
          <div className="flex items-center gap-2">
            {match.llmRanking && (
              <Badge variant="outline" className="bg-purple-50 text-purple-700">
                LLM Rank #{match.llmRanking}
              </Badge>
            )}
            <Badge
              variant={match.overallScore >= 80 ? "default" : "secondary"}
              className={match.overallScore >= 80 ? "bg-green-600" : ""}
            >
              {match.overallScore}% match
            </Badge>
          </div>
        </div>
      </CardHeader>
      <CardContent>
        {/* Score Breakdown */}
        <div className="grid grid-cols-5 gap-3 mb-4">
          <ScoreBar label="Skills" value={match.breakdown.skills} color="bg-blue-500" />
          <ScoreBar label="Experience" value={match.breakdown.experience} color="bg-green-500" />
          <ScoreBar label="Location" value={match.breakdown.location} color="bg-yellow-500" />
          <ScoreBar label="Education" value={match.breakdown.education} color="bg-purple-500" />
          <ScoreBar label="Embedding" value={match.breakdown.embedding} color="bg-pink-500" />
        </div>

        {/* Skills */}
        <div className="flex flex-wrap gap-2 mb-3">
          {match.matchedSkills.map((skill) => (
            <Badge key={skill} variant="outline" className="bg-green-50 text-green-700 border-green-200">
              {skill}
            </Badge>
          ))}
          {match.missingSkills.slice(0, 2).map((skill) => (
            <Badge key={skill} variant="outline" className="bg-red-50 text-red-700 border-red-200">
              Missing: {skill}
            </Badge>
          ))}
        </div>

        {/* Expand for more details */}
        {expanded && (
          <div className="mt-4 pt-4 border-t space-y-4">
            {/* Strengths & Concerns */}
            <div className="grid grid-cols-2 gap-4">
              <div>
                <h4 className="font-medium text-green-700 mb-2">Strengths</h4>
                <ul className="text-sm space-y-1">
                  {match.strengths.map((s, i) => (
                    <li key={i} className="flex items-center gap-1">
                      <span className="text-green-500">+</span> {s}
                    </li>
                  ))}
                </ul>
              </div>
              <div>
                <h4 className="font-medium text-amber-700 mb-2">Concerns</h4>
                <ul className="text-sm space-y-1">
                  {match.concerns.map((c, i) => (
                    <li key={i} className="flex items-center gap-1">
                      <span className="text-amber-500">!</span> {c}
                    </li>
                  ))}
                </ul>
              </div>
            </div>

            {/* LLM Explanation */}
            {match.llmExplanation && (
              <div className="p-3 bg-purple-50 rounded-lg">
                <h4 className="font-medium text-purple-800 mb-1 flex items-center gap-2">
                  <span>🤖</span> AI Analysis
                </h4>
                <p className="text-sm text-purple-700">{match.llmExplanation}</p>
              </div>
            )}
          </div>
        )}

        {/* Actions */}
        <div className="flex justify-between items-center mt-4">
          <Button variant="ghost" size="sm" onClick={() => setExpanded(!expanded)}>
            {expanded ? "Show Less" : "Show More"}
          </Button>
          <div className="flex gap-2">
            <Link href={`/recruiting/candidates/${match.candidateId}`}>
              <Button variant="outline" size="sm">View Profile</Button>
            </Link>
            <Button size="sm">Contact Candidate</Button>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

// Dayforce Job Card
function DayforceJobCard({ job, onRunMatch }: { job: DayforceJob; onRunMatch: () => void }) {
  return (
    <div className="p-4 border rounded-lg hover:shadow-md transition-all">
      <div className="flex items-start justify-between">
        <div>
          <div className="flex items-center gap-2">
            <h4 className="font-medium">{job.title}</h4>
            <Badge
              variant={job.syncStatus === "new" ? "default" : "secondary"}
              className={job.syncStatus === "new" ? "bg-blue-600" : ""}
            >
              {job.syncStatus}
            </Badge>
          </div>
          <p className="text-sm text-gray-500">
            {job.department} • {job.location}
          </p>
          <p className="text-xs text-gray-400 mt-1">
            {job.reqId} • HM: {job.hiringManager}
          </p>
        </div>
        <div className="text-right">
          <p className="text-2xl font-bold text-green-600">{job.matchCount}</p>
          <p className="text-xs text-gray-500">candidates match</p>
        </div>
      </div>
      <div className="mt-4 flex gap-2">
        <Button size="sm" variant="outline" onClick={onRunMatch}>
          Run Match
        </Button>
        <Button size="sm" variant="outline">View Matches</Button>
        <Button size="sm">Create Job Post</Button>
      </div>
    </div>
  );
}

export default function JobMatchingPage() {
  const [activeTab, setActiveTab] = useState("overview");
  const [selectedJobId, setSelectedJobId] = useState<string | null>(null);
  const [matchingInProgress, setMatchingInProgress] = useState(false);

  const detailedMatches = generateDetailedMatches();

  // Group matches by job
  const matchesByJob = mockJobs.map((job) => ({
    job,
    matches: detailedMatches.filter((m) => m.jobId === job.id).sort((a, b) => b.overallScore - a.overallScore),
  }));

  // Group matches by candidate
  const matchesByCandidate = mockCandidates.map((candidate) => ({
    candidate,
    matches: detailedMatches
      .filter((m) => m.candidateId === candidate.id)
      .sort((a, b) => b.overallScore - a.overallScore),
  }));

  const runPoolMatch = async () => {
    setMatchingInProgress(true);
    // Simulate matching process
    await new Promise((r) => setTimeout(r, 2000));
    setMatchingInProgress(false);
  };

  return (
    <div className="container mx-auto py-6 px-4">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-3xl font-bold">Job Matching</h1>
          <p className="text-gray-500">
            Two-way matching: candidates to jobs and jobs to candidate pool
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={runPoolMatch} disabled={matchingInProgress}>
            {matchingInProgress ? "Matching..." : "Run Full Pool Match"}
          </Button>
          <Link href="/recruiting/dashboard">
            <Button variant="outline">Dashboard</Button>
          </Link>
        </div>
      </div>

      {/* Matching Engine Info */}
      <Card className="mb-6">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <span>🎯</span> Hybrid Matching Engine
          </CardTitle>
          <CardDescription>
            Multi-stage matching pipeline for optimal candidate-job pairing
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
            {[
              { stage: "Hard Filters", desc: "Location, Visa, Experience", icon: "🔍" },
              { stage: "Skill Tags", desc: "Pre-indexed intersection", icon: "🏷️" },
              { stage: "Embeddings", desc: "pgvector similarity", icon: "🧮" },
              { stage: "LLM Rerank", desc: "GPT-4 analysis (top 20)", icon: "🤖" },
              { stage: "Final Score", desc: "Weighted combination", icon: "✨" },
            ].map((item, i) => (
              <div key={i} className="text-center p-3 bg-gray-50 rounded-lg">
                <div className="text-2xl mb-1">{item.icon}</div>
                <h4 className="font-medium text-sm">{item.stage}</h4>
                <p className="text-xs text-gray-500">{item.desc}</p>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList className="mb-4">
          <TabsTrigger value="overview">Match Overview</TabsTrigger>
          <TabsTrigger value="by-job">By Job Opening</TabsTrigger>
          <TabsTrigger value="by-candidate">By Candidate</TabsTrigger>
          <TabsTrigger value="dayforce">Dayforce Sync</TabsTrigger>
        </TabsList>

        <TabsContent value="overview">
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Stats */}
            <Card>
              <CardHeader>
                <CardTitle>Match Statistics</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  <div className="flex justify-between items-center">
                    <span>Total Matches</span>
                    <span className="text-2xl font-bold">{detailedMatches.length}</span>
                  </div>
                  <div className="flex justify-between items-center">
                    <span>High Quality (80%+)</span>
                    <span className="text-xl font-bold text-green-600">
                      {detailedMatches.filter((m) => m.overallScore >= 80).length}
                    </span>
                  </div>
                  <div className="flex justify-between items-center">
                    <span>Good Matches (70-79%)</span>
                    <span className="text-xl font-bold text-blue-600">
                      {detailedMatches.filter((m) => m.overallScore >= 70 && m.overallScore < 80).length}
                    </span>
                  </div>
                  <div className="flex justify-between items-center">
                    <span>Partial (60-69%)</span>
                    <span className="text-xl font-bold text-amber-600">
                      {detailedMatches.filter((m) => m.overallScore >= 60 && m.overallScore < 70).length}
                    </span>
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* Top Matches */}
            <Card className="lg:col-span-2">
              <CardHeader>
                <CardTitle>Top Matches Requiring Action</CardTitle>
                <CardDescription>High-score matches ready for outreach</CardDescription>
              </CardHeader>
              <CardContent>
                <ScrollArea className="h-[300px]">
                  {detailedMatches
                    .sort((a, b) => b.overallScore - a.overallScore)
                    .slice(0, 5)
                    .map((match, i) => (
                      <div key={i} className="flex items-center justify-between p-3 border-b last:border-0">
                        <div className="flex items-center gap-3">
                          <Avatar>
                            <AvatarFallback>
                              {match.candidateName.split(" ").map((n) => n[0]).join("")}
                            </AvatarFallback>
                          </Avatar>
                          <div>
                            <p className="font-medium">{match.candidateName}</p>
                            <p className="text-sm text-gray-500">{match.jobTitle}</p>
                          </div>
                        </div>
                        <div className="flex items-center gap-3">
                          <Badge className="bg-green-600">{match.overallScore}%</Badge>
                          <Button size="sm">Contact</Button>
                        </div>
                      </div>
                    ))}
                </ScrollArea>
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        <TabsContent value="by-job">
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Job List */}
            <Card>
              <CardHeader>
                <CardTitle>Open Positions</CardTitle>
              </CardHeader>
              <CardContent>
                <ScrollArea className="h-[600px]">
                  <div className="space-y-2">
                    {matchesByJob.map(({ job, matches }) => (
                      <div
                        key={job.id}
                        className={`p-3 rounded-lg cursor-pointer transition-all ${
                          selectedJobId === job.id ? "bg-blue-50 border border-blue-200" : "hover:bg-gray-50"
                        }`}
                        onClick={() => setSelectedJobId(job.id)}
                      >
                        <div className="flex items-center justify-between">
                          <span className="font-medium">{job.title}</span>
                          <Badge variant="secondary">{matches.length}</Badge>
                        </div>
                        <p className="text-sm text-gray-500">{job.department}</p>
                      </div>
                    ))}
                  </div>
                </ScrollArea>
              </CardContent>
            </Card>

            {/* Matches for Selected Job */}
            <div className="lg:col-span-2">
              {selectedJobId ? (
                <Card>
                  <CardHeader>
                    <CardTitle>
                      Matches for: {mockJobs.find((j) => j.id === selectedJobId)?.title}
                    </CardTitle>
                    <CardDescription>
                      Sorted by overall match score with LLM re-ranking
                    </CardDescription>
                  </CardHeader>
                  <CardContent>
                    <ScrollArea className="h-[600px]">
                      {matchesByJob
                        .find(({ job }) => job.id === selectedJobId)
                        ?.matches.map((match, i) => (
                          <MatchCard key={i} match={match} showJob={false} />
                        ))}
                    </ScrollArea>
                  </CardContent>
                </Card>
              ) : (
                <Card>
                  <CardContent className="py-12 text-center">
                    <span className="text-4xl">📋</span>
                    <h3 className="text-lg font-medium mt-4">Select a Job</h3>
                    <p className="text-gray-500">
                      Click on a job opening to see matched candidates
                    </p>
                  </CardContent>
                </Card>
              )}
            </div>
          </div>
        </TabsContent>

        <TabsContent value="by-candidate">
          <ScrollArea className="h-[700px]">
            {matchesByCandidate.map(({ candidate, matches }) => (
              <Card key={candidate.id} className="mb-4">
                <CardHeader>
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <Avatar>
                        <AvatarFallback>
                          {candidate.firstName[0]}{candidate.lastName[0]}
                        </AvatarFallback>
                      </Avatar>
                      <div>
                        <CardTitle>
                          {candidate.firstName} {candidate.lastName}
                        </CardTitle>
                        <CardDescription>
                          {candidate.currentTitle} at {candidate.currentCompany}
                        </CardDescription>
                      </div>
                    </div>
                    <Badge variant="secondary">{matches.length} job matches</Badge>
                  </div>
                </CardHeader>
                <CardContent>
                  <div className="space-y-2">
                    {matches.map((match, i) => (
                      <div
                        key={i}
                        className="flex items-center justify-between p-3 bg-gray-50 rounded-lg"
                      >
                        <div>
                          <span className="font-medium">{match.jobTitle}</span>
                          <div className="flex gap-2 mt-1">
                            {match.matchedSkills.slice(0, 3).map((skill) => (
                              <Badge key={skill} variant="outline" className="text-xs">
                                {skill}
                              </Badge>
                            ))}
                          </div>
                        </div>
                        <div className="flex items-center gap-3">
                          <Badge
                            className={match.overallScore >= 80 ? "bg-green-600" : ""}
                          >
                            {match.overallScore}%
                          </Badge>
                          <Button size="sm" variant="outline">
                            View Match
                          </Button>
                        </div>
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>
            ))}
          </ScrollArea>
        </TabsContent>

        <TabsContent value="dayforce">
          <div className="space-y-6">
            {/* Sync Status */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <span>🔄</span> Dayforce Job Sync
                </CardTitle>
                <CardDescription>
                  Automatically import job openings from Dayforce HCM and match against candidate pool
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="flex items-center justify-between p-4 bg-green-50 border border-green-200 rounded-lg mb-4">
                  <div>
                    <p className="font-medium text-green-800">Last Sync: 2 hours ago</p>
                    <p className="text-sm text-green-700">
                      3 new jobs imported, 25 matches found
                    </p>
                  </div>
                  <Button>Sync Now</Button>
                </div>

                <h3 className="font-medium mb-3">Recent Dayforce Imports</h3>
                <div className="space-y-3">
                  {simulatedDayforceJobs.map((job) => (
                    <DayforceJobCard key={job.id} job={job} onRunMatch={runPoolMatch} />
                  ))}
                </div>
              </CardContent>
            </Card>

            {/* Sync Configuration */}
            <Card>
              <CardHeader>
                <CardTitle>Sync Configuration</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  <div className="p-4 bg-gray-50 rounded-lg">
                    <h4 className="font-medium mb-2">Sync Frequency</h4>
                    <p className="text-2xl font-bold">Every 15 min</p>
                  </div>
                  <div className="p-4 bg-gray-50 rounded-lg">
                    <h4 className="font-medium mb-2">Auto-Match Threshold</h4>
                    <p className="text-2xl font-bold">70%</p>
                  </div>
                  <div className="p-4 bg-gray-50 rounded-lg">
                    <h4 className="font-medium mb-2">Alert on High Match</h4>
                    <p className="text-2xl font-bold">85%+</p>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
}
