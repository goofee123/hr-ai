"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api/client";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Download, AlertTriangle, CheckCircle2, FileText, Shield, Users } from "lucide-react";
import { formatDate } from "@/lib/utils";

interface CategoryBreakdown {
  value: string;
  label: string;
  count: number;
  percentage: number;
}

interface CategorySummary {
  category: string;
  total_responses: number;
  breakdown: CategoryBreakdown[];
}

interface EEOSummaryReport {
  report_date: string;
  date_range_start: string | null;
  date_range_end: string | null;
  total_applications: number;
  total_eeo_responses: number;
  response_rate: number;
  gender_summary: CategorySummary;
  ethnicity_summary: CategorySummary;
  veteran_summary: CategorySummary;
  disability_summary: CategorySummary;
}

interface AdverseImpactAnalysis {
  stage_from: string;
  stage_to: string;
  group_name: string;
  group_applicants: number;
  group_selected: number;
  group_selection_rate: number;
  reference_group: string;
  reference_selection_rate: number;
  impact_ratio: number;
  four_fifths_rule_pass: boolean;
}

interface AdverseImpactReport {
  report_date: string;
  date_range_start: string | null;
  date_range_end: string | null;
  requisition_id: string | null;
  analyses: AdverseImpactAnalysis[];
  warnings: string[];
}

interface AuditLogEntry {
  id: string;
  action_type: string;
  entity_type: string;
  entity_id: string;
  user_id: string;
  action_data: Record<string, unknown>;
  ip_address: string | null;
  created_at: string;
}

interface AuditLogResponse {
  items: AuditLogEntry[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

function CategoryChart({ summary }: { summary: CategorySummary }) {
  const colors = [
    "bg-blue-500",
    "bg-green-500",
    "bg-yellow-500",
    "bg-purple-500",
    "bg-pink-500",
    "bg-indigo-500",
    "bg-orange-500",
    "bg-gray-500",
  ];

  return (
    <div className="space-y-3">
      {summary.breakdown.map((item, index) => (
        <div key={item.value} className="space-y-1">
          <div className="flex justify-between text-sm">
            <span>{item.label}</span>
            <span className="text-muted-foreground">
              {item.count} ({item.percentage.toFixed(1)}%)
            </span>
          </div>
          <Progress
            value={item.percentage}
            className="h-2"
            indicatorClassName={colors[index % colors.length]}
          />
        </div>
      ))}
    </div>
  );
}

export default function EEOReportsPage() {
  const [dateRange, setDateRange] = useState("30");
  const [auditPage, setAuditPage] = useState(1);

  const { data: summaryData, isLoading: summaryLoading } = useQuery({
    queryKey: ["eeo-summary", dateRange],
    queryFn: () =>
      api.get<EEOSummaryReport>(
        `/api/v1/recruiting/eeo/reports/summary?days=${dateRange}`
      ),
  });

  const { data: adverseImpactData, isLoading: adverseLoading } = useQuery({
    queryKey: ["eeo-adverse-impact", dateRange],
    queryFn: () =>
      api.get<AdverseImpactReport>(
        `/api/v1/recruiting/eeo/reports/adverse-impact?days=${dateRange}`
      ),
  });

  const { data: auditData, isLoading: auditLoading } = useQuery({
    queryKey: ["eeo-audit-log", auditPage],
    queryFn: () =>
      api.get<AuditLogResponse>(
        `/api/v1/recruiting/eeo/audit-log?page=${auditPage}&page_size=10`
      ),
  });

  const handleExportOFCCP = async () => {
    try {
      const response = await api.get<{ download_url: string; filename: string }>(
        `/api/v1/recruiting/eeo/reports/ofccp-export?days=${dateRange}`
      );
      // In a real implementation, this would trigger a file download
      alert(`Export generated: ${response.filename}`);
    } catch (error) {
      console.error("Export failed:", error);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">EEO Compliance Reports</h1>
          <p className="text-muted-foreground">
            Equal Employment Opportunity analytics and OFCCP compliance
          </p>
        </div>
        <div className="flex items-center gap-4">
          <Select value={dateRange} onValueChange={setDateRange}>
            <SelectTrigger className="w-[180px]">
              <SelectValue placeholder="Select period" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="30">Last 30 days</SelectItem>
              <SelectItem value="90">Last 90 days</SelectItem>
              <SelectItem value="180">Last 6 months</SelectItem>
              <SelectItem value="365">Last year</SelectItem>
            </SelectContent>
          </Select>
          <Button onClick={handleExportOFCCP}>
            <Download className="mr-2 h-4 w-4" />
            OFCCP Export
          </Button>
        </div>
      </div>

      <Tabs defaultValue="summary" className="space-y-4">
        <TabsList>
          <TabsTrigger value="summary">
            <Users className="mr-2 h-4 w-4" />
            Summary
          </TabsTrigger>
          <TabsTrigger value="adverse-impact">
            <AlertTriangle className="mr-2 h-4 w-4" />
            Adverse Impact
          </TabsTrigger>
          <TabsTrigger value="audit">
            <Shield className="mr-2 h-4 w-4" />
            Audit Trail
          </TabsTrigger>
        </TabsList>

        <TabsContent value="summary" className="space-y-4">
          {summaryLoading ? (
            <div className="flex justify-center py-8">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary" />
            </div>
          ) : summaryData ? (
            <>
              <div className="grid gap-4 md:grid-cols-3">
                <Card>
                  <CardHeader className="pb-2">
                    <CardTitle className="text-sm font-medium text-muted-foreground">
                      Total Applications
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="text-2xl font-bold">
                      {summaryData.total_applications}
                    </div>
                  </CardContent>
                </Card>
                <Card>
                  <CardHeader className="pb-2">
                    <CardTitle className="text-sm font-medium text-muted-foreground">
                      EEO Responses
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="text-2xl font-bold">
                      {summaryData.total_eeo_responses}
                    </div>
                  </CardContent>
                </Card>
                <Card>
                  <CardHeader className="pb-2">
                    <CardTitle className="text-sm font-medium text-muted-foreground">
                      Response Rate
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="text-2xl font-bold">
                      {(summaryData.response_rate * 100).toFixed(1)}%
                    </div>
                    <Progress
                      value={summaryData.response_rate * 100}
                      className="mt-2 h-2"
                    />
                  </CardContent>
                </Card>
              </div>

              <div className="grid gap-4 md:grid-cols-2">
                <Card>
                  <CardHeader>
                    <CardTitle>Gender Distribution</CardTitle>
                    <CardDescription>
                      Self-identified gender of applicants
                    </CardDescription>
                  </CardHeader>
                  <CardContent>
                    <CategoryChart summary={summaryData.gender_summary} />
                  </CardContent>
                </Card>
                <Card>
                  <CardHeader>
                    <CardTitle>Race/Ethnicity Distribution</CardTitle>
                    <CardDescription>
                      Self-identified race/ethnicity of applicants
                    </CardDescription>
                  </CardHeader>
                  <CardContent>
                    <CategoryChart summary={summaryData.ethnicity_summary} />
                  </CardContent>
                </Card>
                <Card>
                  <CardHeader>
                    <CardTitle>Veteran Status</CardTitle>
                    <CardDescription>
                      Self-identified veteran status
                    </CardDescription>
                  </CardHeader>
                  <CardContent>
                    <CategoryChart summary={summaryData.veteran_summary} />
                  </CardContent>
                </Card>
                <Card>
                  <CardHeader>
                    <CardTitle>Disability Status</CardTitle>
                    <CardDescription>
                      Self-identified disability status
                    </CardDescription>
                  </CardHeader>
                  <CardContent>
                    <CategoryChart summary={summaryData.disability_summary} />
                  </CardContent>
                </Card>
              </div>

              <Alert>
                <FileText className="h-4 w-4" />
                <AlertTitle>Privacy Notice</AlertTitle>
                <AlertDescription>
                  EEO data is collected on a voluntary basis and stored separately from
                  application data. Individual responses are never visible during the
                  candidate evaluation process. This report shows aggregate statistics only.
                </AlertDescription>
              </Alert>
            </>
          ) : (
            <Card>
              <CardContent className="py-8 text-center">
                <p className="text-muted-foreground">No EEO data available</p>
              </CardContent>
            </Card>
          )}
        </TabsContent>

        <TabsContent value="adverse-impact" className="space-y-4">
          {adverseLoading ? (
            <div className="flex justify-center py-8">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary" />
            </div>
          ) : adverseImpactData ? (
            <>
              {adverseImpactData.warnings.length > 0 && (
                <Alert variant="destructive">
                  <AlertTriangle className="h-4 w-4" />
                  <AlertTitle>Potential Adverse Impact Detected</AlertTitle>
                  <AlertDescription>
                    <ul className="mt-2 list-disc pl-4">
                      {adverseImpactData.warnings.map((warning, index) => (
                        <li key={index}>{warning}</li>
                      ))}
                    </ul>
                  </AlertDescription>
                </Alert>
              )}

              <Card>
                <CardHeader>
                  <CardTitle>Four-Fifths Rule Analysis</CardTitle>
                  <CardDescription>
                    Comparing selection rates across demographic groups. A ratio below 0.8
                    (80%) may indicate potential adverse impact under the EEOC guidelines.
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  {adverseImpactData.analyses.length > 0 ? (
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead>Stage Transition</TableHead>
                          <TableHead>Group</TableHead>
                          <TableHead className="text-right">Applicants</TableHead>
                          <TableHead className="text-right">Selected</TableHead>
                          <TableHead className="text-right">Rate</TableHead>
                          <TableHead className="text-right">Impact Ratio</TableHead>
                          <TableHead className="text-center">Status</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {adverseImpactData.analyses.map((analysis, index) => (
                          <TableRow key={index}>
                            <TableCell>
                              {analysis.stage_from} → {analysis.stage_to}
                            </TableCell>
                            <TableCell>{analysis.group_name}</TableCell>
                            <TableCell className="text-right">
                              {analysis.group_applicants}
                            </TableCell>
                            <TableCell className="text-right">
                              {analysis.group_selected}
                            </TableCell>
                            <TableCell className="text-right">
                              {(analysis.group_selection_rate * 100).toFixed(1)}%
                            </TableCell>
                            <TableCell className="text-right">
                              {(analysis.impact_ratio * 100).toFixed(1)}%
                            </TableCell>
                            <TableCell className="text-center">
                              {analysis.four_fifths_rule_pass ? (
                                <Badge variant="outline" className="bg-green-50 text-green-700">
                                  <CheckCircle2 className="mr-1 h-3 w-3" />
                                  Pass
                                </Badge>
                              ) : (
                                <Badge variant="destructive">
                                  <AlertTriangle className="mr-1 h-3 w-3" />
                                  Review
                                </Badge>
                              )}
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  ) : (
                    <p className="text-center text-muted-foreground py-4">
                      Insufficient data for adverse impact analysis. More applications
                      are needed across demographic groups.
                    </p>
                  )}
                </CardContent>
              </Card>

              <Alert>
                <Shield className="h-4 w-4" />
                <AlertTitle>About the Four-Fifths Rule</AlertTitle>
                <AlertDescription>
                  Under EEOC guidelines, a selection rate for any protected group that is
                  less than 80% (four-fifths) of the rate for the group with the highest
                  rate may be evidence of adverse impact. However, this is not conclusive
                  proof of discrimination and should be investigated further.
                </AlertDescription>
              </Alert>
            </>
          ) : (
            <Card>
              <CardContent className="py-8 text-center">
                <p className="text-muted-foreground">No adverse impact data available</p>
              </CardContent>
            </Card>
          )}
        </TabsContent>

        <TabsContent value="audit" className="space-y-4">
          {auditLoading ? (
            <div className="flex justify-center py-8">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary" />
            </div>
          ) : auditData ? (
            <>
              <Card>
                <CardHeader>
                  <CardTitle>Compliance Audit Trail</CardTitle>
                  <CardDescription>
                    All compliance-relevant actions are logged for OFCCP auditing
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Timestamp</TableHead>
                        <TableHead>Action</TableHead>
                        <TableHead>Entity</TableHead>
                        <TableHead>IP Address</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {auditData.items.map((entry) => (
                        <TableRow key={entry.id}>
                          <TableCell className="whitespace-nowrap">
                            {formatDate(entry.created_at)}
                          </TableCell>
                          <TableCell>
                            <Badge variant="outline">
                              {entry.action_type.replace(/_/g, " ")}
                            </Badge>
                          </TableCell>
                          <TableCell>
                            {entry.entity_type}
                            {entry.entity_id && (
                              <span className="text-muted-foreground ml-1">
                                ({entry.entity_id.slice(0, 8)}...)
                              </span>
                            )}
                          </TableCell>
                          <TableCell className="text-muted-foreground">
                            {entry.ip_address || "N/A"}
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </CardContent>
              </Card>

              {auditData.total_pages > 1 && (
                <div className="flex justify-center gap-2">
                  <Button
                    variant="outline"
                    onClick={() => setAuditPage((p) => Math.max(1, p - 1))}
                    disabled={auditPage === 1}
                  >
                    Previous
                  </Button>
                  <span className="flex items-center px-4 text-sm">
                    Page {auditPage} of {auditData.total_pages}
                  </span>
                  <Button
                    variant="outline"
                    onClick={() => setAuditPage((p) => p + 1)}
                    disabled={auditPage >= auditData.total_pages}
                  >
                    Next
                  </Button>
                </div>
              )}
            </>
          ) : (
            <Card>
              <CardContent className="py-8 text-center">
                <p className="text-muted-foreground">No audit log entries found</p>
              </CardContent>
            </Card>
          )}
        </TabsContent>
      </Tabs>
    </div>
  );
}
