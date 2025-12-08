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
import { ArrowLeft, Plus, Pencil, Trash2, Loader2, Check, X } from "lucide-react";
import { api } from "@/lib/api/client";
import { useToast } from "@/hooks/use-toast";

interface DispositionReason {
  id: string;
  tenant_id: string;
  code: string;
  label: string;
  description: string | null;
  is_eeo_compliant: boolean;
  requires_notes: boolean;
  sort_order: number;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export default function DispositionReasonsPage() {
  const { toast } = useToast();
  const [reasons, setReasons] = useState<DispositionReason[]>([]);
  const [loading, setLoading] = useState(true);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingReason, setEditingReason] = useState<DispositionReason | null>(null);
  const [formData, setFormData] = useState({
    code: "",
    label: "",
    description: "",
    is_eeo_compliant: true,
    requires_notes: false,
    sort_order: 0,
    is_active: true,
  });
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    fetchReasons();
  }, []);

  const fetchReasons = async () => {
    try {
      const data = await api.get<DispositionReason[]>("/api/v1/admin/disposition-reasons");
      setReasons(data);
    } catch (error) {
      toast({ title: "Error", description: "Failed to load disposition reasons", variant: "destructive" });
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async () => {
    setSaving(true);
    try {
      if (editingReason) {
        await api.patch(`/api/v1/admin/disposition-reasons/${editingReason.id}`, formData);
        toast({ title: "Success", description: "Reason updated successfully" });
      } else {
        await api.post("/api/v1/admin/disposition-reasons", formData);
        toast({ title: "Success", description: "Reason created successfully" });
      }
      setDialogOpen(false);
      resetForm();
      fetchReasons();
    } catch (error: any) {
      toast({ title: "Error", description: error.message || "Failed to save reason", variant: "destructive" });
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (id: string) => {
    if (!confirm("Are you sure you want to delete this reason?")) return;
    try {
      await api.delete(`/api/v1/admin/disposition-reasons/${id}`);
      toast({ title: "Success", description: "Reason deleted successfully" });
      fetchReasons();
    } catch (error: any) {
      toast({ title: "Error", description: error.message || "Failed to delete reason", variant: "destructive" });
    }
  };

  const openEditDialog = (reason: DispositionReason) => {
    setEditingReason(reason);
    setFormData({
      code: reason.code,
      label: reason.label,
      description: reason.description || "",
      is_eeo_compliant: reason.is_eeo_compliant,
      requires_notes: reason.requires_notes,
      sort_order: reason.sort_order,
      is_active: reason.is_active,
    });
    setDialogOpen(true);
  };

  const resetForm = () => {
    setEditingReason(null);
    setFormData({
      code: "",
      label: "",
      description: "",
      is_eeo_compliant: true,
      requires_notes: false,
      sort_order: 0,
      is_active: true,
    });
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
          <h1 className="text-3xl font-bold">Disposition Reasons</h1>
          <p className="text-muted-foreground">
            Manage rejection and withdrawal reason codes
          </p>
        </div>
        <Dialog open={dialogOpen} onOpenChange={(open) => {
          setDialogOpen(open);
          if (!open) resetForm();
        }}>
          <DialogTrigger asChild>
            <Button>
              <Plus className="h-4 w-4 mr-2" />
              New Reason
            </Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>
                {editingReason ? "Edit Disposition Reason" : "Create Disposition Reason"}
              </DialogTitle>
              <DialogDescription>
                Configure a reason code for candidate rejections or withdrawals.
              </DialogDescription>
            </DialogHeader>
            <div className="space-y-4 py-4">
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="code">Code</Label>
                  <Input
                    id="code"
                    value={formData.code}
                    onChange={(e) => setFormData({ ...formData, code: e.target.value.toUpperCase() })}
                    placeholder="e.g., NOT_QUALIFIED"
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="sort_order">Sort Order</Label>
                  <Input
                    id="sort_order"
                    type="number"
                    value={formData.sort_order}
                    onChange={(e) => setFormData({ ...formData, sort_order: parseInt(e.target.value) || 0 })}
                  />
                </div>
              </div>
              <div className="space-y-2">
                <Label htmlFor="label">Label</Label>
                <Input
                  id="label"
                  value={formData.label}
                  onChange={(e) => setFormData({ ...formData, label: e.target.value })}
                  placeholder="e.g., Does not meet minimum qualifications"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="description">Description (Optional)</Label>
                <Textarea
                  id="description"
                  value={formData.description}
                  onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                  placeholder="Additional context for when to use this reason..."
                />
              </div>
              <div className="space-y-3">
                <div className="flex items-center space-x-2">
                  <Switch
                    id="is_eeo_compliant"
                    checked={formData.is_eeo_compliant}
                    onCheckedChange={(checked) => setFormData({ ...formData, is_eeo_compliant: checked })}
                  />
                  <Label htmlFor="is_eeo_compliant">EEO Compliant</Label>
                </div>
                <div className="flex items-center space-x-2">
                  <Switch
                    id="requires_notes"
                    checked={formData.requires_notes}
                    onCheckedChange={(checked) => setFormData({ ...formData, requires_notes: checked })}
                  />
                  <Label htmlFor="requires_notes">Requires Notes</Label>
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
              <Button onClick={handleSubmit} disabled={saving || !formData.code || !formData.label}>
                {saving && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
                {editingReason ? "Update" : "Create"}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Reasons</CardTitle>
        </CardHeader>
        <CardContent>
          {reasons.length === 0 ? (
            <p className="text-center text-muted-foreground py-8">
              No disposition reasons found. Create your first reason to get started.
            </p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Code</TableHead>
                  <TableHead>Label</TableHead>
                  <TableHead>EEO</TableHead>
                  <TableHead>Notes Req.</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {reasons.map((reason) => (
                  <TableRow key={reason.id}>
                    <TableCell>
                      <code className="text-sm bg-muted px-1 py-0.5 rounded">
                        {reason.code}
                      </code>
                    </TableCell>
                    <TableCell>{reason.label}</TableCell>
                    <TableCell>
                      {reason.is_eeo_compliant ? (
                        <Check className="h-4 w-4 text-green-500" />
                      ) : (
                        <X className="h-4 w-4 text-red-500" />
                      )}
                    </TableCell>
                    <TableCell>
                      {reason.requires_notes ? (
                        <Check className="h-4 w-4 text-blue-500" />
                      ) : (
                        <span className="text-muted-foreground">-</span>
                      )}
                    </TableCell>
                    <TableCell>
                      <Badge variant={reason.is_active ? "default" : "secondary"}>
                        {reason.is_active ? "Active" : "Inactive"}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-right">
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => openEditDialog(reason)}
                      >
                        <Pencil className="h-4 w-4" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => handleDelete(reason.id)}
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
