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
import { ArrowLeft, Plus, Pencil, Trash2, Loader2 } from "lucide-react";
import { api } from "@/lib/api/client";
import { useToast } from "@/hooks/use-toast";

interface ApplicationSource {
  id: string;
  tenant_id: string;
  name: string;
  source_type: string;
  integration_config: Record<string, any>;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

const SOURCE_TYPES = [
  { value: "job_board", label: "Job Board" },
  { value: "referral", label: "Employee Referral" },
  { value: "direct", label: "Direct/Career Site" },
  { value: "agency", label: "Staffing Agency" },
  { value: "social", label: "Social Media" },
  { value: "other", label: "Other" },
];

export default function ApplicationSourcesPage() {
  const { toast } = useToast();
  const [sources, setSources] = useState<ApplicationSource[]>([]);
  const [loading, setLoading] = useState(true);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingSource, setEditingSource] = useState<ApplicationSource | null>(null);
  const [formData, setFormData] = useState({
    name: "",
    source_type: "other",
    is_active: true,
  });
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    fetchSources();
  }, []);

  const fetchSources = async () => {
    try {
      const data = await api.get<ApplicationSource[]>("/api/v1/admin/application-sources");
      setSources(data);
    } catch (error) {
      toast({ title: "Error", description: "Failed to load application sources", variant: "destructive" });
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async () => {
    setSaving(true);
    try {
      if (editingSource) {
        await api.patch(`/api/v1/admin/application-sources/${editingSource.id}`, formData);
        toast({ title: "Success", description: "Source updated successfully" });
      } else {
        await api.post("/api/v1/admin/application-sources", formData);
        toast({ title: "Success", description: "Source created successfully" });
      }
      setDialogOpen(false);
      resetForm();
      fetchSources();
    } catch (error: any) {
      toast({ title: "Error", description: error.message || "Failed to save source", variant: "destructive" });
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (id: string) => {
    if (!confirm("Are you sure you want to delete this source?")) return;
    try {
      await api.delete(`/api/v1/admin/application-sources/${id}`);
      toast({ title: "Success", description: "Source deleted successfully" });
      fetchSources();
    } catch (error: any) {
      toast({ title: "Error", description: error.message || "Failed to delete source", variant: "destructive" });
    }
  };

  const openEditDialog = (source: ApplicationSource) => {
    setEditingSource(source);
    setFormData({
      name: source.name,
      source_type: source.source_type,
      is_active: source.is_active,
    });
    setDialogOpen(true);
  };

  const resetForm = () => {
    setEditingSource(null);
    setFormData({
      name: "",
      source_type: "other",
      is_active: true,
    });
  };

  const getSourceTypeLabel = (type: string) => {
    return SOURCE_TYPES.find(t => t.value === type)?.label || type;
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
          <h1 className="text-3xl font-bold">Application Sources</h1>
          <p className="text-muted-foreground">
            Configure where candidates can apply from
          </p>
        </div>
        <Dialog open={dialogOpen} onOpenChange={(open) => {
          setDialogOpen(open);
          if (!open) resetForm();
        }}>
          <DialogTrigger asChild>
            <Button>
              <Plus className="h-4 w-4 mr-2" />
              New Source
            </Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>
                {editingSource ? "Edit Application Source" : "Create Application Source"}
              </DialogTitle>
              <DialogDescription>
                Configure a source where candidates can submit applications.
              </DialogDescription>
            </DialogHeader>
            <div className="space-y-4 py-4">
              <div className="space-y-2">
                <Label htmlFor="name">Name</Label>
                <Input
                  id="name"
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  placeholder="e.g., LinkedIn, Indeed, Employee Referral"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="source_type">Source Type</Label>
                <Select
                  value={formData.source_type}
                  onValueChange={(value) => setFormData({ ...formData, source_type: value })}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Select type" />
                  </SelectTrigger>
                  <SelectContent>
                    {SOURCE_TYPES.map((type) => (
                      <SelectItem key={type.value} value={type.value}>
                        {type.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
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
            <DialogFooter>
              <Button variant="outline" onClick={() => setDialogOpen(false)}>
                Cancel
              </Button>
              <Button onClick={handleSubmit} disabled={saving || !formData.name}>
                {saving && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
                {editingSource ? "Update" : "Create"}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Sources</CardTitle>
        </CardHeader>
        <CardContent>
          {sources.length === 0 ? (
            <p className="text-center text-muted-foreground py-8">
              No application sources found. Create your first source to get started.
            </p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead>Type</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {sources.map((source) => (
                  <TableRow key={source.id}>
                    <TableCell className="font-medium">{source.name}</TableCell>
                    <TableCell>
                      <Badge variant="outline">
                        {getSourceTypeLabel(source.source_type)}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <Badge variant={source.is_active ? "default" : "secondary"}>
                        {source.is_active ? "Active" : "Inactive"}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-right">
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => openEditDialog(source)}
                      >
                        <Pencil className="h-4 w-4" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => handleDelete(source.id)}
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
