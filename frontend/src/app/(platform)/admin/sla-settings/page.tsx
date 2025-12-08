"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Badge } from "@/components/ui/badge";
import { ArrowLeft, Plus, Pencil, Trash2, Loader2, Clock } from "lucide-react";
import { api } from "@/lib/api/client";
import { useToast } from "@/hooks/use-toast";

interface SLAConfiguration {
  id: string;
  tenant_id: string;
  name: string;
  job_type: string;
  job_sla_days: number;
  recruiter_sla_days: number;
  amber_threshold_percent: number;
  red_threshold_percent: number;
  is_default: boolean;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

const JOB_TYPES = [
  { value: "standard", label: "Standard" },
  { value: "executive", label: "Executive" },
  { value: "urgent", label: "Urgent" },
  { value: "intern", label: "Intern/Entry Level" },
  { value: "contractor", label: "Contractor" },
];

export default function SLASettingsPage() {
  const { toast } = useToast();
  const [configs, setConfigs] = useState<SLAConfiguration[]>([]);
  const [loading, setLoading] = useState(true);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingConfig, setEditingConfig] = useState<SLAConfiguration | null>(null);
  const [formData, setFormData] = useState({
    name: "",
    job_type: "standard",
    job_sla_days: 30,
    recruiter_sla_days: 14,
    amber_threshold_percent: 75,
    red_threshold_percent: 90,
    is_default: false,
    is_active: true,
  });
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    fetchConfigs();
  }, []);

  const fetchConfigs = async () => {
    try {
      const data = await api.get<SLAConfiguration[]>("/api/v1/admin/sla-configurations");
      setConfigs(data);
    } catch (error) {
      toast({ title: "Error", description: "Failed to load SLA configurations", variant: "destructive" });
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async () => {
    setSaving(true);
    try {
      if (editingConfig) {
        await api.patch(`/api/v1/admin/sla-configurations/${editingConfig.id}`, formData);
        toast({ title: "Success", description: "Configuration updated successfully" });
      } else {
        await api.post("/api/v1/admin/sla-configurations", formData);
        toast({ title: "Success", description: "Configuration created successfully" });
      }
      setDialogOpen(false);
      resetForm();
      fetchConfigs();
    } catch (error: any) {
      toast({ title: "Error", description: error.message || "Failed to save configuration", variant: "destructive" });
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (id: string) => {
    if (!confirm("Are you sure you want to delete this configuration?")) return;
    try {
      await api.delete(`/api/v1/admin/sla-configurations/${id}`);
      toast({ title: "Success", description: "Configuration deleted successfully" });
      fetchConfigs();
    } catch (error: any) {
      toast({ title: "Error", description: error.message || "Failed to delete configuration", variant: "destructive" });
    }
  };

  const openEditDialog = (config: SLAConfiguration) => {
    setEditingConfig(config);
    setFormData({
      name: config.name,
      job_type: config.job_type,
      job_sla_days: config.job_sla_days,
      recruiter_sla_days: config.recruiter_sla_days,
      amber_threshold_percent: config.amber_threshold_percent,
      red_threshold_percent: config.red_threshold_percent,
      is_default: config.is_default,
      is_active: config.is_active,
    });
    setDialogOpen(true);
  };

  const resetForm = () => {
    setEditingConfig(null);
    setFormData({
      name: "",
      job_type: "standard",
      job_sla_days: 30,
      recruiter_sla_days: 14,
      amber_threshold_percent: 75,
      red_threshold_percent: 90,
      is_default: false,
      is_active: true,
    });
  };

  const getJobTypeLabel = (type: string) => {
    return JOB_TYPES.find(t => t.value === type)?.label || type;
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="h-8 w-8 animate-spin" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        <Button variant="ghost" size="icon" asChild>
          <Link href="/admin">
            <ArrowLeft className="h-4 w-4" />
          </Link>
        </Button>
        <div className="flex-1">
          <h1 className="text-3xl font-bold">SLA Settings</h1>
          <p className="text-muted-foreground">
            Configure service level agreements for different job types
          </p>
        </div>
        <Dialog open={dialogOpen} onOpenChange={(open) => {
          setDialogOpen(open);
          if (!open) resetForm();
        }}>
          <DialogTrigger asChild>
            <Button>
              <Plus className="h-4 w-4 mr-2" />
              New Configuration
            </Button>
          </DialogTrigger>
          <DialogContent className="max-w-md">
            <DialogHeader>
              <DialogTitle>
                {editingConfig ? "Edit SLA Configuration" : "Create SLA Configuration"}
              </DialogTitle>
              <DialogDescription>
                Set up SLA thresholds for job openings and recruiter assignments.
              </DialogDescription>
            </DialogHeader>
            <div className="space-y-4 py-4">
              <div className="space-y-2">
                <Label htmlFor="name">Name</Label>
                <Input
                  id="name"
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  placeholder="e.g., Standard Hiring SLA"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="job_type">Job Type</Label>
                <Select
                  value={formData.job_type}
                  onValueChange={(value) => setFormData({ ...formData, job_type: value })}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Select type" />
                  </SelectTrigger>
                  <SelectContent>
                    {JOB_TYPES.map((type) => (
                      <SelectItem key={type.value} value={type.value}>
                        {type.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="job_sla_days">Job SLA (days)</Label>
                  <Input
                    id="job_sla_days"
                    type="number"
                    min="1"
                    max="365"
                    value={formData.job_sla_days}
                    onChange={(e) => setFormData({ ...formData, job_sla_days: parseInt(e.target.value) || 30 })}
                  />
                  <p className="text-xs text-muted-foreground">Time to fill</p>
                </div>
                <div className="space-y-2">
                  <Label htmlFor="recruiter_sla_days">Recruiter SLA (days)</Label>
                  <Input
                    id="recruiter_sla_days"
                    type="number"
                    min="1"
                    max="365"
                    value={formData.recruiter_sla_days}
                    onChange={(e) => setFormData({ ...formData, recruiter_sla_days: parseInt(e.target.value) || 14 })}
                  />
                  <p className="text-xs text-muted-foreground">Time to progress</p>
                </div>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="amber_threshold">Amber Alert (%)</Label>
                  <Input
                    id="amber_threshold"
                    type="number"
                    min="1"
                    max="100"
                    value={formData.amber_threshold_percent}
                    onChange={(e) => setFormData({ ...formData, amber_threshold_percent: parseInt(e.target.value) || 75 })}
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="red_threshold">Red Alert (%)</Label>
                  <Input
                    id="red_threshold"
                    type="number"
                    min="1"
                    max="100"
                    value={formData.red_threshold_percent}
                    onChange={(e) => setFormData({ ...formData, red_threshold_percent: parseInt(e.target.value) || 90 })}
                  />
                </div>
              </div>
              <div className="space-y-3">
                <div className="flex items-center space-x-2">
                  <Switch
                    id="is_default"
                    checked={formData.is_default}
                    onCheckedChange={(checked) => setFormData({ ...formData, is_default: checked })}
                  />
                  <Label htmlFor="is_default">Set as default</Label>
                </div>
                <div className="flex items-center space-x-2">
                  <Switch
                    id="is_active"
                    checked={formData.is_active}
                    onCheckedChange={(checked) => setFormData({ ...formData, is_active: checked })}
                  />
                  <Label htmlFor="is_active">Active</Label>
                </div>
              </div>
            </div>
            <DialogFooter>
              <Button variant="outline" onClick={() => setDialogOpen(false)}>
                Cancel
              </Button>
              <Button onClick={handleSubmit} disabled={saving || !formData.name}>
                {saving && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
                {editingConfig ? "Update" : "Create"}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Configurations</CardTitle>
        </CardHeader>
        <CardContent>
          {configs.length === 0 ? (
            <p className="text-center text-muted-foreground py-8">
              No SLA configurations found. Create your first configuration to get started.
            </p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead>Job Type</TableHead>
                  <TableHead>Job SLA</TableHead>
                  <TableHead>Recruiter SLA</TableHead>
                  <TableHead>Thresholds</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {configs.map((config) => (
                  <TableRow key={config.id}>
                    <TableCell className="font-medium">
                      {config.name}
                      {config.is_default && (
                        <Badge variant="outline" className="ml-2">Default</Badge>
                      )}
                    </TableCell>
                    <TableCell>
                      <Badge variant="outline">
                        {getJobTypeLabel(config.job_type)}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <div className="flex items-center">
                        <Clock className="h-3 w-3 mr-1 text-muted-foreground" />
                        {config.job_sla_days} days
                      </div>
                    </TableCell>
                    <TableCell>
                      <div className="flex items-center">
                        <Clock className="h-3 w-3 mr-1 text-muted-foreground" />
                        {config.recruiter_sla_days} days
                      </div>
                    </TableCell>
                    <TableCell>
                      <div className="flex gap-2">
                        <Badge variant="outline" className="bg-amber-50 text-amber-700 border-amber-200">
                          {config.amber_threshold_percent}%
                        </Badge>
                        <Badge variant="outline" className="bg-red-50 text-red-700 border-red-200">
                          {config.red_threshold_percent}%
                        </Badge>
                      </div>
                    </TableCell>
                    <TableCell>
                      <Badge variant={config.is_active ? "default" : "secondary"}>
                        {config.is_active ? "Active" : "Inactive"}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-right">
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => openEditDialog(config)}
                      >
                        <Pencil className="h-4 w-4" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => handleDelete(config.id)}
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
