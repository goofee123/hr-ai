"use client";

import { useState } from "react";
import Link from "next/link";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Switch } from "@/components/ui/switch";
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
  ArrowLeft,
  Plus,
  Settings,
  ChevronRight,
  Loader2,
  Trash2,
  Edit,
  Copy,
} from "lucide-react";
import { rulesApi, type RuleSet, type RuleSetCreate } from "@/lib/api/compensation";
import { useToast } from "@/hooks/use-toast";

const ruleTypeLabels: Record<string, string> = {
  merit: "Merit Increase",
  bonus: "Bonus",
  promotion: "Promotion",
  minimum_salary: "Minimum Salary",
  cap: "Cap/Limit",
  eligibility: "Eligibility",
};

const ruleTypeColors: Record<string, string> = {
  merit: "bg-green-100 text-green-800",
  bonus: "bg-blue-100 text-blue-800",
  promotion: "bg-purple-100 text-purple-800",
  minimum_salary: "bg-orange-100 text-orange-800",
  cap: "bg-red-100 text-red-800",
  eligibility: "bg-gray-100 text-gray-800",
};

export default function CompensationRulesPage() {
  const [showCreateDialog, setShowCreateDialog] = useState(false);
  const [selectedSet, setSelectedSet] = useState<RuleSet | null>(null);
  const [newRuleSet, setNewRuleSet] = useState<RuleSetCreate>({
    name: "",
    description: "",
    is_active: true,
    is_default: false,
  });
  const queryClient = useQueryClient();
  const { toast } = useToast();

  // Fetch rule sets
  const { data, isLoading, error } = useQuery({
    queryKey: ["rule-sets"],
    queryFn: () => rulesApi.listSets(),
  });

  const ruleSets = data?.items || [];

  // Fetch selected rule set with rules
  const { data: selectedSetData } = useQuery({
    queryKey: ["rule-set", selectedSet?.id],
    queryFn: () => (selectedSet ? rulesApi.getSet(selectedSet.id) : null),
    enabled: !!selectedSet,
  });

  // Create rule set mutation
  const createMutation = useMutation({
    mutationFn: (data: RuleSetCreate) => rulesApi.createSet(data),
    onSuccess: () => {
      toast({ title: "Rule set created successfully" });
      queryClient.invalidateQueries({ queryKey: ["rule-sets"] });
      setShowCreateDialog(false);
      setNewRuleSet({ name: "", description: "", is_active: true, is_default: false });
    },
    onError: (error: Error) => {
      toast({ title: "Failed to create rule set", description: error.message, variant: "destructive" });
    },
  });

  // Delete rule set mutation
  const deleteMutation = useMutation({
    mutationFn: (id: string) => rulesApi.deleteSet(id),
    onSuccess: () => {
      toast({ title: "Rule set deleted" });
      queryClient.invalidateQueries({ queryKey: ["rule-sets"] });
      if (selectedSet) setSelectedSet(null);
    },
    onError: (error: Error) => {
      toast({ title: "Failed to delete rule set", description: error.message, variant: "destructive" });
    },
  });

  // Toggle active status mutation
  const toggleMutation = useMutation({
    mutationFn: ({ id, is_active }: { id: string; is_active: boolean }) =>
      rulesApi.updateSet(id, { is_active }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["rule-sets"] });
    },
  });

  const handleCreate = () => {
    if (!newRuleSet.name.trim()) {
      toast({ title: "Name is required", variant: "destructive" });
      return;
    }
    createMutation.mutate(newRuleSet);
  };

  const rules = selectedSetData?.rules || [];

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        <Button variant="ghost" size="icon" asChild>
          <Link href="/compensation">
            <ArrowLeft className="h-4 w-4" />
          </Link>
        </Button>
        <div className="flex-1">
          <h1 className="text-3xl font-bold">Rules Engine</h1>
          <p className="text-muted-foreground">
            Define compensation rules based on performance, tenure, and other criteria
          </p>
        </div>
        <Dialog open={showCreateDialog} onOpenChange={setShowCreateDialog}>
          <DialogTrigger asChild>
            <Button>
              <Plus className="mr-2 h-4 w-4" />
              New Rule Set
            </Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Create Rule Set</DialogTitle>
              <DialogDescription>
                A rule set is a collection of rules that can be applied to a compensation scenario.
              </DialogDescription>
            </DialogHeader>
            <div className="space-y-4 py-4">
              <div className="space-y-2">
                <Label htmlFor="name">Name</Label>
                <Input
                  id="name"
                  placeholder="e.g., 2025 Annual Merit Rules"
                  value={newRuleSet.name}
                  onChange={(e) => setNewRuleSet({ ...newRuleSet, name: e.target.value })}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="description">Description</Label>
                <Textarea
                  id="description"
                  placeholder="Describe the purpose of this rule set..."
                  value={newRuleSet.description || ""}
                  onChange={(e) => setNewRuleSet({ ...newRuleSet, description: e.target.value })}
                />
              </div>
              <div className="flex items-center justify-between">
                <div className="space-y-0.5">
                  <Label>Active</Label>
                  <p className="text-sm text-muted-foreground">
                    Enable this rule set for use in scenarios
                  </p>
                </div>
                <Switch
                  checked={newRuleSet.is_active}
                  onCheckedChange={(checked) => setNewRuleSet({ ...newRuleSet, is_active: checked })}
                />
              </div>
              <div className="flex items-center justify-between">
                <div className="space-y-0.5">
                  <Label>Default</Label>
                  <p className="text-sm text-muted-foreground">
                    Use as the default rule set for new scenarios
                  </p>
                </div>
                <Switch
                  checked={newRuleSet.is_default}
                  onCheckedChange={(checked) => setNewRuleSet({ ...newRuleSet, is_default: checked })}
                />
              </div>
            </div>
            <DialogFooter>
              <Button variant="outline" onClick={() => setShowCreateDialog(false)}>
                Cancel
              </Button>
              <Button onClick={handleCreate} disabled={createMutation.isPending}>
                {createMutation.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                Create
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        {/* Rule Sets List */}
        <Card className="lg:col-span-1">
          <CardHeader>
            <CardTitle className="text-base">Rule Sets</CardTitle>
            <CardDescription>
              {ruleSets.length} rule set{ruleSets.length !== 1 ? "s" : ""}
            </CardDescription>
          </CardHeader>
          <CardContent>
            {isLoading ? (
              <div className="flex items-center justify-center py-8">
                <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
              </div>
            ) : error ? (
              <div className="text-center py-8 text-destructive">
                Failed to load rule sets
              </div>
            ) : ruleSets.length === 0 ? (
              <div className="text-center py-8">
                <Settings className="mx-auto h-8 w-8 text-muted-foreground mb-2" />
                <p className="text-sm text-muted-foreground">
                  No rule sets yet. Create one to get started.
                </p>
              </div>
            ) : (
              <div className="space-y-2">
                {ruleSets.map((ruleSet) => (
                  <div
                    key={ruleSet.id}
                    className={`p-3 rounded-lg border cursor-pointer transition-colors ${
                      selectedSet?.id === ruleSet.id
                        ? "border-primary bg-primary/5"
                        : "hover:bg-muted/50"
                    }`}
                    onClick={() => setSelectedSet(ruleSet)}
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <span className="font-medium truncate">{ruleSet.name}</span>
                          {ruleSet.is_default && (
                            <Badge variant="outline" className="text-xs">
                              Default
                            </Badge>
                          )}
                        </div>
                        <p className="text-xs text-muted-foreground truncate">
                          v{ruleSet.version}
                        </p>
                      </div>
                      <div className="flex items-center gap-2">
                        <Switch
                          checked={ruleSet.is_active}
                          onCheckedChange={(checked) =>
                            toggleMutation.mutate({ id: ruleSet.id, is_active: checked })
                          }
                          onClick={(e) => e.stopPropagation()}
                        />
                        <ChevronRight className="h-4 w-4 text-muted-foreground" />
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        {/* Rule Set Details */}
        <Card className="lg:col-span-2">
          <CardHeader>
            {selectedSet ? (
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle>{selectedSet.name}</CardTitle>
                  <CardDescription>
                    {selectedSet.description || "No description provided"}
                  </CardDescription>
                </div>
                <div className="flex items-center gap-2">
                  <Button variant="outline" size="sm">
                    <Copy className="mr-2 h-4 w-4" />
                    Clone
                  </Button>
                  <Button variant="outline" size="sm">
                    <Edit className="mr-2 h-4 w-4" />
                    Edit
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    className="text-destructive"
                    onClick={() => {
                      if (confirm("Are you sure you want to delete this rule set?")) {
                        deleteMutation.mutate(selectedSet.id);
                      }
                    }}
                  >
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </div>
              </div>
            ) : (
              <div>
                <CardTitle>Rules</CardTitle>
                <CardDescription>
                  Select a rule set to view and manage its rules
                </CardDescription>
              </div>
            )}
          </CardHeader>
          <CardContent>
            {selectedSet ? (
              <>
                {/* Rule Stats */}
                <div className="grid grid-cols-3 gap-4 mb-6">
                  <div className="p-4 rounded-lg bg-muted/50">
                    <p className="text-2xl font-bold">{rules.length}</p>
                    <p className="text-xs text-muted-foreground">Total Rules</p>
                  </div>
                  <div className="p-4 rounded-lg bg-muted/50">
                    <p className="text-2xl font-bold">
                      {rules.filter((r) => r.is_active).length}
                    </p>
                    <p className="text-xs text-muted-foreground">Active</p>
                  </div>
                  <div className="p-4 rounded-lg bg-muted/50">
                    <p className="text-2xl font-bold">{selectedSet.version}</p>
                    <p className="text-xs text-muted-foreground">Version</p>
                  </div>
                </div>

                {/* Rules Table */}
                {rules.length === 0 ? (
                  <div className="text-center py-12 border rounded-lg">
                    <Settings className="mx-auto h-12 w-12 text-muted-foreground mb-4" />
                    <h3 className="text-lg font-semibold mb-2">No rules yet</h3>
                    <p className="text-muted-foreground mb-4">
                      Add rules to define how compensation is calculated
                    </p>
                    <Button>
                      <Plus className="mr-2 h-4 w-4" />
                      Add Rule
                    </Button>
                  </div>
                ) : (
                  <>
                    <div className="flex items-center justify-between mb-4">
                      <h3 className="font-medium">Rules</h3>
                      <Button size="sm">
                        <Plus className="mr-2 h-4 w-4" />
                        Add Rule
                      </Button>
                    </div>
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead>Priority</TableHead>
                          <TableHead>Name</TableHead>
                          <TableHead>Type</TableHead>
                          <TableHead>Status</TableHead>
                          <TableHead className="w-[100px]">Actions</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {rules.map((rule) => (
                          <TableRow key={rule.id}>
                            <TableCell className="font-mono text-sm">
                              {rule.priority}
                            </TableCell>
                            <TableCell>
                              <div>
                                <p className="font-medium">{rule.name}</p>
                                {rule.description && (
                                  <p className="text-xs text-muted-foreground truncate max-w-xs">
                                    {rule.description}
                                  </p>
                                )}
                              </div>
                            </TableCell>
                            <TableCell>
                              <Badge className={ruleTypeColors[rule.rule_type]}>
                                {ruleTypeLabels[rule.rule_type] || rule.rule_type}
                              </Badge>
                            </TableCell>
                            <TableCell>
                              {rule.is_active ? (
                                <Badge variant="outline" className="bg-green-50">
                                  Active
                                </Badge>
                              ) : (
                                <Badge variant="outline" className="bg-gray-50">
                                  Inactive
                                </Badge>
                              )}
                            </TableCell>
                            <TableCell>
                              <div className="flex items-center gap-1">
                                <Button variant="ghost" size="icon" className="h-8 w-8">
                                  <Edit className="h-4 w-4" />
                                </Button>
                                <Button variant="ghost" size="icon" className="h-8 w-8">
                                  <Trash2 className="h-4 w-4" />
                                </Button>
                              </div>
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </>
                )}
              </>
            ) : (
              <div className="text-center py-12">
                <Settings className="mx-auto h-12 w-12 text-muted-foreground mb-4" />
                <h3 className="text-lg font-semibold mb-2">Select a Rule Set</h3>
                <p className="text-muted-foreground">
                  Choose a rule set from the left to view and manage its rules
                </p>
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Help Card */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base">How Rules Work</CardTitle>
        </CardHeader>
        <CardContent className="text-sm text-muted-foreground">
          <div className="grid md:grid-cols-3 gap-6">
            <div>
              <h4 className="font-medium text-foreground mb-2">1. Conditions</h4>
              <p>
                Define when a rule applies using conditions like performance score,
                compa ratio, department, tenure, etc. Conditions can be combined with AND/OR logic.
              </p>
            </div>
            <div>
              <h4 className="font-medium text-foreground mb-2">2. Actions</h4>
              <p>
                Specify what happens when conditions are met: set merit percentage,
                apply bonus, cap salary at band max, flag for review, etc.
              </p>
            </div>
            <div>
              <h4 className="font-medium text-foreground mb-2">3. Priority</h4>
              <p>
                Rules are evaluated in priority order (lower number = higher priority).
                Later rules can override earlier ones or add to their effects.
              </p>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
