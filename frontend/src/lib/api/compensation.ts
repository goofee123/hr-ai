/**
 * Compensation API Client
 *
 * API client for compensation module endpoints.
 * All data flows through the FastAPI backend for security and audit logging.
 */

import { api } from "./client";

// ============================================================================
// Types
// ============================================================================

export interface CompCycle {
  id: string;
  tenant_id: string;
  name: string;
  description?: string;
  fiscal_year: number;
  cycle_type: "annual" | "mid_year" | "off_cycle";
  scope_type: "company_wide" | "department" | "custom";
  department_ids: string[];
  effective_date: string;
  planning_start_date?: string;
  manager_review_start?: string;
  manager_review_deadline?: string;
  executive_review_deadline?: string;
  status: "draft" | "modeling" | "manager_review" | "executive_review" | "comp_qa" | "approved" | "exported" | "archived";
  overall_budget_percent?: number;
  budget_guidance?: string;
  created_by?: string;
  approved_by?: string;
  approved_at?: string;
  created_at: string;
  updated_at: string;
}

export interface CompCycleCreate {
  name: string;
  description?: string;
  fiscal_year: number;
  cycle_type: "annual" | "mid_year" | "off_cycle";
  scope_type?: "company_wide" | "department" | "custom";
  department_ids?: string[];
  effective_date: string;
  planning_start_date?: string;
  manager_review_start?: string;
  manager_review_deadline?: string;
  executive_review_deadline?: string;
  overall_budget_percent?: number;
  budget_guidance?: string;
}

export interface RuleSet {
  id: string;
  tenant_id: string;
  name: string;
  description?: string;
  is_active: boolean;
  is_default: boolean;
  version: number;
  created_by?: string;
  created_at: string;
  updated_at: string;
}

export interface RuleSetCreate {
  name: string;
  description?: string;
  is_active?: boolean;
  is_default?: boolean;
}

export interface Rule {
  id: string;
  tenant_id: string;
  rule_set_id: string;
  name: string;
  description?: string;
  priority: number;
  is_active: boolean;
  rule_type: "merit" | "bonus" | "promotion" | "minimum_salary" | "cap" | "eligibility";
  conditions: RuleCondition;
  actions: RuleAction;
  effective_date?: string;
  expiry_date?: string;
  created_by?: string;
  created_at: string;
  updated_at: string;
}

export interface RuleCondition {
  logic: "AND" | "OR";
  conditions: Array<{
    field?: string;
    operator?: string;
    value?: unknown;
    logic?: "AND" | "OR";
    conditions?: RuleCondition["conditions"];
  }>;
}

export interface RuleAction {
  action_type: string;
  value?: number;
  value_field?: string;
  value_formula?: string;
  min_value?: number;
  max_value?: number;
  apply_to?: string;
  notes?: string;
}

export interface RuleCreate {
  rule_set_id: string;
  name: string;
  description?: string;
  priority?: number;
  is_active?: boolean;
  rule_type: Rule["rule_type"];
  conditions: RuleCondition;
  actions: RuleAction;
  effective_date?: string;
  expiry_date?: string;
}

export interface Scenario {
  id: string;
  tenant_id: string;
  cycle_id: string;
  name: string;
  description?: string;
  rule_set_id?: string;
  base_merit_percent?: number;
  base_bonus_percent?: number;
  budget_target_percent?: number;
  goal_description?: string;
  status: "draft" | "calculating" | "calculated" | "selected" | "archived";
  calculated_at?: string;
  total_current_payroll?: number;
  total_recommended_increase?: number;
  overall_increase_percent?: number;
  employees_affected?: number;
  is_selected: boolean;
  selected_by?: string;
  selected_at?: string;
  created_by?: string;
  created_at: string;
  updated_at: string;
}

export interface ScenarioCreate {
  name: string;
  description?: string;
  rule_set_id?: string;
  base_merit_percent?: number;
  base_bonus_percent?: number;
  budget_target_percent?: number;
  goal_description?: string;
}

export interface WorksheetEntry {
  id: string;
  tenant_id: string;
  cycle_id: string;
  scenario_id?: string;
  employee_snapshot_id: string;
  employee_id: string;
  first_name: string;
  last_name: string;
  email?: string;
  department?: string;
  job_title?: string;
  current_annual?: number;
  current_compa_ratio?: number;
  performance_score?: number;
  system_raise_percent?: number;
  system_raise_amount?: number;
  system_new_salary?: number;
  system_bonus_percent?: number;
  system_bonus_amount?: number;
  manager_raise_percent?: number;
  manager_raise_amount?: number;
  manager_new_salary?: number;
  manager_bonus_percent?: number;
  manager_bonus_amount?: number;
  manager_promotion_flag: boolean;
  manager_justification?: string;
  manager_exception_flag: boolean;
  delta_raise_percent?: number;
  delta_bonus_amount?: number;
  status: "pending" | "submitted" | "approved" | "rejected" | "flagged";
  submitted_by?: string;
  submitted_at?: string;
  reviewed_by?: string;
  reviewed_at?: string;
  review_notes?: string;
  approved_by?: string;
  approved_at?: string;
  approval_notes?: string;
  highlight_color?: "light_green" | "dark_green" | "beige" | "red";
  created_at: string;
  updated_at: string;
}

export interface WorksheetEntryUpdate {
  manager_raise_percent?: number;
  manager_raise_amount?: number;
  manager_new_salary?: number;
  manager_bonus_percent?: number;
  manager_bonus_amount?: number;
  manager_promotion_flag?: boolean;
  manager_justification?: string;
  manager_exception_flag?: boolean;
  highlight_color?: WorksheetEntry["highlight_color"];
}

export interface WorksheetTotals {
  cycle_id: string;
  department?: string;
  total_employees: number;
  total_current_payroll: number;
  total_system_increase: number;
  total_manager_increase: number;
  overall_percent_increase: number;
  pending_count: number;
  submitted_count: number;
  approved_count: number;
  rejected_count: number;
  flagged_count: number;
}

export interface DatasetVersion {
  id: string;
  tenant_id: string;
  cycle_id?: string;
  version_number: number;
  source: string;
  source_file_name?: string;
  imported_by?: string;
  imported_at: string;
  row_count?: number;
  error_count: number;
  status: "imported" | "validated" | "active" | "archived";
  is_active: boolean;
  notes?: string;
  created_at: string;
}

export interface EmployeeSnapshot {
  id: string;
  tenant_id: string;
  dataset_version_id: string;
  employee_id: string;
  first_name?: string;
  last_name?: string;
  email?: string;
  business_unit?: string;
  department?: string;
  sub_department?: string;
  manager_name?: string;
  manager_employee_id?: string;
  job_title?: string;
  hire_date?: string;
  last_increase_date?: string;
  employment_type?: string;
  schedule?: string;
  weekly_hours?: number;
  location?: string;
  country?: string;
  current_hourly_rate?: number;
  current_weekly?: number;
  current_annual?: number;
  pay_grade?: string;
  band_minimum?: number;
  band_midpoint?: number;
  band_maximum?: number;
  current_compa_ratio?: number;
  performance_score?: number;
  performance_rating?: string;
  prior_year_rate?: number;
  prior_year_increase_pct?: number;
  current_year_rate?: number;
  current_year_increase_pct?: number;
  gbp_eligible: boolean;
  cap_bonus_eligible: boolean;
  prior_year_bonus?: number;
  ytd_total?: number;
  historical_data?: Record<string, unknown>;
  extra_attributes?: Record<string, unknown>;
  created_at: string;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

// ============================================================================
// Cycles API
// ============================================================================

export const cyclesApi = {
  list: (params?: { status?: string; fiscal_year?: number; page?: number; page_size?: number }) => {
    const query = new URLSearchParams();
    if (params?.status) query.append("status", params.status);
    if (params?.fiscal_year) query.append("fiscal_year", params.fiscal_year.toString());
    if (params?.page) query.append("page", params.page.toString());
    if (params?.page_size) query.append("page_size", params.page_size.toString());
    const queryString = query.toString();
    return api.get<PaginatedResponse<CompCycle>>(`/api/v1/compensation/cycles${queryString ? `?${queryString}` : ""}`);
  },

  get: (id: string) => api.get<CompCycle>(`/api/v1/compensation/cycles/${id}`),

  create: (data: CompCycleCreate) => api.post<CompCycle>("/api/v1/compensation/cycles", data),

  update: (id: string, data: Partial<CompCycleCreate>) =>
    api.patch<CompCycle>(`/api/v1/compensation/cycles/${id}`, data),

  delete: (id: string) => api.delete<void>(`/api/v1/compensation/cycles/${id}`),

  launch: (id: string) => api.post<CompCycle>(`/api/v1/compensation/cycles/${id}/launch`),

  finalize: (id: string) => api.post<CompCycle>(`/api/v1/compensation/cycles/${id}/finalize`),
};

// ============================================================================
// Rules API
// ============================================================================

export const rulesApi = {
  listSets: (params?: { is_active?: boolean; page?: number; page_size?: number }) => {
    const query = new URLSearchParams();
    if (params?.is_active !== undefined) query.append("is_active", params.is_active.toString());
    if (params?.page) query.append("page", params.page.toString());
    if (params?.page_size) query.append("page_size", params.page_size.toString());
    const queryString = query.toString();
    return api.get<PaginatedResponse<RuleSet>>(`/api/v1/compensation/rules/sets${queryString ? `?${queryString}` : ""}`);
  },

  getSet: (id: string) => api.get<RuleSet & { rules: Rule[] }>(`/api/v1/compensation/rules/sets/${id}`),

  createSet: (data: RuleSetCreate) => api.post<RuleSet>("/api/v1/compensation/rules/sets", data),

  updateSet: (id: string, data: Partial<RuleSetCreate>) =>
    api.patch<RuleSet>(`/api/v1/compensation/rules/sets/${id}`, data),

  deleteSet: (id: string) => api.delete<void>(`/api/v1/compensation/rules/sets/${id}`),

  createRule: (data: RuleCreate) => api.post<Rule>("/api/v1/compensation/rules", data),

  updateRule: (id: string, data: Partial<RuleCreate>) =>
    api.patch<Rule>(`/api/v1/compensation/rules/${id}`, data),

  deleteRule: (id: string) => api.delete<void>(`/api/v1/compensation/rules/${id}`),

  testRule: (data: { rule: RuleCreate; employee_data: Record<string, unknown> }) =>
    api.post<{ matches: boolean; result: Record<string, unknown> }>("/api/v1/compensation/rules/test", data),
};

// ============================================================================
// Scenarios API
// ============================================================================

export const scenariosApi = {
  list: (cycleId: string) =>
    api.get<Scenario[]>(`/api/v1/compensation/scenarios?cycle_id=${cycleId}`),

  get: (id: string) => api.get<Scenario>(`/api/v1/compensation/scenarios/${id}`),

  create: (cycleId: string, data: ScenarioCreate) =>
    api.post<Scenario>(`/api/v1/compensation/scenarios?cycle_id=${cycleId}`, data),

  update: (id: string, data: Partial<ScenarioCreate>) =>
    api.patch<Scenario>(`/api/v1/compensation/scenarios/${id}`, data),

  delete: (id: string) => api.delete<void>(`/api/v1/compensation/scenarios/${id}`),

  calculate: (id: string) => api.post<Scenario>(`/api/v1/compensation/scenarios/${id}/calculate`),

  select: (id: string) => api.post<Scenario>(`/api/v1/compensation/scenarios/${id}/select`),

  getResults: (id: string, params?: { page?: number; page_size?: number; department?: string }) => {
    const query = new URLSearchParams();
    if (params?.page) query.append("page", params.page.toString());
    if (params?.page_size) query.append("page_size", params.page_size.toString());
    if (params?.department) query.append("department", params.department);
    const queryString = query.toString();
    return api.get<PaginatedResponse<WorksheetEntry>>(`/api/v1/compensation/scenarios/${id}/results${queryString ? `?${queryString}` : ""}`);
  },

  getSummary: (id: string) =>
    api.get<{ total_employees: number; total_payroll: number; total_increase: number; by_department: Record<string, unknown>[] }>(`/api/v1/compensation/scenarios/${id}/summary`),

  compare: (scenarioIds: string[]) =>
    api.get<{ scenarios: Scenario[]; comparison: Record<string, unknown> }>(`/api/v1/compensation/scenarios/compare?ids=${scenarioIds.join(",")}`),
};

// ============================================================================
// Worksheets API
// ============================================================================

export const worksheetsApi = {
  list: (cycleId: string, params?: { status?: string; department?: string; page?: number; page_size?: number }) => {
    const query = new URLSearchParams();
    query.append("cycle_id", cycleId);
    if (params?.status) query.append("status", params.status);
    if (params?.department) query.append("department", params.department);
    if (params?.page) query.append("page", params.page.toString());
    if (params?.page_size) query.append("page_size", params.page_size.toString());
    return api.get<PaginatedResponse<WorksheetEntry>>(`/api/v1/compensation/worksheets?${query.toString()}`);
  },

  getMyTeam: (cycleId: string) =>
    api.get<PaginatedResponse<WorksheetEntry>>(`/api/v1/compensation/worksheets/my-team?cycle_id=${cycleId}`),

  getTotals: (cycleId: string, department?: string) => {
    const query = new URLSearchParams();
    query.append("cycle_id", cycleId);
    if (department) query.append("department", department);
    return api.get<WorksheetTotals>(`/api/v1/compensation/worksheets/totals?${query.toString()}`);
  },

  update: (entryId: string, data: WorksheetEntryUpdate) =>
    api.patch<WorksheetEntry>(`/api/v1/compensation/worksheets/entry/${entryId}`, data),

  bulkUpdate: (entries: Array<{ entry_id: string } & WorksheetEntryUpdate>) =>
    api.post<{ updated_count: number }>("/api/v1/compensation/worksheets/bulk-update", { entries }),

  submit: (cycleId: string, entryIds?: string[]) =>
    api.post<{ submitted_count: number }>("/api/v1/compensation/worksheets/submit", { cycle_id: cycleId, entry_ids: entryIds }),

  review: (entryId: string, action: "approve" | "reject", notes?: string) =>
    api.post<WorksheetEntry>(`/api/v1/compensation/worksheets/entry/${entryId}/review`, { action, notes }),

  bulkReview: (entryIds: string[], action: "approve" | "reject", notes?: string) =>
    api.post<{ processed_count: number }>("/api/v1/compensation/worksheets/bulk-review", { entry_ids: entryIds, action, notes }),
};

// ============================================================================
// Import API
// ============================================================================

export const importApi = {
  validate: (file: File) => api.upload<{ valid: boolean; errors: string[]; preview: Record<string, unknown>[] }>("/api/v1/compensation/import/validate", file),

  importEmployees: (file: File, cycleId?: string) => {
    const url = cycleId ? `/api/v1/compensation/import/employees?cycle_id=${cycleId}` : "/api/v1/compensation/import/employees";
    return api.upload<DatasetVersion>(url, file);
  },

  listVersions: (cycleId: string) =>
    api.get<DatasetVersion[]>(`/api/v1/compensation/import/versions?cycle_id=${cycleId}`),

  activateVersion: (versionId: string) =>
    api.post<DatasetVersion>(`/api/v1/compensation/import/versions/${versionId}/activate`),

  deleteVersion: (versionId: string) =>
    api.delete<void>(`/api/v1/compensation/import/versions/${versionId}`),

  listEmployees: (versionId: string, params?: { page?: number; page_size?: number; department?: string }) => {
    const query = new URLSearchParams();
    query.append("version_id", versionId);
    if (params?.page) query.append("page", params.page.toString());
    if (params?.page_size) query.append("page_size", params.page_size.toString());
    if (params?.department) query.append("department", params.department);
    return api.get<PaginatedResponse<EmployeeSnapshot>>(`/api/v1/compensation/import/employees?${query.toString()}`);
  },

  getDepartments: (versionId: string) =>
    api.get<string[]>(`/api/v1/compensation/import/departments?version_id=${versionId}`),
};
