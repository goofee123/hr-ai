/**
 * Recruiting Module API Types - OFFICIAL API CONTRACT
 *
 * These types define the shape of data exchanged between frontend and backend.
 * Backend MUST implement these exact shapes.
 *
 * IMPORTANT: This file is the source of truth for API contracts.
 * - Do not modify without coordinating with backend team
 * - All field names use camelCase for JSON serialization
 * - All timestamps use ISO 8601 format
 */

// =============================================================================
// CONFIDENCE INTERPRETATION
// =============================================================================

/**
 * Human-readable confidence labels.
 * Recruiters think in words, not numbers.
 */
export type ConfidenceLabel = "Explicit" | "Very Likely" | "Inferred" | "Uncertain";

/**
 * Map numeric confidence to label.
 * - Explicit: 0.95+ (explicitly stated in document)
 * - Very Likely: 0.80-0.94 (clearly implied or standard format)
 * - Inferred: 0.65-0.79 (inferred from context)
 * - Uncertain: <0.65 (may need verification)
 */
export function getConfidenceLabel(confidence: number): ConfidenceLabel {
  if (confidence >= 0.95) return "Explicit";
  if (confidence >= 0.80) return "Very Likely";
  if (confidence >= 0.65) return "Inferred";
  return "Uncertain";
}

/**
 * Tailwind CSS classes for confidence badges.
 */
export function getConfidenceLabelColor(label: ConfidenceLabel): string {
  switch (label) {
    case "Explicit": return "bg-green-100 text-green-800 border-green-200";
    case "Very Likely": return "bg-blue-100 text-blue-800 border-blue-200";
    case "Inferred": return "bg-yellow-100 text-yellow-800 border-yellow-200";
    case "Uncertain": return "bg-red-100 text-red-800 border-red-200";
  }
}

// =============================================================================
// EXTRACTION & SOURCE TYPES
// =============================================================================

/**
 * Method used to extract data.
 */
export type ExtractionMethod =
  | "llm"             // LLM extraction from resume
  | "manual"          // Human-entered data
  | "linkedin"        // LinkedIn import
  | "form"            // Application form submission
  | "external_scrape" // External enrichment (best-effort)
  | "system";         // System-generated

// =============================================================================
// DUPLICATE DETECTION TYPES
// =============================================================================

/**
 * Reasons why candidates might be duplicates.
 * Always show WHY to the user.
 */
export type DuplicateMatchReason =
  | "email_match"           // Same email address (hard match)
  | "linkedin_match"        // Same LinkedIn URL (hard match)
  | "name_similarity"       // Similar name (fuzzy)
  | "resume_similarity"     // High embedding similarity
  | "company_overlap"       // Worked at same company + similar timeline
  | "phone_match";          // Same phone number

/**
 * Duplicate candidate detection result.
 */
export interface DuplicateCandidate {
  candidateId: string;
  candidateName: string;
  matchScore: number;  // 0.0-1.0
  matchType: "hard" | "strong" | "fuzzy" | "review";
  reasons: DuplicateMatchReason_[];
}

/**
 * Individual reason for duplicate match.
 */
export interface DuplicateMatchReason_ {
  type: DuplicateMatchReason;
  confidence: number;
  detail?: string;  // e.g., "Worked at TechCorp 2020-2023"
}

// =============================================================================
// CANDIDATE DTOs
// =============================================================================

/**
 * Candidate entity - the core recruiting unit.
 * A candidate is an ENTITY with documents and observations.
 */
export interface CandidateDTO {
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
  createdAt: string;  // ISO 8601
  updatedAt: string;  // ISO 8601
}

/**
 * Candidate list response (paginated).
 */
export interface CandidateListResponse {
  items: CandidateDTO[];
  total: number;
  page: number;
  pageSize: number;
  totalPages: number;
}

/**
 * Candidate detail response with full data.
 */
export interface CandidateDetailResponse extends CandidateDTO {
  observations: ObservationDTO[];
  resumes: ResumeDTO[];
  activityEvents: ActivityEventDTO[];
  jobMatches: JobMatchDTO[];
  duplicateCandidates?: DuplicateCandidate[];
}

// =============================================================================
// OBSERVATION DTOs (Fact-based extraction)
// =============================================================================

/**
 * Observation - a fact about a candidate with provenance.
 * Every piece of data has a confidence score and source.
 */
export interface ObservationDTO {
  id: string;
  fieldName: string;
  fieldValue: string;
  valueType: "string" | "number" | "date" | "array";
  confidence: number;  // 0.0-1.0
  confidenceLabel: ConfidenceLabel;  // Derived
  extractionMethod: ExtractionMethod;
  sourceDocumentId: string | null;
  sourceUrl?: string;  // For external scrape
  extractedAt: string;  // ISO 8601
  isCurrent: boolean;
  // Model provenance (critical for debugging & legal)
  modelName?: string;      // e.g., "gpt-4"
  modelVersion?: string;   // e.g., "0613"
  promptVersion?: string;  // e.g., "v2.1"
  // Relevance decay
  ageDays: number;
  relevanceScore: number;  // 0.0-1.0
}

/**
 * Create observation request.
 */
export interface CreateObservationRequest {
  candidateId: string;
  fieldName: string;
  fieldValue: string;
  valueType: "string" | "number" | "date" | "array";
  confidence?: number;
  extractionMethod: ExtractionMethod;
  sourceDocumentId?: string;
}

// =============================================================================
// ACTIVITY EVENT DTOs
// =============================================================================

/**
 * Activity event - tracks recruiter engagement.
 */
export interface ActivityEventDTO {
  id: string;
  eventType: string;
  userId: string;
  userName: string;
  eventData: Record<string, unknown>;
  createdAt: string;  // ISO 8601
}

/**
 * Event types for activity tracking.
 */
export type ActivityEventType =
  | "resume_uploaded"
  | "profile_viewed"
  | "job_match_found"
  | "note_added"
  | "stage_changed"
  | "observation_updated"
  | "application_submitted"
  | "interview_scheduled"
  | "offer_extended"
  | "rejected";

// =============================================================================
// RESUME DTOs
// =============================================================================

/**
 * Resume document.
 */
export interface ResumeDTO {
  id: string;
  fileName: string;
  uploadedAt: string;  // ISO 8601
  source: string;
  isPrimary: boolean;
  parsedData: Record<string, unknown>;
  extractionStatus: "pending" | "processing" | "completed" | "failed";
}

/**
 * Resume upload request.
 */
export interface UploadResumeRequest {
  candidateId: string;
  file: File;
  isPrimary?: boolean;
  source?: string;
}

// =============================================================================
// JOB MATCHING DTOs
// =============================================================================

/**
 * Job match result.
 */
export interface JobMatchDTO {
  jobId: string;
  jobTitle: string;
  department: string;
  matchScore: number;  // 0.0-1.0
  matchBreakdown: MatchBreakdown;
  matchedAt: string;  // ISO 8601
}

/**
 * Match breakdown by category.
 */
export interface MatchBreakdown {
  skills: number;     // 0.0-1.0
  experience: number; // 0.0-1.0
  location: number;   // 0.0-1.0
}

/**
 * Job for matching.
 */
export interface JobDTO {
  id: string;
  title: string;
  department: string;
  location: string;
  status: "open" | "closed" | "on_hold";
  requiredSkills: string[];
  minExperience: number;
  maxExperience: number;
  salaryMin: number;
  salaryMax: number;
  createdAt: string;  // ISO 8601
  candidateMatches: number;
}

// =============================================================================
// MATCHING MODEL CONFIGURATION
// =============================================================================

/**
 * Matching model configuration.
 * Read-only for recruiters, admin-editable only.
 */
export interface MatchingModelConfig {
  modelId: string;
  modelName: string;
  description: string;
  weights: MatchingWeights;
  embeddingModel: string;
  llmRerankModel: string;
  llmRerankTopN: number;
  updatedAt: string;  // ISO 8601
  updatedBy: string;
}

/**
 * Matching weights (sum should be 1.0).
 */
export interface MatchingWeights {
  skillsMatch: number;
  experienceMatch: number;
  locationMatch: number;
  educationMatch: number;
  recency: number;
}

// =============================================================================
// MERGE QUEUE DTOs
// =============================================================================

/**
 * Merge queue item for duplicate review.
 */
export interface MergeQueueItem {
  id: string;
  primaryCandidateId: string;
  duplicateCandidateId: string;
  matchScore: number;
  matchType: "hard" | "strong" | "fuzzy" | "review";
  reasons: DuplicateMatchReason_[];
  status: "pending" | "merged" | "rejected" | "deferred";
  createdAt: string;  // ISO 8601
  reviewedAt?: string;
  reviewedBy?: string;
}

/**
 * Merge request.
 */
export interface MergeCandidatesRequest {
  primaryCandidateId: string;
  duplicateCandidateId: string;
  mergeQueueItemId?: string;
}

/**
 * Reject duplicate request.
 */
export interface RejectDuplicateRequest {
  mergeQueueItemId: string;
  reason?: string;
}

// =============================================================================
// ALERTS & NOTIFICATIONS
// =============================================================================

/**
 * Recruiter alert.
 */
export interface AlertDTO {
  id: string;
  type: "new_match" | "new_applicant" | "sla_warning" | "dayforce_sync" | "duplicate_found";
  title: string;
  description: string;
  severity: "info" | "warning" | "critical";
  createdAt: string;  // ISO 8601
  read: boolean;
  entityId?: string;
  entityType?: string;
}

// =============================================================================
// HELPER FUNCTIONS
// =============================================================================

/**
 * Calculate relevance score based on extraction age.
 * Skills/certifications decay over time.
 */
export function calculateRelevanceScore(extractedAt: string): number {
  const now = new Date();
  const extracted = new Date(extractedAt);
  const ageYears = (now.getTime() - extracted.getTime()) / (1000 * 60 * 60 * 24 * 365);

  // 0-1 year: 100%, 1-3 years: 90%, 3-5 years: 75%, 5+ years: 50%
  if (ageYears < 1) return 1.0;
  if (ageYears < 3) return 0.9;
  if (ageYears < 5) return 0.75;
  return 0.5;
}

/**
 * Get relevance decay label.
 */
export function getRelevanceDecayLabel(score: number): string {
  if (score >= 1.0) return "Current";
  if (score >= 0.9) return "Recent";
  if (score >= 0.75) return "Aging";
  return "Outdated";
}

/**
 * Format event type for display.
 */
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

/**
 * Get event icon class (Tailwind).
 */
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
