/**
 * Mock data for Recruiting UX testing
 * This allows testing the frontend without backend dependency
 *
 * IMPORTANT: These interfaces serve as the API contract.
 * Backend must implement these exact shapes.
 */

// =============================================================================
// CONFIDENCE INTERPRETATION (Recruiters think in words, not numbers)
// =============================================================================
export type ConfidenceLabel = "Explicit" | "Very Likely" | "Inferred" | "Uncertain";

export function getConfidenceLabel(confidence: number): ConfidenceLabel {
  if (confidence >= 0.95) return "Explicit";
  if (confidence >= 0.80) return "Very Likely";
  if (confidence >= 0.65) return "Inferred";
  return "Uncertain";
}

export function getConfidenceLabelColor(label: ConfidenceLabel): string {
  switch (label) {
    case "Explicit": return "bg-green-100 text-green-800 border-green-200";
    case "Very Likely": return "bg-blue-100 text-blue-800 border-blue-200";
    case "Inferred": return "bg-yellow-100 text-yellow-800 border-yellow-200";
    case "Uncertain": return "bg-red-100 text-red-800 border-red-200";
  }
}

// =============================================================================
// EXTRACTION METHOD TYPES
// =============================================================================
export type ExtractionMethod =
  | "llm"           // LLM extraction from resume
  | "manual"        // Human-entered data
  | "linkedin"      // LinkedIn import
  | "form"          // Application form submission
  | "external_scrape" // External enrichment (best-effort)
  | "system";       // System-generated

// =============================================================================
// DUPLICATE MATCH REASONS (Always show WHY)
// =============================================================================
export type DuplicateMatchReason =
  | "email_match"           // Same email address (hard match)
  | "linkedin_match"        // Same LinkedIn URL (hard match)
  | "name_similarity"       // Similar name (fuzzy)
  | "resume_similarity"     // High embedding similarity
  | "company_overlap"       // Worked at same company + similar timeline
  | "phone_match";          // Same phone number

export interface DuplicateCandidate {
  candidate_id: string;
  candidate_name: string;
  match_score: number;  // 0.0-1.0
  match_type: "hard" | "strong" | "fuzzy" | "review";
  reasons: Array<{
    type: DuplicateMatchReason;
    confidence: number;
    detail?: string;  // e.g., "Worked at TechCorp 2020-2023"
  }>;
}

// =============================================================================
// CORE DTOs (Backend API Contract)
// =============================================================================
export interface MockCandidate {
  id: string;
  firstName: string;
  lastName: string;
  email: string;
  phone: string;
  linkedinUrl: string;
  topSkills: string[];
  source: string;
  currentTitle: string;
  currentCompany: string;
  yearsExperience: number;
  createdAt: string;
  updatedAt: string;
}

export interface MockObservation {
  id: string;
  fieldName: string;
  fieldValue: string;
  valueType: "string" | "number" | "date" | "array";
  confidence: number;
  confidenceLabel: ConfidenceLabel;  // Derived from confidence
  extractionMethod: ExtractionMethod;
  sourceDocumentId: string | null;
  sourceUrl?: string;  // For external scrape
  extractedAt: string;
  isCurrent: boolean;
  // Model provenance (critical for debugging & legal)
  modelName?: string;      // e.g., "gpt-4"
  modelVersion?: string;   // e.g., "0613"
  promptVersion?: string;  // e.g., "v2.1"
  // For relevance decay visualization
  ageDays: number;
  relevanceScore: number;
}

export interface MockActivityEvent {
  id: string;
  event_type: string;
  user_id: string;
  user_name: string;
  event_data: Record<string, unknown>;
  created_at: string;
}

export interface MockResume {
  id: string;
  file_name: string;
  uploaded_at: string;
  source: string;
  is_primary: boolean;
  parsed_data: Record<string, unknown>;
  extraction_status: string;
}

export interface MockJobMatch {
  job_id: string;
  job_title: string;
  department: string;
  match_score: number;
  match_breakdown: {
    skills: number;
    experience: number;
    location: number;
  };
  matched_at: string;
}

export interface MockJob {
  id: string;
  title: string;
  department: string;
  location: string;
  status: string;
  required_skills: string[];
  min_experience: number;
  max_experience: number;
  salary_min: number;
  salary_max: number;
  created_at: string;
  candidate_matches: number;
}

// Helper to calculate relevance score based on age
export function calculateRelevanceScore(extractedAt: string): number {
  const now = new Date();
  const extracted = new Date(extractedAt);
  const ageYears = (now.getTime() - extracted.getTime()) / (1000 * 60 * 60 * 24 * 365);

  // Skills/certifications decay over time
  // 0-1 year: 100%, 1-3 years: 90%, 3-5 years: 75%, 5+ years: 50%
  if (ageYears < 1) return 1.0;
  if (ageYears < 3) return 0.9;
  if (ageYears < 5) return 0.75;
  return 0.5;
}

// Mock candidates with rich history (camelCase for API consistency)
export const mockCandidates: MockCandidate[] = [
  {
    id: "c1-jane-doe",
    firstName: "Jane",
    lastName: "Doe",
    email: "jane.doe@email.com",
    phone: "+1-555-123-4567",
    linkedinUrl: "https://linkedin.com/in/janedoe",
    topSkills: ["Python", "Machine Learning", "TensorFlow", "SQL", "AWS"],
    source: "LinkedIn",
    currentTitle: "Senior ML Engineer",
    currentCompany: "TechCorp",
    yearsExperience: 8,
    createdAt: "2024-01-15T10:00:00Z",
    updatedAt: "2025-12-10T15:30:00Z",
  },
  {
    id: "c2-john-smith",
    firstName: "John",
    lastName: "Smith",
    email: "john.smith@email.com",
    phone: "+1-555-234-5678",
    linkedinUrl: "https://linkedin.com/in/johnsmith",
    topSkills: ["React", "TypeScript", "Node.js", "GraphQL", "Docker"],
    source: "Referral",
    currentTitle: "Staff Frontend Engineer",
    currentCompany: "WebScale Inc",
    yearsExperience: 10,
    createdAt: "2024-03-20T08:00:00Z",
    updatedAt: "2025-12-12T09:00:00Z",
  },
  {
    id: "c3-alex-chen",
    firstName: "Alex",
    lastName: "Chen",
    email: "alex.chen@email.com",
    phone: "+1-555-345-6789",
    linkedinUrl: "https://linkedin.com/in/alexchen",
    topSkills: ["Java", "Spring Boot", "Kubernetes", "PostgreSQL", "Redis"],
    source: "Indeed",
    currentTitle: "Backend Tech Lead",
    currentCompany: "DataFlow Systems",
    yearsExperience: 12,
    createdAt: "2024-06-10T14:00:00Z",
    updatedAt: "2025-12-11T11:00:00Z",
  },
  {
    id: "c4-sarah-wilson",
    firstName: "Sarah",
    lastName: "Wilson",
    email: "sarah.wilson@email.com",
    phone: "+1-555-456-7890",
    linkedinUrl: "https://linkedin.com/in/sarahwilson",
    topSkills: ["Salesforce", "Apex", "LWC", "Integration", "SQL"],
    source: "Direct Apply",
    currentTitle: "Salesforce Architect",
    currentCompany: "CRM Solutions",
    yearsExperience: 7,
    createdAt: "2025-10-05T09:00:00Z",
    updatedAt: "2025-12-13T08:00:00Z",
  },
];

// Mock observations with confidence labels and model provenance
export const mockObservations: Record<string, MockObservation[]> = {
  "c1-jane-doe": [
    {
      id: "obs-1",
      fieldName: "current_title",
      fieldValue: "Senior ML Engineer",
      valueType: "string",
      confidence: 0.98,
      confidenceLabel: "Explicit",
      extractionMethod: "llm",
      sourceDocumentId: "resume-1",
      extractedAt: "2025-12-10T15:30:00Z",
      isCurrent: true,
      modelName: "gpt-4",
      modelVersion: "0613",
      promptVersion: "v2.1",
      ageDays: 3,
      relevanceScore: 1.0,
    },
    {
      id: "obs-2",
      fieldName: "skill",
      fieldValue: "TensorFlow",
      valueType: "string",
      confidence: 0.95,
      confidenceLabel: "Explicit",
      extractionMethod: "llm",
      sourceDocumentId: "resume-1",
      extractedAt: "2025-12-10T15:30:00Z",
      isCurrent: true,
      modelName: "gpt-4",
      modelVersion: "0613",
      promptVersion: "v2.1",
      ageDays: 3,
      relevanceScore: 1.0,
    },
    {
      id: "obs-3",
      fieldName: "skill",
      fieldValue: "AWS Certified Solutions Architect",
      valueType: "string",
      confidence: 0.92,
      confidenceLabel: "Very Likely",
      extractionMethod: "llm",
      sourceDocumentId: "resume-1",
      extractedAt: "2022-03-15T10:00:00Z",
      isCurrent: true,
      modelName: "gpt-4",
      modelVersion: "0613",
      promptVersion: "v1.5",
      ageDays: 1003,
      relevanceScore: 0.75, // 3+ years old certification
    },
    {
      id: "obs-4",
      fieldName: "education_degree",
      fieldValue: "MS Computer Science - Stanford",
      valueType: "string",
      confidence: 0.99,
      confidenceLabel: "Explicit",
      extractionMethod: "llm",
      sourceDocumentId: "resume-1",
      extractedAt: "2025-12-10T15:30:00Z",
      isCurrent: true,
      modelName: "gpt-4",
      modelVersion: "0613",
      promptVersion: "v2.1",
      ageDays: 3,
      relevanceScore: 1.0,
    },
    {
      id: "obs-5",
      fieldName: "years_experience",
      fieldValue: "8",
      valueType: "number",
      confidence: 0.85,
      confidenceLabel: "Very Likely",
      extractionMethod: "llm",
      sourceDocumentId: "resume-1",
      extractedAt: "2025-12-10T15:30:00Z",
      isCurrent: true,
      modelName: "gpt-4",
      modelVersion: "0613",
      promptVersion: "v2.1",
      ageDays: 3,
      relevanceScore: 1.0,
    },
    {
      id: "obs-6",
      fieldName: "skill",
      fieldValue: "Salesforce Certified",
      valueType: "string",
      confidence: 0.88,
      confidenceLabel: "Very Likely",
      extractionMethod: "llm",
      sourceDocumentId: "resume-old",
      extractedAt: "2019-06-01T10:00:00Z",
      isCurrent: true,
      modelName: "gpt-3.5-turbo",
      modelVersion: "0301",
      promptVersion: "v1.0",
      ageDays: 2020,
      relevanceScore: 0.5, // 5+ years old - significantly decayed
    },
    {
      id: "obs-7",
      fieldName: "linkedin_profile",
      fieldValue: "https://linkedin.com/in/janedoe",
      valueType: "string",
      confidence: 0.72,
      confidenceLabel: "Inferred",
      extractionMethod: "external_scrape",
      sourceDocumentId: null,
      sourceUrl: "https://linkedin.com/search/jane+doe+ml+engineer",
      extractedAt: "2025-12-11T10:00:00Z",
      isCurrent: true,
      ageDays: 2,
      relevanceScore: 1.0,
    },
    {
      id: "obs-8",
      fieldName: "github_repos",
      fieldValue: "12 public repos (ML focus)",
      valueType: "string",
      confidence: 0.55,
      confidenceLabel: "Uncertain",
      extractionMethod: "external_scrape",
      sourceDocumentId: null,
      sourceUrl: "https://github.com/janedoe",
      extractedAt: "2025-12-11T10:05:00Z",
      isCurrent: true,
      ageDays: 2,
      relevanceScore: 1.0,
    },
  ],
  "c4-sarah-wilson": [
    {
      id: "obs-s1",
      fieldName: "current_title",
      fieldValue: "Salesforce Architect",
      valueType: "string",
      confidence: 0.97,
      confidenceLabel: "Explicit",
      extractionMethod: "llm",
      sourceDocumentId: "resume-s1",
      extractedAt: "2025-12-13T08:00:00Z",
      isCurrent: true,
      modelName: "gpt-4",
      modelVersion: "0613",
      promptVersion: "v2.1",
      ageDays: 0,
      relevanceScore: 1.0,
    },
    {
      id: "obs-s2",
      fieldName: "skill",
      fieldValue: "Salesforce Admin Certified",
      valueType: "string",
      confidence: 0.95,
      confidenceLabel: "Explicit",
      extractionMethod: "llm",
      sourceDocumentId: "resume-s1",
      extractedAt: "2025-11-01T10:00:00Z",
      isCurrent: true,
      modelName: "gpt-4",
      modelVersion: "0613",
      promptVersion: "v2.1",
      ageDays: 42,
      relevanceScore: 1.0,
    },
    {
      id: "obs-s3",
      fieldName: "skill",
      fieldValue: "Apex Development",
      valueType: "string",
      confidence: 0.93,
      confidenceLabel: "Very Likely",
      extractionMethod: "llm",
      sourceDocumentId: "resume-s1",
      extractedAt: "2025-12-13T08:00:00Z",
      isCurrent: true,
      modelName: "gpt-4",
      modelVersion: "0613",
      promptVersion: "v2.1",
      ageDays: 0,
      relevanceScore: 1.0,
    },
    {
      id: "obs-s4",
      fieldName: "certification_expiry",
      fieldValue: "Salesforce PDI - Expires Mar 2026",
      valueType: "string",
      confidence: 0.65,
      confidenceLabel: "Inferred",
      extractionMethod: "manual",
      sourceDocumentId: null,
      extractedAt: "2025-12-13T09:00:00Z",
      isCurrent: true,
      ageDays: 0,
      relevanceScore: 1.0,
    },
  ],
};

// Mock activity history
export const mockActivityEvents: Record<string, MockActivityEvent[]> = {
  "c1-jane-doe": [
    {
      id: "act-1",
      event_type: "resume_uploaded",
      user_id: "u1",
      user_name: "HR Admin",
      event_data: { file_name: "jane_doe_resume_2025.pdf", source: "upload" },
      created_at: "2025-12-10T15:30:00Z",
    },
    {
      id: "act-2",
      event_type: "profile_viewed",
      user_id: "u2",
      user_name: "Mike Johnson (Recruiter)",
      event_data: {},
      created_at: "2025-12-11T09:15:00Z",
    },
    {
      id: "act-3",
      event_type: "job_match_found",
      user_id: "system",
      user_name: "System",
      event_data: { job_id: "j1", job_title: "Senior ML Engineer", match_score: 0.92 },
      created_at: "2025-12-11T09:20:00Z",
    },
    {
      id: "act-4",
      event_type: "note_added",
      user_id: "u2",
      user_name: "Mike Johnson (Recruiter)",
      event_data: { note: "Strong candidate for ML role, 8 years experience" },
      created_at: "2025-12-11T10:00:00Z",
    },
    {
      id: "act-5",
      event_type: "stage_changed",
      user_id: "u2",
      user_name: "Mike Johnson (Recruiter)",
      event_data: { from_stage: "New", to_stage: "Phone Screen" },
      created_at: "2025-12-12T14:00:00Z",
    },
    {
      id: "act-6",
      event_type: "resume_uploaded",
      user_id: "system",
      user_name: "System",
      event_data: { file_name: "jane_doe_resume_old.pdf", source: "linkedin_import" },
      created_at: "2024-01-15T10:00:00Z",
    },
    {
      id: "act-7",
      event_type: "observation_updated",
      user_id: "system",
      user_name: "System",
      event_data: {
        field: "current_title",
        old_value: "ML Engineer",
        new_value: "Senior ML Engineer",
        delta: "Promoted to Senior level"
      },
      created_at: "2025-12-10T15:35:00Z",
    },
  ],
  "c4-sarah-wilson": [
    {
      id: "act-s1",
      event_type: "application_submitted",
      user_id: "system",
      user_name: "System",
      event_data: { job_id: "j3", job_title: "Salesforce Developer", source: "career_portal" },
      created_at: "2025-10-05T09:00:00Z",
    },
    {
      id: "act-s2",
      event_type: "resume_uploaded",
      user_id: "c4-sarah-wilson",
      user_name: "Sarah Wilson",
      event_data: { file_name: "sarah_wilson_cv.pdf", source: "direct_apply" },
      created_at: "2025-10-05T09:00:00Z",
    },
    {
      id: "act-s3",
      event_type: "job_match_found",
      user_id: "system",
      user_name: "System",
      event_data: { job_id: "j3", job_title: "Salesforce Developer", match_score: 0.88 },
      created_at: "2025-10-05T09:05:00Z",
    },
  ],
};

// Mock resume history
export const mockResumes: Record<string, MockResume[]> = {
  "c1-jane-doe": [
    {
      id: "resume-1",
      file_name: "jane_doe_resume_2025.pdf",
      uploaded_at: "2025-12-10T15:30:00Z",
      source: "upload",
      is_primary: true,
      parsed_data: {
        skills_extracted: ["Python", "ML", "TensorFlow", "AWS"],
        experience_years: 8,
      },
      extraction_status: "completed",
    },
    {
      id: "resume-old",
      file_name: "jane_doe_resume_old.pdf",
      uploaded_at: "2024-01-15T10:00:00Z",
      source: "linkedin_import",
      is_primary: false,
      parsed_data: {
        skills_extracted: ["Python", "ML", "Salesforce"],
        experience_years: 6,
      },
      extraction_status: "completed",
    },
  ],
  "c4-sarah-wilson": [
    {
      id: "resume-s1",
      file_name: "sarah_wilson_cv.pdf",
      uploaded_at: "2025-10-05T09:00:00Z",
      source: "direct_apply",
      is_primary: true,
      parsed_data: {
        skills_extracted: ["Salesforce", "Apex", "LWC"],
        experience_years: 7,
      },
      extraction_status: "completed",
    },
  ],
};

// Mock job matches
export const mockJobMatches: Record<string, MockJobMatch[]> = {
  "c1-jane-doe": [
    {
      job_id: "j1",
      job_title: "Senior ML Engineer",
      department: "Engineering",
      match_score: 0.92,
      match_breakdown: { skills: 0.95, experience: 0.90, location: 0.88 },
      matched_at: "2025-12-11T09:20:00Z",
    },
    {
      job_id: "j2",
      job_title: "AI Research Lead",
      department: "R&D",
      match_score: 0.85,
      match_breakdown: { skills: 0.88, experience: 0.82, location: 0.85 },
      matched_at: "2025-12-11T09:20:00Z",
    },
  ],
  "c4-sarah-wilson": [
    {
      job_id: "j3",
      job_title: "Salesforce Developer",
      department: "IT",
      match_score: 0.88,
      match_breakdown: { skills: 0.92, experience: 0.85, location: 0.90 },
      matched_at: "2025-10-05T09:05:00Z",
    },
  ],
};

// Mock jobs (for two-way matching) - camelCase for API consistency
export const mockJobs: MockJob[] = [
  {
    id: "j1",
    title: "Senior ML Engineer",
    department: "Engineering",
    location: "San Francisco, CA",
    status: "open",
    required_skills: ["Python", "Machine Learning", "TensorFlow", "AWS"],
    min_experience: 5,
    max_experience: 12,
    salary_min: 180000,
    salary_max: 250000,
    created_at: "2025-12-01T10:00:00Z",
    candidate_matches: 3,
  },
  {
    id: "j2",
    title: "AI Research Lead",
    department: "R&D",
    location: "Remote",
    status: "open",
    required_skills: ["Deep Learning", "PyTorch", "Research", "PhD preferred"],
    min_experience: 8,
    max_experience: 15,
    salary_min: 220000,
    salary_max: 300000,
    created_at: "2025-12-05T14:00:00Z",
    candidate_matches: 2,
  },
  {
    id: "j3",
    title: "Salesforce Developer",
    department: "IT",
    location: "Chicago, IL",
    status: "open",
    required_skills: ["Salesforce", "Apex", "LWC", "Integration"],
    min_experience: 4,
    max_experience: 10,
    salary_min: 120000,
    salary_max: 160000,
    created_at: "2025-09-15T08:00:00Z",
    candidate_matches: 5,
  },
  {
    id: "j4",
    title: "Full Stack Engineer",
    department: "Engineering",
    location: "New York, NY",
    status: "open",
    required_skills: ["React", "Node.js", "TypeScript", "PostgreSQL"],
    min_experience: 3,
    max_experience: 8,
    salary_min: 140000,
    salary_max: 200000,
    created_at: "2025-12-10T09:00:00Z",
    candidate_matches: 8,
  },
];

// =============================================================================
// DUPLICATE CANDIDATES (For Merge Review Queue - Sprint R3)
// =============================================================================
export const mockDuplicateCandidates: Record<string, DuplicateCandidate[]> = {
  "c2-john-smith": [
    {
      candidate_id: "c5-johnny-smith",
      candidate_name: "Johnny Smith",
      match_score: 0.92,
      match_type: "strong",
      reasons: [
        { type: "name_similarity", confidence: 0.88, detail: "John Smith ↔ Johnny Smith (Jaro-Winkler: 0.88)" },
        { type: "company_overlap", confidence: 0.95, detail: "Both worked at WebScale Inc (2022-2024)" },
        { type: "resume_similarity", confidence: 0.85, detail: "Embedding cosine similarity: 0.85" },
      ],
    },
  ],
  "c1-jane-doe": [
    {
      candidate_id: "c6-jane-m-doe",
      candidate_name: "Jane M. Doe",
      match_score: 0.98,
      match_type: "hard",
      reasons: [
        { type: "email_match", confidence: 1.0, detail: "Same email: jane.doe@email.com" },
      ],
    },
    {
      candidate_id: "c7-janet-doe",
      candidate_name: "Janet Doe",
      match_score: 0.72,
      match_type: "review",
      reasons: [
        { type: "name_similarity", confidence: 0.65, detail: "Jane Doe ↔ Janet Doe (Jaro-Winkler: 0.65)" },
        { type: "phone_match", confidence: 0.80, detail: "Same phone ending: ***-4567" },
      ],
    },
  ],
};

// =============================================================================
// MATCHING MODEL CONFIGURATION (Read-only in Dashboard, Admin-editable only)
// =============================================================================
export interface MatchingModelConfig {
  modelId: string;
  modelName: string;
  description: string;
  weights: {
    skillsMatch: number;
    experienceMatch: number;
    locationMatch: number;
    educationMatch: number;
    recency: number;
  };
  embeddingModel: string;
  llmRerankModel: string;
  llmRerankTopN: number;
  updatedAt: string;
  updatedBy: string;
}

export const mockMatchingConfig: MatchingModelConfig = {
  modelId: "match-v2.1",
  modelName: "Hybrid Matching Engine v2.1",
  description: "Hard filters → Skill tags → Embeddings → LLM Rerank",
  weights: {
    skillsMatch: 0.40,
    experienceMatch: 0.25,
    locationMatch: 0.15,
    educationMatch: 0.10,
    recency: 0.10,
  },
  embeddingModel: "text-embedding-ada-002",
  llmRerankModel: "gpt-4-turbo",
  llmRerankTopN: 20,
  updatedAt: "2025-12-01T10:00:00Z",
  updatedBy: "System Admin",
};

// Mock alerts for recruiter dashboard
export interface MockAlert {
  id: string;
  type: "new_match" | "new_applicant" | "sla_warning" | "dayforce_sync" | "duplicate_found";
  title: string;
  description: string;
  severity: "info" | "warning" | "critical";
  created_at: string;
  read: boolean;
  entity_id?: string;
  entity_type?: string;
}

export const mockAlerts: MockAlert[] = [
  {
    id: "alert-1",
    type: "new_match",
    title: "New high-match candidate for Senior ML Engineer",
    description: "Jane Doe matches at 92% - strong skills alignment",
    severity: "info",
    created_at: "2025-12-11T09:20:00Z",
    read: false,
    entity_id: "c1-jane-doe",
    entity_type: "candidate",
  },
  {
    id: "alert-2",
    type: "new_applicant",
    title: "New application: Salesforce Developer",
    description: "Sarah Wilson applied via career portal",
    severity: "info",
    created_at: "2025-10-05T09:00:00Z",
    read: true,
    entity_id: "c4-sarah-wilson",
    entity_type: "candidate",
  },
  {
    id: "alert-3",
    type: "dayforce_sync",
    title: "New job opening synced from Dayforce",
    description: "Full Stack Engineer position created",
    severity: "info",
    created_at: "2025-12-10T09:00:00Z",
    read: false,
    entity_id: "j4",
    entity_type: "job",
  },
  {
    id: "alert-4",
    type: "sla_warning",
    title: "SLA Warning: Senior ML Engineer",
    description: "Job has been open for 10 days (SLA: 14 days)",
    severity: "warning",
    created_at: "2025-12-11T08:00:00Z",
    read: false,
    entity_id: "j1",
    entity_type: "job",
  },
  {
    id: "alert-5",
    type: "duplicate_found",
    title: "Potential duplicate candidate detected",
    description: "John Smith may be a duplicate of existing candidate",
    severity: "warning",
    created_at: "2025-12-12T10:00:00Z",
    read: false,
    entity_id: "c2-john-smith",
    entity_type: "candidate",
  },
];

// Helper to format event type for display
export function formatEventType(eventType: string): string {
  const mapping: Record<string, string> = {
    resume_uploaded: "Resume Uploaded",
    profile_viewed: "Profile Viewed",
    job_match_found: "Job Match Found",
    note_added: "Note Added",
    stage_changed: "Stage Changed",
    observation_updated: "Observation Updated",
    application_submitted: "Application Submitted",
    interview_scheduled: "Interview Scheduled",
    offer_extended: "Offer Extended",
    rejected: "Rejected",
  };
  return mapping[eventType] || eventType;
}

// Helper to get event icon class
export function getEventIconClass(eventType: string): string {
  const mapping: Record<string, string> = {
    resume_uploaded: "text-blue-500",
    profile_viewed: "text-gray-500",
    job_match_found: "text-green-500",
    note_added: "text-yellow-500",
    stage_changed: "text-purple-500",
    observation_updated: "text-orange-500",
    application_submitted: "text-blue-500",
  };
  return mapping[eventType] || "text-gray-500";
}
