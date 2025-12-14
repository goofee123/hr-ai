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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
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
  LineChart,
  Loader2,
  Play,
  CheckCircle,
  DollarSign,
  Users,
  TrendingUp,
  AlertCircle,
} from "lucide-react";
import { cyclesApi, scenariosApi, rulesApi, type CompCycle, type Scenario, type ScenarioCreate, type RuleSet } from "@/lib/api/compensation";
import { useToast } from "@/hooks/use-toast";

const statusColors: Record<string, string> = {
  draft: "bg-gray-100 text-gray-800",
  calculating: "bg-blue-100 text-blue-800",
  calculated: "bg-green-100 text-green-800",
  selected: "bg-purple-100 text-purple-800",
  archived: "bg-gray-100 text-gray-600",
};

const statusLabels: Record<string, string> = {
  draft: "Draft",
  calculating: "Calculating...",
  calculated: "Calculated",
  selected: "Selected",
  archived: "Archived",
};

export default function CompensationScenariosPage() {
  const [selectedCycleId, setSelectedCycleId] = useState<string>("");
  const [showCreateDialog, setShowCreateDialog] = useState(false);
  const [newScenario, setNewScenario] = useState<ScenarioCreate>({
    name: "",
    description: "",
    base_merit_percent: 3.0,
    base_bonus_percent: 0,
    budget_target_percent: 3.0,
  });
  const queryClient = useQueryClient();
  const { toast } = useToast();

  // Fetch cycles
  const { data: cyclesData, isLoading: cyclesLoading } = useQuery({
    queryKey: ["compensation-cycles-for-scenarios"],
    queryFn: () => cyclesApi.list(),
  });

  const cycles = cyclesData?.items || [];

  // Fetch rule sets for dropdown
  const { data: ruleSetsData } = useQuery({
    queryKey: ["rule-sets-active"],
    queryFn: () => rulesApi.listSets({ is_active: true }),
  });

  const ruleSets = ruleSetsData?.items || [];

  // Fetch scenarios for selected cycle
  const { data: scenarios, isLoading: scenariosLoading } = useQuery({
    queryKey: ["scenarios", selectedCycleId],
    queryFn: () => scenariosApi.list(selectedCycleId),
    enabled: !!selectedCycleId,
  });

  // Create scenario mutation
  const createMutation = useMutation({
    mutationFn: (data: ScenarioCreate) => scenariosApi.create(selectedCycleId, data),
    onSuccess: () => {
      toast({ title: "Scenario created successfully" });
      queryClient.invalidateQueries({ queryKey: ["scenarios", selectedCycleId] });
      setShowCreateDialog(false);
      setNewScenario({
        name: "",
        description: "",
        base_merit_percent: 3.0,
        base_bonus_percent: 0,
        budget_target_percent: 3.0,
      });
    },
    onError: (error: Error) => {
      toast({ title: "Failed to create scenario", description: error.message, variant: "destructive" });
    },
  });

  // Calculate scenario mutation
  const calculateMutation = useMutation({
    mutationFn: (scenarioId: string) => scenariosApi.calculate(scenarioId),
    onSuccess: () => {
      toast({ title: "Calculation started" });
      queryClient.invalidateQueries({ queryKey: ["scenarios", selectedCycleId] });
    },
    onError: (error: Error) => {
      toast({ title: "Calculation failed", description: error.message, variant: "destructive" });
    },
  });

  // Select scenario mutation
  const selectMutation = useMutation({
    mutationFn: (scenarioId: string) => scenariosApi.select(scenarioId),
    onSuccess: () => {
      toast({ title: "Scenario selected" });
      queryClient.invalidateQueries({ queryKey: ["scenarios", selectedCycleId] });
    },
    onError: (error: Error) => {
      toast({ title: "Failed to select scenario", description: error.message, variant: "destructive" });
    },
  });

  const handleCreate = () => {
    if (!newScenario.name.trim()) {
      toast({ title: "Name is required", variant: "destructive" });
      return;
    }
    createMutation.mutate(newScenario);
  };

  const selectedCycle = cycles.find((c: CompCycle) => c.id === selectedCycleId);

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        <Button variant="ghost" size="icon" asChild>
          <Link href="/compensation">
            <ArrowLeft className="h-4 w-4" />
          </Link>
        </Button>
        <div className="flex-1">
          <h1 className="text-3xl font-bold">Scenario Modeling</h1>
          <p className="text-muted-foreground">
            Create and compare different compensation scenarios
          </p>
        </div>
        {selectedCycleId && (
          <Dialog open={showCreateDialog} onOpenChange={setShowCreateDialog}>
            <DialogTrigger asChild>
              <Button>
                <Plus className="mr-2 h-4 w-4" />
                New Scenario
              </Button>
            </DialogTrigger>
            <DialogContent className="max-w-lg">
              <DialogHeader>
                <DialogTitle>Create Scenario</DialogTitle>
                <DialogDescription>
                  Create a new compensation scenario for {selectedCycle?.name}
                </DialogDescription>
              </DialogHeader>
              <div className="space-y-4 py-4">
                <div className="space-y-2">
                  <Label htmlFor="name">Scenario Name</Label>
                  <Input
                    id="name"
                    placeholder="e.g., Conservative 2.5% Merit"
                    value={newScenario.name}
                    onChange={(e) => setNewScenario({ ...newScenario, name: e.target.value })}
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="description">Description</Label>
                  <Textarea
                    id="description"
                    placeholder="Describe the goals of this scenario..."
                    value={newScenario.description || ""}
                    onChange={(e) => setNewScenario({ ...newScenario, description: e.target.value })}
                  />
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label htmlFor="base_merit">Base Merit %</Label>
                    <Input
                      id="base_merit"
                      type="number"
                      step="0.1"
                      value={newScenario.base_merit_percent}
                      onChange={(e) => setNewScenario({ ...newScenario, base_merit_percent: parseFloat(e.target.value) || 0 })}
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="budget_target">Budget Target %</Label>
                    <Input
                      id="budget_target"
                      type="number"
                      step="0.1"
                      value={newScenario.budget_target_percent}
                      onChange={(e) => setNewScenario({ ...newScenario, budget_target_percent: parseFloat(e.target.value) || 0 })}
                    />
                  </div>
                </div>
                <div className="space-y-2">
                  <Label htmlFor="rule_set">Rule Set (Optional)</Label>
                  <Select
                    value={newScenario.rule_set_id || "none"}
                    onValueChange={(value) => setNewScenario({ ...newScenario, rule_set_id: value === "none" ? undefined : value })}
                  >
                    <SelectTrigger>
                      <SelectValue placeholder="Select a rule set..." />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="none">No rule set</SelectItem>
                      {ruleSets.map((rs: RuleSet) => (
                        <SelectItem key={rs.id} value={rs.id}>
                          {rs.name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-2">
                  <Label htmlFor="goal">Goal Description</Label>
                  <Textarea
                    id="goal"
                    placeholder="e.g., Stay below 3% overall, reward top 10% performers..."
                    value={newScenario.goal_description || ""}
                    onChange={(e) => setNewScenario({ ...newScenario, goal_description: e.target.value })}
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
        )}
      </div>

      {/* Cycle Selection */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base">Select Compensation Cycle</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="w-80">
            <Select value={selectedCycleId} onValueChange={setSelectedCycleId}>
              <SelectTrigger>
                <SelectValue placeholder="Select a cycle..." />
              </SelectTrigger>
              <SelectContent>
                {cyclesLoading ? (
                  <SelectItem value="loading" disabled>Loading...</SelectItem>
                ) : cycles.length === 0 ? (
                  <SelectItem value="none" disabled>No cycles found</SelectItem>
                ) : (
                  cycles.map((cycle: CompCycle) => (
                    <SelectItem key={cycle.id} value={cycle.id}>
                      {cycle.name} ({cycle.fiscal_year}) - {statusLabels[cycle.status]}
                    </SelectItem>
                  ))
                )}
              </SelectContent>
            </Select>
          </div>
        </CardContent>
      </Card>

      {/* Scenarios Grid */}
      {selectedCycleId ? (
        scenariosLoading ? (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
          </div>
        ) : !scenarios || scenarios.length === 0 ? (
          <Card className="border-dashed">
            <CardContent className="py-12 text-center">
              <LineChart className="mx-auto h-12 w-12 text-muted-foreground mb-4" />
              <h3 className="text-lg font-semibold mb-2">No scenarios yet</h3>
              <p className="text-muted-foreground mb-4">
                Create your first scenario to start modeling compensation changes.
              </p>
              <Button onClick={() => setShowCreateDialog(true)}>
                <Plus className="mr-2 h-4 w-4" />
                Create Scenario
              </Button>
            </CardContent>
          </Card>
        ) : (
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            {scenarios.map((scenario: Scenario) => (
              <Card key={scenario.id} className={scenario.is_selected ? "border-primary" : ""}>
                <CardHeader className="pb-2">
                  <div className="flex items-start justify-between">
                    <div>
                      <CardTitle className="text-lg flex items-center gap-2">
                        {scenario.name}
                        {scenario.is_selected && (
                          <CheckCircle className="h-4 w-4 text-primary" />
                        )}
                      </CardTitle>
                      <CardDescription className="mt-1">
                        {scenario.description || "No description"}
                      </CardDescription>
                    </div>
                    <Badge className={statusColors[scenario.status]}>
                      {statusLabels[scenario.status]}
                    </Badge>
                  </div>
                </CardHeader>
                <CardContent>
                  {/* Parameters */}
                  <div className="grid grid-cols-2 gap-2 mb-4 text-sm">
                    <div className="flex items-center gap-2">
                      <TrendingUp className="h-4 w-4 text-muted-foreground" />
                      <span>Base Merit: {scenario.base_merit_percent?.toFixed(1) || 0}%</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <AlertCircle className="h-4 w-4 text-muted-foreground" />
                      <span>Target: {scenario.budget_target_percent?.toFixed(1) || 0}%</span>
                    </div>
                  </div>

                  {/* Results (if calculated) */}
                  {scenario.status === "calculated" || scenario.status === "selected" ? (
                    <div className="grid grid-cols-2 gap-4 p-4 bg-muted/50 rounded-lg mb-4">
                      <div>
                        <div className="flex items-center gap-2 text-muted-foreground text-xs">
                          <Users className="h-3 w-3" />
                          Employees
                        </div>
                        <p className="text-lg font-bold">{scenario.employees_affected || 0}</p>
                      </div>
                      <div>
                        <div className="flex items-center gap-2 text-muted-foreground text-xs">
                          <DollarSign className="h-3 w-3" />
                          Total Increase
                        </div>
                        <p className="text-lg font-bold">
                          {new Intl.NumberFormat("en-US", {
                            style: "currency",
                            currency: "USD",
                            notation: "compact",
                          }).format(scenario.total_recommended_increase || 0)}
                        </p>
                      </div>
                      <div className="col-span-2">
                        <div className="flex items-center gap-2 text-muted-foreground text-xs">
                          <TrendingUp className="h-3 w-3" />
                          Overall Increase
                        </div>
                        <p className="text-lg font-bold">
                          {((scenario.overall_increase_percent || 0) * 100).toFixed(2)}%
                        </p>
                      </div>
                    </div>
                  ) : null}

                  {/* Actions */}
                  <div className="flex gap-2">
                    {scenario.status === "draft" && (
                      <Button
                        size="sm"
                        onClick={() => calculateMutation.mutate(scenario.id)}
                        disabled={calculateMutation.isPending}
                      >
                        {calculateMutation.isPending ? (
                          <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                        ) : (
                          <Play className="mr-2 h-4 w-4" />
                        )}
                        Calculate
                      </Button>
                    )}
                    {scenario.status === "calculated" && !scenario.is_selected && (
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => selectMutation.mutate(scenario.id)}
                        disabled={selectMutation.isPending}
                      >
                        {selectMutation.isPending ? (
                          <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                        ) : (
                          <CheckCircle className="mr-2 h-4 w-4" />
                        )}
                        Select
                      </Button>
                    )}
                    <Button variant="ghost" size="sm">
                      View Details
                    </Button>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        )
      ) : (
        <Card className="border-dashed">
          <CardContent className="py-12 text-center">
            <LineChart className="mx-auto h-12 w-12 text-muted-foreground mb-4" />
            <h3 className="text-lg font-semibold mb-2">Select a Cycle</h3>
            <p className="text-muted-foreground">
              Choose a compensation cycle above to view and create scenarios.
            </p>
          </CardContent>
        </Card>
      )}

      {/* Help Card */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base">How Scenario Modeling Works</CardTitle>
        </CardHeader>
        <CardContent className="text-sm text-muted-foreground">
          <div className="grid md:grid-cols-4 gap-6">
            <div>
              <h4 className="font-medium text-foreground mb-2">1. Create</h4>
              <p>
                Define a scenario with base merit percentages, budget targets,
                and optionally link a rule set.
              </p>
            </div>
            <div>
              <h4 className="font-medium text-foreground mb-2">2. Calculate</h4>
              <p>
                Run the calculation to apply rules and generate per-employee
                recommendations.
              </p>
            </div>
            <div>
              <h4 className="font-medium text-foreground mb-2">3. Compare</h4>
              <p>
                Create multiple scenarios with different parameters to compare
                budget impact and distribution.
              </p>
            </div>
            <div>
              <h4 className="font-medium text-foreground mb-2">4. Select</h4>
              <p>
                Choose the approved scenario to populate manager worksheets
                with recommendations.
              </p>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
