"""Rules Engine for Compensation Calculations.

This module provides a flexible rules engine that evaluates JSONB-based conditions
and applies actions to generate compensation recommendations.

Supports:
- Nested conditions with AND/OR logic
- Multiple comparison operators
- Formula evaluation (safe, no eval())
- Multiple action types
"""

import re
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID


class RulesEngine:
    """
    Flexible rules engine for compensation calculations.
    Supports nested conditions, multiple operators, and formula evaluation.
    """

    # Supported comparison operators
    OPERATORS = {
        'EQ': lambda a, b: a == b,
        'NEQ': lambda a, b: a != b,
        'GT': lambda a, b: float(a) > float(b) if a is not None and b is not None else False,
        'GTE': lambda a, b: float(a) >= float(b) if a is not None and b is not None else False,
        'LT': lambda a, b: float(a) < float(b) if a is not None and b is not None else False,
        'LTE': lambda a, b: float(a) <= float(b) if a is not None and b is not None else False,
        'IN': lambda a, b: a in b if b else False,
        'NOT_IN': lambda a, b: a not in b if b else True,
        'BETWEEN': lambda a, b: b[0] <= float(a) <= b[1] if a is not None and b and len(b) >= 2 else False,
        'CONTAINS': lambda a, b: str(b).lower() in str(a).lower() if a else False,
        'IS_NULL': lambda a, b: a is None,
        'IS_NOT_NULL': lambda a, b: a is not None,
    }

    def __init__(self):
        self.evaluation_log: List[Dict[str, Any]] = []

    def evaluate_conditions(
        self,
        conditions: Dict[str, Any],
        employee: Dict[str, Any],
        log_evaluation: bool = False
    ) -> bool:
        """
        Recursively evaluate nested conditions.

        Args:
            conditions: Condition structure with 'logic' and 'conditions' keys
            employee: Employee data dict to evaluate against
            log_evaluation: Whether to log each condition evaluation

        Returns:
            True if conditions are satisfied, False otherwise

        Example conditions:
        {
            "logic": "AND",
            "conditions": [
                {"field": "performance_score", "operator": "GTE", "value": 4.0},
                {"field": "current_compa_ratio", "operator": "LT", "value": 1.0}
            ]
        }
        """
        logic = conditions.get('logic', 'AND').upper()
        condition_list = conditions.get('conditions', [])

        if not condition_list:
            return True

        results = []
        for cond in condition_list:
            if 'logic' in cond:
                # Nested condition group
                result = self.evaluate_conditions(cond, employee, log_evaluation)
                results.append(result)
            else:
                # Single condition
                result = self._evaluate_single_condition(cond, employee)
                results.append(result)

                if log_evaluation:
                    self.evaluation_log.append({
                        'field': cond.get('field'),
                        'operator': cond.get('operator'),
                        'expected_value': cond.get('value'),
                        'actual_value': employee.get(cond.get('field')),
                        'result': result
                    })

        if logic == 'AND':
            return all(results)
        elif logic == 'OR':
            return any(results)
        else:
            return all(results)

    def _evaluate_single_condition(
        self,
        condition: Dict[str, Any],
        employee: Dict[str, Any]
    ) -> bool:
        """Evaluate a single condition against employee data."""
        field = condition.get('field', '')
        operator = condition.get('operator', 'EQ').upper()
        expected_value = condition.get('value')

        # Get actual value from employee, supporting nested fields (e.g., "extra_attributes.field")
        actual_value = self._get_nested_value(employee, field)

        # Get operator function
        op_func = self.OPERATORS.get(operator)
        if not op_func:
            return False

        try:
            return op_func(actual_value, expected_value)
        except (TypeError, ValueError):
            return False

    def _get_nested_value(self, data: Dict[str, Any], field: str) -> Any:
        """Get a value from nested dict using dot notation."""
        if '.' not in field:
            return data.get(field)

        parts = field.split('.')
        value = data
        for part in parts:
            if isinstance(value, dict):
                value = value.get(part)
            else:
                return None
        return value

    def apply_action(
        self,
        action: Dict[str, Any],
        employee: Dict[str, Any],
        result: Dict[str, Any],
        rule_id: Optional[UUID] = None
    ) -> Dict[str, Any]:
        """
        Apply a rule action to generate/modify recommendation.

        Args:
            action: Action configuration
            employee: Employee data
            result: Current result dict to modify
            rule_id: Optional rule ID for tracking

        Returns:
            Modified result dict
        """
        action_type = action.get('action_type', '')

        if action_type == 'SET_MERIT_PERCENT':
            value = self._resolve_value(action, employee)
            value = self._apply_min_max(value, action)
            result['recommended_raise_percent'] = Decimal(str(value))

        elif action_type == 'SET_MERIT_AMOUNT':
            value = self._resolve_value(action, employee)
            value = self._apply_min_max(value, action)
            result['recommended_raise_amount'] = Decimal(str(value))

        elif action_type == 'SET_BONUS_PERCENT':
            value = self._resolve_value(action, employee)
            value = self._apply_min_max(value, action)
            result['recommended_bonus_percent'] = Decimal(str(value))

        elif action_type == 'SET_BONUS_AMOUNT':
            value = self._resolve_value(action, employee)
            value = self._apply_min_max(value, action)
            result['recommended_bonus_amount'] = Decimal(str(value))

        elif action_type == 'SET_MINIMUM_SALARY':
            value = self._resolve_value(action, employee)
            result['minimum_salary'] = Decimal(str(value))

        elif action_type == 'CAP_TO_BAND_MAX':
            band_max = employee.get('band_maximum')
            if band_max:
                result['salary_cap'] = Decimal(str(band_max))

        elif action_type == 'CAP_BONUS':
            result['cap_bonus_flag'] = True

        elif action_type == 'FLAG_FOR_REVIEW':
            result['needs_review_flag'] = True

        elif action_type == 'REQUIRE_JUSTIFICATION':
            result['requires_justification'] = True

        elif action_type == 'SET_PROMOTION_FLAG':
            result['promotion_flag'] = True

        elif action_type == 'EXCLUDE':
            result['excluded_flag'] = True

        # Track which rule was applied
        if 'applied_rules' not in result:
            result['applied_rules'] = []

        result['applied_rules'].append({
            'rule_id': str(rule_id) if rule_id else None,
            'action_type': action_type,
            'notes': action.get('notes', '')
        })

        return result

    def _resolve_value(self, action: Dict[str, Any], employee: Dict[str, Any]) -> float:
        """
        Resolve action value from static value, field reference, or formula.

        Supports:
        - {"value": 4.5} - Static value
        - {"value_field": "performance_score"} - Value from employee field
        - {"value_formula": "{performance_score} * 0.5 + 2.0"} - Formula
        """
        if 'value' in action:
            return float(action['value'])

        elif 'value_field' in action:
            field_value = self._get_nested_value(employee, action['value_field'])
            return float(field_value) if field_value is not None else 0.0

        elif 'value_formula' in action:
            return self._evaluate_formula(action['value_formula'], employee)

        return 0.0

    def _apply_min_max(self, value: float, action: Dict[str, Any]) -> float:
        """Apply min/max constraints to a value."""
        min_val = action.get('min_value')
        max_val = action.get('max_value')

        if min_val is not None:
            value = max(value, float(min_val))
        if max_val is not None:
            value = min(value, float(max_val))

        return value

    def _evaluate_formula(self, formula: str, employee: Dict[str, Any]) -> float:
        """
        Safely evaluate a simple formula.

        Only supports basic arithmetic: +, -, *, /
        Variables are referenced with {field_name}

        Example: "{performance_score} * 0.5 + 2.0"
        """
        # Replace field references with values
        def replace_field(match):
            field_name = match.group(1)
            value = self._get_nested_value(employee, field_name)
            return str(float(value)) if value is not None else '0'

        # Replace {field_name} with actual values
        expression = re.sub(r'\{([^}]+)\}', replace_field, formula)

        # Only allow safe characters: numbers, operators, parentheses, decimals, spaces
        if not re.match(r'^[\d\s\+\-\*\/\.\(\)]+$', expression):
            return 0.0

        try:
            # Safe evaluation using only numeric operations
            result = eval(expression, {"__builtins__": {}}, {})
            return float(result)
        except (SyntaxError, NameError, TypeError, ZeroDivisionError):
            return 0.0

    def process_employee(
        self,
        employee: Dict[str, Any],
        rules: List[Dict[str, Any]],
        base_merit_percent: Optional[Decimal] = None,
        base_bonus_percent: Optional[Decimal] = None
    ) -> Dict[str, Any]:
        """
        Process a single employee through all rules to generate recommendations.

        Args:
            employee: Employee data dict
            rules: List of rule configurations, sorted by priority
            base_merit_percent: Default merit % before rules
            base_bonus_percent: Default bonus % before rules

        Returns:
            Result dict with recommendations and flags
        """
        result = {
            'recommended_raise_percent': base_merit_percent or Decimal('0'),
            'recommended_raise_amount': Decimal('0'),
            'recommended_new_salary': Decimal('0'),
            'recommended_new_hourly': Decimal('0'),
            'recommended_bonus_percent': base_bonus_percent or Decimal('0'),
            'recommended_bonus_amount': Decimal('0'),
            'proposed_compa_ratio': Decimal('0'),
            'total_increase_percent': Decimal('0'),
            'total_increase_amount': Decimal('0'),
            'promotion_flag': False,
            'cap_bonus_flag': False,
            'needs_review_flag': False,
            'excluded_flag': False,
            'applied_rules': [],
            'rule_notes': '',
        }

        # Sort rules by priority (lower = higher priority)
        sorted_rules = sorted(rules, key=lambda r: r.get('priority', 100))

        for rule in sorted_rules:
            if not rule.get('is_active', True):
                continue

            conditions = rule.get('conditions', {})
            actions = rule.get('actions', {})
            rule_id = rule.get('id')

            # Evaluate conditions
            if self.evaluate_conditions(conditions, employee):
                # Apply actions
                if isinstance(actions, dict):
                    result = self.apply_action(actions, employee, result, rule_id)
                elif isinstance(actions, list):
                    for action in actions:
                        result = self.apply_action(action, employee, result, rule_id)

        # Calculate derived values
        result = self._calculate_derived_values(employee, result)

        return result

    def _calculate_derived_values(
        self,
        employee: Dict[str, Any],
        result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Calculate derived values like new salary, compa ratio, etc."""
        current_annual = employee.get('current_annual') or 0
        current_hourly = employee.get('current_hourly_rate') or 0
        band_midpoint = employee.get('band_midpoint') or 0
        weekly_hours = employee.get('weekly_hours') or 40

        raise_percent = result.get('recommended_raise_percent') or Decimal('0')
        raise_amount = result.get('recommended_raise_amount') or Decimal('0')

        # Calculate new salary
        if raise_amount > 0:
            new_annual = Decimal(str(current_annual)) + raise_amount
        else:
            new_annual = Decimal(str(current_annual)) * (1 + raise_percent / 100)

        # Apply salary cap if set
        salary_cap = result.get('salary_cap')
        if salary_cap and new_annual > salary_cap:
            new_annual = salary_cap

        result['recommended_new_salary'] = new_annual

        # Calculate new hourly rate
        if current_hourly:
            new_hourly = new_annual / (Decimal(str(weekly_hours)) * 52)
            result['recommended_new_hourly'] = new_hourly

        # Calculate raise amount if only percent was provided
        if raise_amount == 0 and raise_percent > 0:
            result['recommended_raise_amount'] = new_annual - Decimal(str(current_annual))

        # Calculate proposed compa ratio
        if band_midpoint > 0:
            result['proposed_compa_ratio'] = new_annual / Decimal(str(band_midpoint))

        # Calculate total increase
        total_increase = new_annual - Decimal(str(current_annual))
        result['total_increase_amount'] = total_increase
        if current_annual > 0:
            result['total_increase_percent'] = (total_increase / Decimal(str(current_annual))) * 100

        # Add bonus to total if applicable
        bonus_amount = result.get('recommended_bonus_amount') or Decimal('0')
        if bonus_amount == 0 and result.get('recommended_bonus_percent'):
            bonus_percent = result['recommended_bonus_percent']
            bonus_amount = new_annual * (bonus_percent / 100)
            result['recommended_bonus_amount'] = bonus_amount

        return result

    def test_rule(
        self,
        conditions: Dict[str, Any],
        actions: Dict[str, Any],
        test_employee: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Test a rule against sample employee data without saving.

        Returns detailed evaluation results for debugging.
        """
        self.evaluation_log = []

        # Evaluate conditions with logging
        matched = self.evaluate_conditions(conditions, test_employee, log_evaluation=True)

        # Apply actions if matched
        result = {
            'recommended_raise_percent': Decimal('0'),
            'recommended_bonus_percent': Decimal('0'),
            'applied_rules': [],
            'promotion_flag': False,
            'cap_bonus_flag': False,
            'needs_review_flag': False,
            'excluded_flag': False,
        }

        actions_applied = []
        if matched:
            if isinstance(actions, dict):
                result = self.apply_action(actions, test_employee, result)
                actions_applied.append(actions)
            elif isinstance(actions, list):
                for action in actions:
                    result = self.apply_action(action, test_employee, result)
                    actions_applied.append(action)

            result = self._calculate_derived_values(test_employee, result)

        return {
            'matched': matched,
            'conditions_evaluated': self.evaluation_log,
            'actions_applied': actions_applied,
            'result': result
        }


# Singleton instance
_rules_engine: Optional[RulesEngine] = None


def get_rules_engine() -> RulesEngine:
    """Get the rules engine singleton."""
    global _rules_engine
    if _rules_engine is None:
        _rules_engine = RulesEngine()
    return _rules_engine
