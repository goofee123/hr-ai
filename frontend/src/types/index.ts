// Common types
export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

// User types
export interface User {
  id: string;
  email: string;
  full_name: string;
  role: UserRole;
  department_id?: string;
  is_active: boolean;
  created_at: string;
}

export type UserRole =
  | "super_admin"
  | "hr_admin"
  | "recruiter"
  | "hiring_manager"
  | "executive"
  | "payroll"
  | "manager"
  | "employee";

// Organization types
export interface Department {
  id: string;
  name: string;
  code: string;
  parent_id?: string;
}

export interface Location {
  id: string;
  name: string;
  city: string;
  state?: string;
  country: string;
}

// Recruiting types
export interface JobRequisition {
  id: string;
  tenant_id: string;
  requisition_number: string;
  external_title: string;
  internal_title?: string;
  job_description?: string;
  requirements?: string;
  department_id?: string;
  location_id?: string;
  status: RequisitionStatus;
  positions_approved: number;
  positions_filled: number;
  worker_type: WorkerType;
  salary_min?: number;
  salary_max?: number;
  is_salary_visible: boolean;
  hiring_manager_id?: string;
  primary_recruiter_id?: string;
  target_fill_date?: string;
  sla_days: number;
  opened_at?: string;
  closed_at?: string;
  created_at: string;
  updated_at?: string;
}

export type RequisitionStatus =
  | "draft"
  | "pending_approval"
  | "open"
  | "on_hold"
  | "closed_filled"
  | "closed_cancelled";

export type WorkerType = "full_time" | "part_time" | "contractor" | "intern" | "temporary";

export interface Candidate {
  id: string;
  tenant_id: string;
  first_name: string;
  last_name: string;
  email: string;
  phone?: string;
  source?: string;
  source_details?: string;
  linkedin_url?: string;
  portfolio_url?: string;
  skills: string[];
  tags: string[];
  notes?: string;
  created_at: string;
  updated_at?: string;
}

export interface Application {
  id: string;
  tenant_id: string;
  candidate_id: string;
  requisition_id: string;
  status: ApplicationStatus;
  current_stage: string;
  current_stage_id?: string;
  stage_entered_at: string;
  resume_id?: string;
  cover_letter?: string;
  screening_answers: Record<string, unknown>;
  recruiter_rating?: number;
  hiring_manager_rating?: number;
  overall_score?: number;
  rejection_reason?: string;
  rejection_notes?: string;
  assigned_recruiter_id?: string;
  applied_at: string;
  last_activity_at: string;
  created_at: string;
}

export type ApplicationStatus = "active" | "rejected" | "withdrawn" | "hired";

export interface PipelineStage {
  id: string;
  name: string;
  stage_type: string;
  sort_order: number;
  is_rejection_stage: boolean;
  requires_feedback: boolean;
  interview_required: boolean;
  candidate_count: number;
}

export interface PipelineCandidate {
  application_id: string;
  candidate_id: string;
  candidate_name: string;
  candidate_email: string;
  current_stage: string;
  stage_entered_at: string;
  applied_at: string;
  source?: string;
  recruiter_rating?: number;
  hiring_manager_rating?: number;
  days_in_stage: number;
}

export interface Pipeline {
  requisition_id: string;
  requisition_number: string;
  external_title: string;
  total_candidates: number;
  stages: Array<PipelineStage & { candidates: PipelineCandidate[] }>;
}

export interface RecruiterTask {
  id: string;
  tenant_id: string;
  task_type: string;
  title: string;
  description?: string;
  due_date?: string;
  priority: "low" | "normal" | "high" | "urgent";
  application_id?: string;
  requisition_id?: string;
  candidate_id?: string;
  assigned_to?: string;
  status: "pending" | "in_progress" | "completed";
  completed_at?: string;
  completed_by?: string;
  reminder_sent: boolean;
  created_at: string;
}

// Resume types
export interface Resume {
  id: string;
  candidate_id: string;
  file_name: string;
  file_path: string;
  file_size_bytes: number;
  mime_type: string;
  version_number: number;
  is_primary: boolean;
  parsing_status: "pending" | "processing" | "completed" | "failed";
  parsed_data?: Record<string, unknown>;
  created_at: string;
}
