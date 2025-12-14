"use client";

import { useState, useCallback } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  mockJobs,
  calculateRelevanceScore,
  getConfidenceLabel,
  getConfidenceLabelColor,
  type ConfidenceLabel,
  type ExtractionMethod,
  type DuplicateMatchReason,
} from "@/lib/mock-data/recruiting";
import Link from "next/link";

// Simulated extraction result type with model provenance
interface ExtractedFact {
  field: string;
  value: string;
  confidence: number;
  confidenceLabel: ConfidenceLabel;
  source: string;
  extractionMethod: ExtractionMethod;
  modelName?: string;
  modelVersion?: string;
  promptVersion?: string;
}

interface DuplicateReason {
  type: DuplicateMatchReason;
  confidence: number;
  detail: string;
}

interface ExtractionResult {
  candidateId: string;
  candidateName: string;
  email: string;
  facts: ExtractedFact[];
  modelProvenance: {
    modelName: string;
    modelVersion: string;
    promptVersion: string;
  };
  jobMatches: Array<{
    jobId: string;
    jobTitle: string;
    score: number;
    reasons: string[];
  }>;
  duplicateCheck: {
    found: boolean;
    existingId?: string;
    existingName?: string;
    matchScore?: number;
    matchType?: "hard" | "strong" | "fuzzy" | "review";
    reasons?: DuplicateReason[];
  };
}

// Processing stages
type ProcessingStage =
  | "idle"
  | "uploading"
  | "extracting_text"
  | "llm_extraction"
  | "generating_embeddings"
  | "matching_jobs"
  | "checking_duplicates"
  | "complete";

const stageLabels: Record<ProcessingStage, string> = {
  idle: "Ready to process",
  uploading: "Uploading file...",
  extracting_text: "Extracting text from document...",
  llm_extraction: "LLM extracting structured facts...",
  generating_embeddings: "Generating vector embeddings...",
  matching_jobs: "Matching against open positions...",
  checking_duplicates: "Checking for duplicates...",
  complete: "Processing complete!",
};

const stageProgress: Record<ProcessingStage, number> = {
  idle: 0,
  uploading: 10,
  extracting_text: 25,
  llm_extraction: 50,
  generating_embeddings: 70,
  matching_jobs: 85,
  checking_duplicates: 95,
  complete: 100,
};

// Sample resume templates for simulation
const sampleResumes = [
  {
    name: "Software Engineer Resume",
    content: `
JOHN DOE
Senior Software Engineer
john.doe@email.com | (555) 123-4567 | San Francisco, CA
LinkedIn: linkedin.com/in/johndoe

SUMMARY
Experienced software engineer with 8+ years of expertise in Python, JavaScript, and cloud technologies.
Passionate about building scalable systems and mentoring junior developers.

EXPERIENCE
Senior Software Engineer | TechCorp Inc. | 2020 - Present
- Led development of microservices architecture serving 10M+ users
- Implemented CI/CD pipelines reducing deployment time by 60%
- Mentored team of 5 junior engineers

Software Engineer | StartupXYZ | 2017 - 2020
- Built real-time data processing pipeline using Apache Kafka
- Developed REST APIs using Python FastAPI
- Improved system performance by 40% through optimization

EDUCATION
BS Computer Science | Stanford University | 2017

SKILLS
Python, JavaScript, TypeScript, React, Node.js, AWS, Docker, Kubernetes, PostgreSQL, MongoDB

CERTIFICATIONS
AWS Solutions Architect - Professional (2023)
Google Cloud Professional Data Engineer (2022)
    `,
  },
  {
    name: "Product Manager Resume",
    content: `
JANE SMITH
Product Manager
jane.smith@email.com | (555) 987-6543 | New York, NY

SUMMARY
Strategic product manager with 6 years of experience driving product vision and execution.
Proven track record of launching products that increased revenue by 40%.

EXPERIENCE
Senior Product Manager | BigTech Corp | 2021 - Present
- Owned product roadmap for flagship B2B SaaS platform
- Led cross-functional team of 15 (engineering, design, data science)
- Launched 3 major features driving $5M ARR

Product Manager | Growth Startup | 2018 - 2021
- Managed product lifecycle from ideation to launch
- Conducted user research and A/B testing
- Increased user engagement by 50%

EDUCATION
MBA | Wharton School of Business | 2018
BA Economics | Yale University | 2014

SKILLS
Product Strategy, Agile/Scrum, User Research, Data Analysis, SQL, Figma, JIRA
    `,
  },
  {
    name: "DevOps Engineer Resume",
    content: `
ALEX JOHNSON
DevOps Engineer
alex.j@email.com | (555) 456-7890 | Seattle, WA

SUMMARY
DevOps specialist with 5 years of experience in cloud infrastructure and automation.
Expert in containerization, CI/CD, and infrastructure as code.

EXPERIENCE
DevOps Engineer | CloudFirst Inc. | 2020 - Present
- Managed Kubernetes clusters handling 500K+ requests/second
- Implemented GitOps workflow with ArgoCD
- Reduced infrastructure costs by 35% through optimization

Systems Administrator | TechServices | 2018 - 2020
- Maintained Linux servers and network infrastructure
- Automated routine tasks with Ansible and Python
- Achieved 99.99% uptime SLA

EDUCATION
BS Information Technology | University of Washington | 2018

SKILLS
AWS, GCP, Kubernetes, Docker, Terraform, Ansible, Jenkins, GitHub Actions, Prometheus, Grafana

CERTIFICATIONS
AWS DevOps Professional (2023)
Kubernetes Administrator (CKA) (2022)
    `,
  },
];

// Confidence badge component with semantic labels
function ConfidenceBadge({ confidence }: { confidence: number }) {
  const label = getConfidenceLabel(confidence);
  const color = getConfidenceLabelColor(label);

  return (
    <span className={`text-xs px-2 py-0.5 rounded border ${color}`}>
      {label} ({Math.round(confidence * 100)}%)
    </span>
  );
}

export default function ResumeUploadPage() {
  const [stage, setStage] = useState<ProcessingStage>("idle");
  const [selectedResume, setSelectedResume] = useState(0);
  const [customResume, setCustomResume] = useState("");
  const [useCustom, setUseCustom] = useState(false);
  const [result, setResult] = useState<ExtractionResult | null>(null);
  const [processingLogs, setProcessingLogs] = useState<string[]>([]);

  const addLog = useCallback((message: string) => {
    setProcessingLogs((prev) => [...prev, `[${new Date().toLocaleTimeString()}] ${message}`]);
  }, []);

  // Simulate the extraction pipeline
  const simulateExtraction = async () => {
    const resumeText = useCustom ? customResume : sampleResumes[selectedResume].content;

    setProcessingLogs([]);
    setResult(null);

    // Stage 1: Uploading
    setStage("uploading");
    addLog("Starting file upload...");
    await new Promise((r) => setTimeout(r, 500));
    addLog("File uploaded successfully (simulated)");

    // Stage 2: Text extraction
    setStage("extracting_text");
    addLog("Extracting text from document...");
    await new Promise((r) => setTimeout(r, 800));
    addLog(`Extracted ${resumeText.length} characters of text`);

    // Stage 3: LLM extraction
    setStage("llm_extraction");
    addLog("Sending to GPT-4 for structured extraction...");
    await new Promise((r) => setTimeout(r, 1500));

    // Generate simulated extracted facts based on resume content
    const facts = generateFacts(resumeText);
    addLog(`Extracted ${facts.length} facts with confidence scores`);

    // Stage 4: Generate embeddings
    setStage("generating_embeddings");
    addLog("Generating text-embedding-ada-002 vectors...");
    await new Promise((r) => setTimeout(r, 1000));
    addLog("Generated 1536-dimensional embedding vector");

    // Stage 5: Job matching
    setStage("matching_jobs");
    addLog("Running pgvector similarity search against open positions...");
    await new Promise((r) => setTimeout(r, 800));

    const matches = generateJobMatches(facts);
    addLog(`Found ${matches.length} potential job matches`);

    // Stage 6: Duplicate check
    setStage("checking_duplicates");
    addLog("Checking for duplicate candidates...");
    await new Promise((r) => setTimeout(r, 600));

    const duplicateCheck = checkDuplicates(facts);
    if (duplicateCheck.found) {
      addLog(`Potential duplicate found: ${duplicateCheck.existingName} (${duplicateCheck.matchType})`);
    } else {
      addLog("No duplicates found - new candidate");
    }

    // Complete
    setStage("complete");
    addLog("Processing complete!");

    // Build result
    const candidateName = facts.find((f) => f.field === "name")?.value || "Unknown";
    const email = facts.find((f) => f.field === "email")?.value || "unknown@email.com";

    setResult({
      candidateId: `new-${Date.now()}`,
      candidateName,
      email,
      facts,
      modelProvenance: {
        modelName: "gpt-4",
        modelVersion: "0613",
        promptVersion: "v2.1",
      },
      jobMatches: matches,
      duplicateCheck,
    });
  };

  // Helper to create fact with confidence label and model provenance
  const createFact = (
    field: string,
    value: string,
    confidence: number,
    source: string,
    extractionMethod: ExtractionMethod = "llm"
  ): ExtractedFact => ({
    field,
    value,
    confidence,
    confidenceLabel: getConfidenceLabel(confidence),
    source,
    extractionMethod,
    modelName: "gpt-4",
    modelVersion: "0613",
    promptVersion: "v2.1",
  });

  // Generate facts from resume text
  const generateFacts = (text: string): ExtractedFact[] => {
    const facts: ExtractedFact[] = [];

    // Extract name (first line usually)
    const lines = text.trim().split("\n").filter((l) => l.trim());
    if (lines.length > 0) {
      const nameLine = lines[0].trim();
      if (nameLine.length < 50 && !nameLine.includes("@")) {
        facts.push(createFact("name", nameLine, 0.95, "resume_header"));
      }
    }

    // Extract email
    const emailMatch = text.match(/[\w.-]+@[\w.-]+\.\w+/);
    if (emailMatch) {
      facts.push(createFact("email", emailMatch[0], 1.0, "contact_info"));
    }

    // Extract phone
    const phoneMatch = text.match(/\(\d{3}\)\s?\d{3}-\d{4}/);
    if (phoneMatch) {
      facts.push(createFact("phone", phoneMatch[0], 0.98, "contact_info"));
    }

    // Extract title
    const titleKeywords = ["Engineer", "Manager", "Developer", "Designer", "Analyst", "Architect", "Lead"];
    for (const keyword of titleKeywords) {
      const titleMatch = text.match(new RegExp(`(Senior |Lead |Staff |Principal )?(\\w+ )*${keyword}`, "i"));
      if (titleMatch) {
        facts.push(createFact("current_title", titleMatch[0], 0.88, "summary"));
        break;
      }
    }

    // Extract years of experience
    const expMatch = text.match(/(\d+)\+?\s*years?\s*(of\s*)?(experience|expertise)/i);
    if (expMatch) {
      facts.push(createFact("years_experience", expMatch[1], 0.92, "summary"));
    }

    // Extract skills
    const skillsSection = text.match(/SKILLS[\s\S]*?(?=\n[A-Z]{4,}|\n*$)/i);
    if (skillsSection) {
      const skillList = skillsSection[0].replace(/SKILLS/i, "").split(/[,|•\n]/).map((s) => s.trim()).filter((s) => s && s.length < 30);
      skillList.slice(0, 8).forEach((skill, i) => {
        const conf = 0.85 - (i * 0.03);
        facts.push(createFact("skill", skill, conf, "skills_section"));
      });
    }

    // Extract education
    const eduMatch = text.match(/(BS|BA|MS|MBA|PhD|Master|Bachelor)[^|]*?(University|School|College|Institute)[^|]*?\d{4}/i);
    if (eduMatch) {
      facts.push(createFact("education", eduMatch[0].trim(), 0.9, "education_section"));
    }

    // Extract certifications with relevance decay
    const certMatches = text.match(/([A-Z]+\s)?(Certified|Certification|Certificate)[^()\n]*\(\d{4}\)/gi);
    if (certMatches) {
      certMatches.forEach((cert) => {
        const yearMatch = cert.match(/\((\d{4})\)/);
        const year = yearMatch ? parseInt(yearMatch[1]) : 2024;
        const ageYears = new Date().getFullYear() - year;
        // Apply relevance decay to confidence
        let confidence = 0.95;
        if (ageYears > 5) confidence = 0.55; // "Uncertain"
        else if (ageYears > 3) confidence = 0.70; // "Inferred"
        else if (ageYears > 1) confidence = 0.85; // "Very Likely"

        facts.push(createFact(
          "certification",
          cert.replace(/\(\d{4}\)/, "").trim(),
          confidence,
          `certification_${year}`
        ));
      });
    }

    // Extract companies
    const companyPatterns = /(?:at|@|,)\s*([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)*(?:\s+(?:Inc|Corp|LLC|Ltd|Co)\.?)?)/g;
    let companyMatch;
    const companies = new Set<string>();
    while ((companyMatch = companyPatterns.exec(text)) !== null) {
      if (companyMatch[1].length < 40 && !companyMatch[1].match(/University|School|College/i)) {
        companies.add(companyMatch[1]);
      }
    }
    Array.from(companies).slice(0, 3).forEach((company, i) => {
      const conf = 0.82 - (i * 0.1);
      facts.push(createFact(
        i === 0 ? "current_company" : "previous_company",
        company,
        conf,
        "experience_section"
      ));
    });

    return facts;
  };

  // Generate job matches
  const generateJobMatches = (facts: ExtractedFact[]) => {
    const skills = facts.filter((f) => f.field === "skill").map((f) => f.value.toLowerCase());
    const title = facts.find((f) => f.field === "current_title")?.value.toLowerCase() || "";

    return mockJobs
      .filter((job) => job.status === "open")
      .map((job) => {
        let score = 50 + Math.random() * 30;
        const reasons: string[] = [];

        // Title match
        if (title.includes("engineer") && job.title.toLowerCase().includes("engineer")) {
          score += 20;
          reasons.push("Title match: Engineer");
        }
        if (title.includes("manager") && job.title.toLowerCase().includes("manager")) {
          score += 20;
          reasons.push("Title match: Manager");
        }

        // Skills match (simulated)
        const jobSkills = ["python", "javascript", "aws", "react", "kubernetes"];
        const matchedSkills = skills.filter((s) =>
          jobSkills.some((js) => s.includes(js) || js.includes(s))
        );
        if (matchedSkills.length > 0) {
          score += matchedSkills.length * 5;
          reasons.push(`${matchedSkills.length} skills matched`);
        }

        return {
          jobId: job.id,
          jobTitle: job.title,
          score: Math.min(98, Math.round(score)),
          reasons,
        };
      })
      .sort((a, b) => b.score - a.score)
      .slice(0, 4);
  };

  // Check for duplicates with explicit reasons
  const checkDuplicates = (facts: ExtractedFact[]): ExtractionResult["duplicateCheck"] => {
    const email = facts.find((f) => f.field === "email")?.value;
    const name = facts.find((f) => f.field === "name")?.value;
    const company = facts.find((f) => f.field === "current_company")?.value;

    // Simulate 25% chance of hard match (email)
    if (Math.random() < 0.25 && email) {
      return {
        found: true,
        existingId: "c-existing-123",
        existingName: "John D.",
        matchScore: 0.99,
        matchType: "hard",
        reasons: [
          { type: "email_match", confidence: 1.0, detail: `Same email: ${email}` },
        ],
      };
    }

    // Simulate 15% chance of strong match (name + company)
    if (Math.random() < 0.15 && name) {
      return {
        found: true,
        existingId: "c-existing-456",
        existingName: "J. Doe",
        matchScore: 0.92,
        matchType: "strong",
        reasons: [
          { type: "name_similarity", confidence: 0.88, detail: `Name similarity: ${name} (Jaro-Winkler: 0.88)` },
          ...(company ? [{ type: "company_overlap" as DuplicateMatchReason, confidence: 0.95, detail: `Both worked at ${company}` }] : []),
        ],
      };
    }

    // Simulate 10% chance of fuzzy match (review queue)
    if (Math.random() < 0.1) {
      return {
        found: true,
        existingId: "c-existing-789",
        existingName: "Similar Candidate",
        matchScore: 0.72,
        matchType: "review",
        reasons: [
          { type: "resume_similarity", confidence: 0.72, detail: "Embedding cosine similarity: 0.72" },
          { type: "name_similarity", confidence: 0.65, detail: "Weak name match (Jaro-Winkler: 0.65)" },
        ],
      };
    }

    return { found: false };
  };

  const resetProcess = () => {
    setStage("idle");
    setResult(null);
    setProcessingLogs([]);
  };

  return (
    <div className="container mx-auto py-6 px-4">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-3xl font-bold">Resume Upload Simulation</h1>
          <p className="text-gray-500">
            Simulate the full resume ingestion pipeline with LLM extraction
          </p>
        </div>
        <Link href="/recruiting/dashboard">
          <Button variant="outline">Back to Dashboard</Button>
        </Link>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Input Section */}
        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Select Resume Source</CardTitle>
              <CardDescription>
                Choose a sample resume or paste your own
              </CardDescription>
            </CardHeader>
            <CardContent>
              <Tabs defaultValue="samples">
                <TabsList className="mb-4">
                  <TabsTrigger value="samples" onClick={() => setUseCustom(false)}>
                    Sample Resumes
                  </TabsTrigger>
                  <TabsTrigger value="custom" onClick={() => setUseCustom(true)}>
                    Custom Text
                  </TabsTrigger>
                </TabsList>

                <TabsContent value="samples">
                  <div className="space-y-3">
                    {sampleResumes.map((resume, i) => (
                      <div
                        key={i}
                        className={`p-4 border rounded-lg cursor-pointer transition-all ${
                          selectedResume === i && !useCustom
                            ? "border-blue-500 bg-blue-50"
                            : "hover:border-gray-400"
                        }`}
                        onClick={() => {
                          setSelectedResume(i);
                          setUseCustom(false);
                        }}
                      >
                        <div className="flex items-center justify-between">
                          <span className="font-medium">{resume.name}</span>
                          {selectedResume === i && !useCustom && (
                            <Badge variant="default">Selected</Badge>
                          )}
                        </div>
                        <p className="text-sm text-gray-500 mt-1">
                          {resume.content.slice(0, 100).trim()}...
                        </p>
                      </div>
                    ))}
                  </div>
                </TabsContent>

                <TabsContent value="custom">
                  <div className="space-y-3">
                    <Label>Paste Resume Text</Label>
                    <Textarea
                      value={customResume}
                      onChange={(e) => setCustomResume(e.target.value)}
                      placeholder="Paste resume content here..."
                      className="min-h-[200px] font-mono text-sm"
                    />
                  </div>
                </TabsContent>
              </Tabs>

              <div className="mt-6 flex gap-3">
                <Button
                  onClick={simulateExtraction}
                  disabled={stage !== "idle" && stage !== "complete"}
                  className="flex-1"
                >
                  {stage === "idle" ? "Start Processing" : "Processing..."}
                </Button>
                {stage === "complete" && (
                  <Button variant="outline" onClick={resetProcess}>
                    Reset
                  </Button>
                )}
              </div>
            </CardContent>
          </Card>

          {/* Processing Logs */}
          <Card>
            <CardHeader>
              <CardTitle>Processing Log</CardTitle>
              <CardDescription>Real-time pipeline status</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="mb-4">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm font-medium">{stageLabels[stage]}</span>
                  <span className="text-sm text-gray-500">{stageProgress[stage]}%</span>
                </div>
                <Progress value={stageProgress[stage]} className="h-2" />
              </div>

              <ScrollArea className="h-[200px] bg-gray-900 rounded-lg p-3">
                <div className="font-mono text-xs text-green-400 space-y-1">
                  {processingLogs.length === 0 ? (
                    <p className="text-gray-500">Waiting to start...</p>
                  ) : (
                    processingLogs.map((log, i) => <p key={i}>{log}</p>)
                  )}
                </div>
              </ScrollArea>
            </CardContent>
          </Card>
        </div>

        {/* Results Section */}
        <div className="space-y-6">
          {result ? (
            <>
              {/* Candidate Summary */}
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center justify-between">
                    <span>Extracted Candidate</span>
                    <Badge variant="default" className="bg-green-600">
                      New
                    </Badge>
                  </CardTitle>
                  <CardDescription>
                    ID: {result.candidateId}
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="space-y-4">
                    <div>
                      <h3 className="text-xl font-bold">{result.candidateName}</h3>
                      <p className="text-gray-500">{result.email}</p>
                    </div>

                    {result.duplicateCheck.found && (
                      <div className="p-4 bg-amber-50 border border-amber-200 rounded-lg">
                        <div className="flex items-start gap-3">
                          <span className="text-2xl">⚠️</span>
                          <div className="flex-1">
                            <div className="flex items-center gap-2 mb-1">
                              <p className="font-medium text-amber-800">
                                Potential Duplicate Detected
                              </p>
                              <Badge
                                variant="outline"
                                className={
                                  result.duplicateCheck.matchType === "hard"
                                    ? "border-red-500 text-red-700 bg-red-50"
                                    : result.duplicateCheck.matchType === "strong"
                                    ? "border-orange-500 text-orange-700 bg-orange-50"
                                    : result.duplicateCheck.matchType === "fuzzy"
                                    ? "border-yellow-500 text-yellow-700 bg-yellow-50"
                                    : "border-gray-500 text-gray-700 bg-gray-50"
                                }
                              >
                                {result.duplicateCheck.matchType === "hard"
                                  ? "Auto-Merge"
                                  : result.duplicateCheck.matchType === "strong"
                                  ? "High Confidence"
                                  : result.duplicateCheck.matchType === "fuzzy"
                                  ? "Medium Confidence"
                                  : "Needs Review"}
                              </Badge>
                            </div>
                            <p className="text-sm text-amber-700 mb-3">
                              Matches: <span className="font-semibold">{result.duplicateCheck.existingName}</span>
                              <span className="ml-2 text-amber-600">
                                ({Math.round((result.duplicateCheck.matchScore || 0) * 100)}% overall confidence)
                              </span>
                            </p>

                            {/* Explicit Reasons List */}
                            {result.duplicateCheck.reasons && result.duplicateCheck.reasons.length > 0 && (
                              <div className="bg-white/50 rounded p-2 mb-3 space-y-1.5">
                                <p className="text-xs font-medium text-amber-800 uppercase tracking-wide">Why this matched:</p>
                                {result.duplicateCheck.reasons.map((reason, idx) => (
                                  <div key={idx} className="flex items-center gap-2 text-sm">
                                    <span className={`w-2 h-2 rounded-full ${
                                      reason.confidence >= 0.95 ? "bg-green-500" :
                                      reason.confidence >= 0.80 ? "bg-blue-500" :
                                      reason.confidence >= 0.65 ? "bg-yellow-500" :
                                      "bg-red-500"
                                    }`} />
                                    <span className="text-gray-700">{reason.detail}</span>
                                    <ConfidenceBadge confidence={reason.confidence} />
                                  </div>
                                ))}
                              </div>
                            )}
                          </div>
                        </div>
                        <div className="mt-3 flex gap-2 ml-9">
                          {result.duplicateCheck.matchType === "hard" ? (
                            <Button size="sm" variant="default" className="bg-amber-600 hover:bg-amber-700">
                              Auto-Merge (Same Person)
                            </Button>
                          ) : (
                            <>
                              <Button size="sm" variant="outline">
                                Review & Merge
                              </Button>
                              <Button size="sm" variant="outline">
                                Keep Separate
                              </Button>
                            </>
                          )}
                        </div>
                      </div>
                    )}
                  </div>
                </CardContent>
              </Card>

              {/* Extracted Facts */}
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center justify-between">
                    <span>Extracted Facts</span>
                    <div className="flex items-center gap-2">
                      <Badge variant="outline" className="text-xs font-normal">
                        Model: {result.modelProvenance.modelName}
                      </Badge>
                      <Badge variant="outline" className="text-xs font-normal">
                        v{result.modelProvenance.modelVersion}
                      </Badge>
                      <Badge variant="outline" className="text-xs font-normal">
                        Prompt: {result.modelProvenance.promptVersion}
                      </Badge>
                    </div>
                  </CardTitle>
                  <CardDescription>
                    LLM-extracted observations with confidence scores and provenance
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <ScrollArea className="h-[350px]">
                    <div className="space-y-2">
                      {result.facts.map((fact, i) => (
                        <div
                          key={i}
                          className="p-3 bg-gray-50 rounded border border-gray-100 hover:border-gray-200 transition-colors"
                        >
                          <div className="flex items-start justify-between">
                            <div className="flex-1">
                              <div className="flex items-center gap-2 mb-1">
                                <span className="text-xs text-gray-500 uppercase font-medium">
                                  {fact.field}
                                </span>
                                <Badge
                                  variant="outline"
                                  className={`text-[10px] h-4 ${
                                    fact.extractionMethod === "llm"
                                      ? "border-purple-300 text-purple-600 bg-purple-50"
                                      : fact.extractionMethod === "manual"
                                      ? "border-blue-300 text-blue-600 bg-blue-50"
                                      : fact.extractionMethod === "linkedin"
                                      ? "border-sky-300 text-sky-600 bg-sky-50"
                                      : fact.extractionMethod === "external_scrape"
                                      ? "border-amber-300 text-amber-600 bg-amber-50"
                                      : "border-gray-300 text-gray-600 bg-gray-50"
                                  }`}
                                >
                                  {fact.extractionMethod.replace("_", " ")}
                                </Badge>
                              </div>
                              <p className="font-medium text-gray-900">{fact.value}</p>
                            </div>
                            <div className="flex flex-col items-end gap-1">
                              <ConfidenceBadge confidence={fact.confidence} />
                              <span className="text-[10px] text-gray-400">{fact.source}</span>
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  </ScrollArea>
                </CardContent>
              </Card>

              {/* Job Matches */}
              <Card>
                <CardHeader>
                  <CardTitle>Job Matches</CardTitle>
                  <CardDescription>
                    Automatically matched against open positions
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="space-y-3">
                    {result.jobMatches.map((match) => (
                      <div
                        key={match.jobId}
                        className="p-3 border rounded-lg hover:shadow-md transition-all"
                      >
                        <div className="flex items-center justify-between">
                          <span className="font-medium">{match.jobTitle}</span>
                          <Badge
                            variant={match.score >= 80 ? "default" : "secondary"}
                            className={match.score >= 80 ? "bg-green-600" : ""}
                          >
                            {match.score}% match
                          </Badge>
                        </div>
                        <div className="flex flex-wrap gap-1 mt-2">
                          {match.reasons.map((reason, i) => (
                            <span
                              key={i}
                              className="text-xs bg-gray-200 px-2 py-0.5 rounded"
                            >
                              {reason}
                            </span>
                          ))}
                        </div>
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>
            </>
          ) : (
            <Card>
              <CardContent className="py-12 text-center">
                <span className="text-6xl">📄</span>
                <h3 className="text-lg font-medium mt-4">No Results Yet</h3>
                <p className="text-gray-500">
                  Select a resume and click &quot;Start Processing&quot; to simulate the extraction pipeline.
                </p>
              </CardContent>
            </Card>
          )}
        </div>
      </div>

      {/* Pipeline Explanation */}
      <Card className="mt-6">
        <CardHeader>
          <CardTitle>Processing Pipeline</CardTitle>
          <CardDescription>
            How resumes are processed in the system
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-6 gap-4">
            {[
              { icon: "📤", title: "Upload", desc: "File received" },
              { icon: "📝", title: "Text Extract", desc: "PDF/DOCX parsing" },
              { icon: "🤖", title: "LLM Extract", desc: "GPT-4 structured facts" },
              { icon: "🧮", title: "Embeddings", desc: "Vector generation" },
              { icon: "🎯", title: "Job Match", desc: "pgvector similarity" },
              { icon: "👥", title: "Dedup Check", desc: "Identity resolution" },
            ].map((step, i) => (
              <div key={i} className="text-center">
                <div className="text-3xl mb-2">{step.icon}</div>
                <h4 className="font-medium">{step.title}</h4>
                <p className="text-xs text-gray-500">{step.desc}</p>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
