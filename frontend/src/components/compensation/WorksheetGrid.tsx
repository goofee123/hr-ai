"use client";

import { useMemo, useCallback, useState } from "react";
import { AgGridReact } from "ag-grid-react";
import type { ColDef, ValueFormatterParams, CellClassParams, CellValueChangedEvent, GridReadyEvent } from "ag-grid-community";
import "ag-grid-community/styles/ag-grid.css";
import "ag-grid-community/styles/ag-theme-alpine.css";
import type { WorksheetEntry, WorksheetEntryUpdate } from "@/lib/api/compensation";

interface WorksheetGridProps {
  entries: WorksheetEntry[];
  onUpdateEntry: (entryId: string, data: WorksheetEntryUpdate) => Promise<void>;
  isLoading?: boolean;
  readOnly?: boolean;
}

const currencyFormatter = (params: ValueFormatterParams) => {
  if (params.value == null) return "-";
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(params.value);
};

const percentFormatter = (params: ValueFormatterParams) => {
  if (params.value == null) return "-";
  return `${params.value.toFixed(2)}%`;
};

const compaRatioFormatter = (params: ValueFormatterParams) => {
  if (params.value == null) return "-";
  return params.value.toFixed(3);
};

const statusColors: Record<string, string> = {
  pending: "#f3f4f6",
  submitted: "#fef3c7",
  approved: "#d1fae5",
  rejected: "#fee2e2",
  flagged: "#fce7f3",
};

const highlightColors: Record<string, string> = {
  light_green: "#d1fae5",
  dark_green: "#a7f3d0",
  beige: "#fef3c7",
  red: "#fecaca",
};

export default function WorksheetGrid({ entries, onUpdateEntry, isLoading, readOnly }: WorksheetGridProps) {
  const [gridApi, setGridApi] = useState<any>(null);

  const onGridReady = useCallback((params: GridReadyEvent) => {
    setGridApi(params.api);
    params.api.sizeColumnsToFit();
  }, []);

  const columnDefs: ColDef[] = useMemo(
    () => [
      // Employee Info
      {
        headerName: "Employee",
        children: [
          {
            field: "employee_id",
            headerName: "ID",
            width: 100,
            pinned: "left",
          },
          {
            field: "first_name",
            headerName: "First Name",
            width: 120,
            pinned: "left",
          },
          {
            field: "last_name",
            headerName: "Last Name",
            width: 120,
            pinned: "left",
          },
          {
            field: "department",
            headerName: "Department",
            width: 150,
          },
          {
            field: "job_title",
            headerName: "Title",
            width: 180,
          },
        ],
      },
      // Current Compensation
      {
        headerName: "Current",
        children: [
          {
            field: "current_annual",
            headerName: "Annual Salary",
            width: 130,
            valueFormatter: currencyFormatter,
            type: "numericColumn",
          },
          {
            field: "current_compa_ratio",
            headerName: "Compa Ratio",
            width: 110,
            valueFormatter: compaRatioFormatter,
            type: "numericColumn",
          },
          {
            field: "performance_score",
            headerName: "Perf Score",
            width: 100,
            type: "numericColumn",
          },
        ],
      },
      // System Recommendations
      {
        headerName: "System Recommended",
        children: [
          {
            field: "system_raise_percent",
            headerName: "Raise %",
            width: 100,
            valueFormatter: percentFormatter,
            type: "numericColumn",
            cellStyle: { backgroundColor: "#f0f9ff" },
          },
          {
            field: "system_new_salary",
            headerName: "New Salary",
            width: 130,
            valueFormatter: currencyFormatter,
            type: "numericColumn",
            cellStyle: { backgroundColor: "#f0f9ff" },
          },
          {
            field: "system_bonus_percent",
            headerName: "Bonus %",
            width: 100,
            valueFormatter: percentFormatter,
            type: "numericColumn",
            cellStyle: { backgroundColor: "#f0f9ff" },
          },
        ],
      },
      // Manager Input (Editable)
      {
        headerName: "Manager Input",
        children: [
          {
            field: "manager_raise_percent",
            headerName: "Raise %",
            width: 100,
            editable: !readOnly,
            valueFormatter: percentFormatter,
            type: "numericColumn",
            cellStyle: { backgroundColor: "#fef9c3" },
          },
          {
            field: "manager_new_salary",
            headerName: "New Salary",
            width: 130,
            editable: !readOnly,
            valueFormatter: currencyFormatter,
            type: "numericColumn",
            cellStyle: { backgroundColor: "#fef9c3" },
          },
          {
            field: "manager_bonus_percent",
            headerName: "Bonus %",
            width: 100,
            editable: !readOnly,
            valueFormatter: percentFormatter,
            type: "numericColumn",
            cellStyle: { backgroundColor: "#fef9c3" },
          },
          {
            field: "manager_justification",
            headerName: "Justification",
            width: 200,
            editable: !readOnly,
            cellStyle: { backgroundColor: "#fef9c3" },
          },
        ],
      },
      // Deltas
      {
        headerName: "Delta",
        children: [
          {
            field: "delta_raise_percent",
            headerName: "Raise Δ",
            width: 90,
            valueFormatter: percentFormatter,
            type: "numericColumn",
            cellStyle: (params: CellClassParams) => {
              if (params.value == null) return {};
              if (params.value > 0) return { color: "#16a34a", fontWeight: "bold" };
              if (params.value < 0) return { color: "#dc2626", fontWeight: "bold" };
              return {};
            },
          },
        ],
      },
      // Status & Flags
      {
        headerName: "Status",
        children: [
          {
            field: "status",
            headerName: "Status",
            width: 110,
            cellStyle: (params: CellClassParams) => ({
              backgroundColor: statusColors[params.value] || "#ffffff",
              fontWeight: "500",
              textTransform: "capitalize",
            }),
          },
          {
            field: "manager_promotion_flag",
            headerName: "Promo",
            width: 80,
            editable: !readOnly,
            cellRenderer: (params: any) =>
              params.value ? "✓" : "",
            cellStyle: { textAlign: "center" },
          },
          {
            field: "manager_exception_flag",
            headerName: "Exception",
            width: 90,
            editable: !readOnly,
            cellRenderer: (params: any) =>
              params.value ? "⚠" : "",
            cellStyle: { textAlign: "center" },
          },
        ],
      },
    ],
    [readOnly]
  );

  const defaultColDef = useMemo(
    () => ({
      sortable: true,
      filter: true,
      resizable: true,
    }),
    []
  );

  const onCellValueChanged = useCallback(
    async (event: CellValueChangedEvent) => {
      if (!event.data?.id) return;

      const field = event.colDef.field;
      if (!field) return;

      const update: WorksheetEntryUpdate = {};

      switch (field) {
        case "manager_raise_percent":
          update.manager_raise_percent = event.newValue;
          // Recalculate new salary based on current + raise
          if (event.data.current_annual && event.newValue != null) {
            update.manager_new_salary =
              event.data.current_annual * (1 + event.newValue / 100);
            update.manager_raise_amount =
              event.data.current_annual * (event.newValue / 100);
          }
          break;
        case "manager_new_salary":
          update.manager_new_salary = event.newValue;
          // Recalculate raise percent based on new salary
          if (event.data.current_annual && event.newValue != null) {
            update.manager_raise_percent =
              ((event.newValue - event.data.current_annual) /
                event.data.current_annual) *
              100;
            update.manager_raise_amount =
              event.newValue - event.data.current_annual;
          }
          break;
        case "manager_bonus_percent":
          update.manager_bonus_percent = event.newValue;
          if (event.data.current_annual && event.newValue != null) {
            update.manager_bonus_amount =
              event.data.current_annual * (event.newValue / 100);
          }
          break;
        case "manager_justification":
          update.manager_justification = event.newValue;
          break;
        case "manager_promotion_flag":
          update.manager_promotion_flag = event.newValue;
          break;
        case "manager_exception_flag":
          update.manager_exception_flag = event.newValue;
          break;
      }

      try {
        await onUpdateEntry(event.data.id, update);
      } catch (error) {
        console.error("Failed to update entry:", error);
        // Revert the change
        event.node.setDataValue(field, event.oldValue);
      }
    },
    [onUpdateEntry]
  );

  const getRowStyle = useCallback((params: any) => {
    if (params.data?.highlight_color) {
      return {
        backgroundColor: highlightColors[params.data.highlight_color] || undefined,
      };
    }
    return undefined;
  }, []);

  return (
    <div className="ag-theme-alpine" style={{ height: 600, width: "100%" }}>
      <AgGridReact
        rowData={entries}
        columnDefs={columnDefs}
        defaultColDef={defaultColDef}
        onGridReady={onGridReady}
        onCellValueChanged={onCellValueChanged}
        getRowStyle={getRowStyle}
        animateRows={true}
        rowSelection="multiple"
        enableRangeSelection={true}
        suppressRowClickSelection={true}
        loading={isLoading}
        overlayLoadingTemplate='<span class="ag-overlay-loading-center">Loading worksheet...</span>'
        overlayNoRowsTemplate='<span class="ag-overlay-no-rows-center">No employees found</span>'
      />
    </div>
  );
}
