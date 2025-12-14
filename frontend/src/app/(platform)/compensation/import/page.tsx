"use client";

import { useState, useCallback } from "react";
import Link from "next/link";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  ArrowLeft,
  Upload,
  FileSpreadsheet,
  Loader2,
  CheckCircle,
  XCircle,
  Clock,
  Trash2,
  RotateCcw,
} from "lucide-react";
import { cyclesApi, importApi, type CompCycle, type DatasetVersion } from "@/lib/api/compensation";
import { useToast } from "@/hooks/use-toast";

const statusColors: Record<string, string> = {
  imported: "bg-blue-100 text-blue-800",
  validated: "bg-yellow-100 text-yellow-800",
  active: "bg-green-100 text-green-800",
  archived: "bg-gray-100 text-gray-600",
};

const statusLabels: Record<string, string> = {
  imported: "Imported",
  validated: "Validated",
  active: "Active",
  archived: "Archived",
};

export default function CompensationImportPage() {
  const [selectedCycleId, setSelectedCycleId] = useState<string>("");
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const queryClient = useQueryClient();
  const { toast } = useToast();

  // Fetch cycles
  const { data: cyclesData, isLoading: cyclesLoading } = useQuery({
    queryKey: ["compensation-cycles-for-import"],
    queryFn: () => cyclesApi.list(),
  });

  const cycles = cyclesData?.items || [];

  // Fetch import versions for selected cycle
  const { data: versions, isLoading: versionsLoading } = useQuery({
    queryKey: ["import-versions", selectedCycleId],
    queryFn: () => importApi.listVersions(selectedCycleId),
    enabled: !!selectedCycleId,
  });

  // Import mutation
  const importMutation = useMutation({
    mutationFn: (file: File) => importApi.importEmployees(file, selectedCycleId || undefined),
    onSuccess: (data) => {
      toast({
        title: "Import successful",
        description: `Imported ${data.row_count} employees with ${data.error_count} errors.`,
      });
      queryClient.invalidateQueries({ queryKey: ["import-versions", selectedCycleId] });
      setSelectedFile(null);
    },
    onError: (error: Error) => {
      toast({
        title: "Import failed",
        description: error.message,
        variant: "destructive",
      });
    },
  });

  // Activate version mutation
  const activateMutation = useMutation({
    mutationFn: (versionId: string) => importApi.activateVersion(versionId),
    onSuccess: () => {
      toast({ title: "Version activated" });
      queryClient.invalidateQueries({ queryKey: ["import-versions", selectedCycleId] });
    },
    onError: (error: Error) => {
      toast({
        title: "Failed to activate version",
        description: error.message,
        variant: "destructive",
      });
    },
  });

  // Delete version mutation
  const deleteMutation = useMutation({
    mutationFn: (versionId: string) => importApi.deleteVersion(versionId),
    onSuccess: () => {
      toast({ title: "Version deleted" });
      queryClient.invalidateQueries({ queryKey: ["import-versions", selectedCycleId] });
    },
    onError: (error: Error) => {
      toast({
        title: "Failed to delete version",
        description: error.message,
        variant: "destructive",
      });
    },
  });

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  }, []);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    const file = e.dataTransfer.files[0];
    if (file && (file.name.endsWith(".csv") || file.name.endsWith(".xlsx"))) {
      setSelectedFile(file);
    } else {
      toast({
        title: "Invalid file type",
        description: "Please upload a CSV or Excel file.",
        variant: "destructive",
      });
    }
  }, [toast]);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      setSelectedFile(file);
    }
  };

  const handleImport = () => {
    if (selectedFile) {
      importMutation.mutate(selectedFile);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        <Button variant="ghost" size="icon" asChild>
          <Link href="/compensation">
            <ArrowLeft className="h-4 w-4" />
          </Link>
        </Button>
        <div className="flex-1">
          <h1 className="text-3xl font-bold">Data Import</h1>
          <p className="text-muted-foreground">
            Import employee compensation data from Dayforce or other HR systems
          </p>
        </div>
      </div>

      {/* Cycle Selection */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base">Select Compensation Cycle (Optional)</CardTitle>
          <CardDescription>
            Link this import to a specific cycle, or import without linking
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="w-80">
            <Select value={selectedCycleId} onValueChange={setSelectedCycleId}>
              <SelectTrigger>
                <SelectValue placeholder="Select a cycle (optional)..." />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="none">No cycle (standalone import)</SelectItem>
                {cyclesLoading ? (
                  <SelectItem value="loading" disabled>Loading...</SelectItem>
                ) : (
                  cycles.map((cycle: CompCycle) => (
                    <SelectItem key={cycle.id} value={cycle.id}>
                      {cycle.name} ({cycle.fiscal_year})
                    </SelectItem>
                  ))
                )}
              </SelectContent>
            </Select>
          </div>
        </CardContent>
      </Card>

      {/* Upload Area */}
      <Card>
        <CardHeader>
          <CardTitle>Upload Employee Data</CardTitle>
          <CardDescription>
            Upload a CSV or Excel file with employee compensation data
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div
            className={`border-2 border-dashed rounded-lg p-8 text-center transition-colors ${
              isDragging
                ? "border-primary bg-primary/5"
                : "border-muted-foreground/25 hover:border-muted-foreground/50"
            }`}
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
          >
            {selectedFile ? (
              <div className="space-y-4">
                <FileSpreadsheet className="mx-auto h-12 w-12 text-green-500" />
                <div>
                  <p className="font-medium">{selectedFile.name}</p>
                  <p className="text-sm text-muted-foreground">
                    {(selectedFile.size / 1024).toFixed(1)} KB
                  </p>
                </div>
                <div className="flex justify-center gap-2">
                  <Button
                    variant="outline"
                    onClick={() => setSelectedFile(null)}
                  >
                    Remove
                  </Button>
                  <Button
                    onClick={handleImport}
                    disabled={importMutation.isPending}
                  >
                    {importMutation.isPending ? (
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    ) : (
                      <Upload className="mr-2 h-4 w-4" />
                    )}
                    Import Data
                  </Button>
                </div>
              </div>
            ) : (
              <div className="space-y-4">
                <Upload className="mx-auto h-12 w-12 text-muted-foreground" />
                <div>
                  <p className="font-medium">
                    Drag and drop your file here, or click to browse
                  </p>
                  <p className="text-sm text-muted-foreground">
                    Supports CSV and Excel (.xlsx) files
                  </p>
                </div>
                <div>
                  <Input
                    type="file"
                    accept=".csv,.xlsx"
                    className="hidden"
                    id="file-upload"
                    onChange={handleFileChange}
                  />
                  <Button variant="outline" asChild>
                    <label htmlFor="file-upload" className="cursor-pointer">
                      Browse Files
                    </label>
                  </Button>
                </div>
              </div>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Import History */}
      {selectedCycleId && selectedCycleId !== "none" && (
        <Card>
          <CardHeader>
            <CardTitle>Import History</CardTitle>
            <CardDescription>
              Previous imports for this compensation cycle
            </CardDescription>
          </CardHeader>
          <CardContent>
            {versionsLoading ? (
              <div className="flex items-center justify-center py-8">
                <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
              </div>
            ) : !versions || versions.length === 0 ? (
              <div className="text-center py-8">
                <Clock className="mx-auto h-8 w-8 text-muted-foreground mb-2" />
                <p className="text-muted-foreground">
                  No imports yet for this cycle
                </p>
              </div>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Version</TableHead>
                    <TableHead>Source</TableHead>
                    <TableHead>File</TableHead>
                    <TableHead>Rows</TableHead>
                    <TableHead>Errors</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Imported</TableHead>
                    <TableHead className="w-[100px]">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {versions.map((version: DatasetVersion) => (
                    <TableRow key={version.id}>
                      <TableCell className="font-mono">
                        v{version.version_number}
                      </TableCell>
                      <TableCell>{version.source}</TableCell>
                      <TableCell className="truncate max-w-[150px]">
                        {version.source_file_name || "-"}
                      </TableCell>
                      <TableCell>{version.row_count || 0}</TableCell>
                      <TableCell>
                        {version.error_count > 0 ? (
                          <span className="text-destructive font-medium">
                            {version.error_count}
                          </span>
                        ) : (
                          <CheckCircle className="h-4 w-4 text-green-500" />
                        )}
                      </TableCell>
                      <TableCell>
                        <Badge className={statusColors[version.status]}>
                          {statusLabels[version.status]}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-sm text-muted-foreground">
                        {new Date(version.imported_at).toLocaleDateString()}
                      </TableCell>
                      <TableCell>
                        <div className="flex items-center gap-1">
                          {version.status !== "active" && (
                            <Button
                              variant="ghost"
                              size="icon"
                              className="h-8 w-8"
                              onClick={() => activateMutation.mutate(version.id)}
                              disabled={activateMutation.isPending}
                              title="Activate this version"
                            >
                              <RotateCcw className="h-4 w-4" />
                            </Button>
                          )}
                          <Button
                            variant="ghost"
                            size="icon"
                            className="h-8 w-8 text-destructive"
                            onClick={() => {
                              if (confirm("Delete this import version?")) {
                                deleteMutation.mutate(version.id);
                              }
                            }}
                            disabled={deleteMutation.isPending || version.is_active}
                            title={version.is_active ? "Cannot delete active version" : "Delete version"}
                          >
                            <Trash2 className="h-4 w-4" />
                          </Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </CardContent>
        </Card>
      )}

      {/* Required Columns */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base">Required Columns</CardTitle>
          <CardDescription>
            Your file should include these columns (names are flexible)
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid md:grid-cols-3 gap-6 text-sm">
            <div>
              <h4 className="font-medium mb-2">Employee Identity</h4>
              <ul className="space-y-1 text-muted-foreground">
                <li>Employee ID (required)</li>
                <li>First Name</li>
                <li>Last Name</li>
                <li>Email</li>
              </ul>
            </div>
            <div>
              <h4 className="font-medium mb-2">Organization</h4>
              <ul className="space-y-1 text-muted-foreground">
                <li>Business Unit</li>
                <li>Department</li>
                <li>Manager Name</li>
                <li>Job Title</li>
              </ul>
            </div>
            <div>
              <h4 className="font-medium mb-2">Compensation</h4>
              <ul className="space-y-1 text-muted-foreground">
                <li>Current Hourly Rate / Annual Salary</li>
                <li>Pay Grade</li>
                <li>Band Min/Mid/Max</li>
                <li>Performance Score</li>
              </ul>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Help */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base">Import Sources</CardTitle>
        </CardHeader>
        <CardContent className="text-sm text-muted-foreground">
          <div className="grid md:grid-cols-2 gap-6">
            <div>
              <h4 className="font-medium text-foreground mb-2">Dayforce Export</h4>
              <p>
                Export employee data from Dayforce using the standard Compensation
                Planning report. The system will automatically map columns.
              </p>
            </div>
            <div>
              <h4 className="font-medium text-foreground mb-2">Manual Upload</h4>
              <p>
                Prepare your own spreadsheet following the required columns above.
                Save as CSV or Excel format for best results.
              </p>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
