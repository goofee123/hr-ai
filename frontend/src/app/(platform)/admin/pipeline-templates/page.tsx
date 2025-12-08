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
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Switch } from "@/components/ui/switch";
import { Badge } from "@/components/ui/badge";
import { ArrowLeft, Plus, Pencil, Trash2, Loader2 } from "lucide-react";
import { api } from "@/lib/api/client";
import { useToast } from "@/hooks/use-toast";

interface PipelineStage {
  name: string;
  stage_type: string;
  sort_order: number;
  is_rejection_stage?: boolean;
  requires_feedback?: boolean;
  interview_required?: boolean;
}

interface PipelineTemplate {
  id: string;
  tenant_id: string;
  name: string;
  description: string | null;
  is_default: boolean;
  stages: PipelineStage[];
  created_at: string;
  updated_at: string;
}

export default function PipelineTemplatesPage() {
  const { toast } = useToast();
  const [templates, setTemplates] = useState<PipelineTemplate[]>([]);
  const [loading, setLoading] = useState(true);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingTemplate, setEditingTemplate] = useState<PipelineTemplate | null>(null);
  const [formData, setFormData] = useState({
    name: "",
    description: "",
    is_default: false,
  });
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    fetchTemplates();
  }, []);

  const fetchTemplates = async () => {
    try {
      const data = await api.get<PipelineTemplate[]>("/api/v1/admin/pipeline-templates");
      setTemplates(data);
    } catch (error) {
      toast({ title: "Error", description: "Failed to load pipeline templates", variant: "destructive" });
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async () => {
    setSaving(true);
    try {
      if (editingTemplate) {
        await api.patch(`/api/v1/admin/pipeline-templates/${editingTemplate.id}`, formData);
        toast({ title: "Success", description: "Template updated successfully" });
      } else {
        await api.post("/api/v1/admin/pipeline-templates", {
          ...formData,
          stages: [
            { name: "Applied", stage_type: "initial", sort_order: 1 },
            { name: "Screening", stage_type: "screen", sort_order: 2 },
            { name: "Interview", stage_type: "interview", sort_order: 3, interview_required: true },
            { name: "Offer", stage_type: "offer", sort_order: 4 },
            { name: "Hired", stage_type: "hired", sort_order: 5 },
          ],
        });
        toast({ title: "Success", description: "Template created successfully" });
      }
      setDialogOpen(false);
      resetForm();
      fetchTemplates();
    } catch (error: any) {
      toast({ title: "Error", description: error.message || "Failed to save template", variant: "destructive" });
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (id: string) => {
    if (!confirm("Are you sure you want to delete this template?")) return;
    try {
      await api.delete(`/api/v1/admin/pipeline-templates/${id}`);
      toast({ title: "Success", description: "Template deleted successfully" });
      fetchTemplates();
    } catch (error: any) {
      toast({ title: "Error", description: error.message || "Failed to delete template", variant: "destructive" });
    }
  };

  const openEditDialog = (template: PipelineTemplate) => {
    setEditingTemplate(template);
    setFormData({
      name: template.name,
      description: template.description || "",
      is_default: template.is_default,
    });
    setDialogOpen(true);
  };

  const resetForm = () => {
    setEditingTemplate(null);
    setFormData({ name: "", description: "", is_default: false });
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
          <h1 className="text-3xl font-bold">Pipeline Templates</h1>
          <p className="text-muted-foreground">
            Configure hiring workflow stages and templates
          </p>
        </div>
        <Dialog open={dialogOpen} onOpenChange={(open) => {
          setDialogOpen(open);
          if (!open) resetForm();
        }}>
          <DialogTrigger asChild>
            <Button>
              <Plus className="h-4 w-4 mr-2" />
              New Template
            </Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>
                {editingTemplate ? "Edit Template" : "Create Pipeline Template"}
              </DialogTitle>
              <DialogDescription>
                {editingTemplate
                  ? "Update the template details below."
                  : "Create a new pipeline template with default stages. You can customize stages after creation."}
              </DialogDescription>
            </DialogHeader>
            <div className="space-y-4 py-4">
              <div className="space-y-2">
                <Label htmlFor="name">Name</Label>
                <Input
                  id="name"
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  placeholder="e.g., Standard Hiring Pipeline"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="description">Description</Label>
                <Textarea
                  id="description"
                  value={formData.description}
                  onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                  placeholder="Describe when this template should be used..."
                />
              </div>
              <div className="flex items-center space-x-2">
                <Switch
                  id="is_default"
                  checked={formData.is_default}
                  onCheckedChange={(checked) => setFormData({ ...formData, is_default: checked })}
                />
                <Label htmlFor="is_default">Set as default template</Label>
              </div>
            </div>
            <DialogFooter>
              <Button variant="outline" onClick={() => setDialogOpen(false)}>
                Cancel
              </Button>
              <Button onClick={handleSubmit} disabled={saving || !formData.name}>
                {saving && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
                {editingTemplate ? "Update" : "Create"}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Templates</CardTitle>
        </CardHeader>
        <CardContent>
          {templates.length === 0 ? (
            <p className="text-center text-muted-foreground py-8">
              No pipeline templates found. Create your first template to get started.
            </p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead>Description</TableHead>
                  <TableHead>Stages</TableHead>
                  <TableHead>Default</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {templates.map((template) => (
                  <TableRow key={template.id}>
                    <TableCell className="font-medium">{template.name}</TableCell>
                    <TableCell className="max-w-xs truncate">
                      {template.description || "-"}
                    </TableCell>
                    <TableCell>
                      <div className="flex flex-wrap gap-1">
                        {template.stages?.slice(0, 3).map((stage, i) => (
                          <Badge key={i} variant="outline" className="text-xs">
                            {stage.name}
                          </Badge>
                        ))}
                        {template.stages?.length > 3 && (
                          <Badge variant="outline" className="text-xs">
                            +{template.stages.length - 3} more
                          </Badge>
                        )}
                      </div>
                    </TableCell>
                    <TableCell>
                      {template.is_default ? (
                        <Badge variant="default">Default</Badge>
                      ) : (
                        <span className="text-muted-foreground">-</span>
                      )}
                    </TableCell>
                    <TableCell className="text-right">
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => openEditDialog(template)}
                      >
                        <Pencil className="h-4 w-4" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => handleDelete(template.id)}
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
