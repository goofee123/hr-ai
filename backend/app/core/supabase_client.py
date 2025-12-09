"""Supabase REST API Client.

This module provides a client for accessing Supabase's REST API.
Used as a fallback when direct PostgreSQL connection fails.
"""

from typing import Optional, Dict, Any, List
import httpx
from app.config import get_settings

settings = get_settings()


class SupabaseClient:
    """Client for Supabase REST API using the service role key."""

    def __init__(self):
        self.url = settings.supabase_url
        self.key = settings.supabase_service_role_key
        self.headers = {
            "apikey": self.key,
            "Authorization": f"Bearer {self.key}",
            "Content-Type": "application/json",
            "Prefer": "return=representation",
        }

    async def select(
        self,
        table: str,
        columns: str = "*",
        filters: Optional[Dict[str, Any]] = None,
        single: bool = False,
        return_empty_on_404: bool = False,
    ) -> Optional[List[Dict[str, Any]] | Dict[str, Any]]:
        """Select rows from a table.

        Args:
            table: Table name
            columns: Columns to select (default: *)
            filters: Dict of column=value filters
            single: If True, return single row or None
            return_empty_on_404: If True, return empty list/None on 404 (table not found)

        Returns:
            List of rows or single row if single=True
        """
        params = {"select": columns}

        # Build filter query params
        if filters:
            for key, value in filters.items():
                params[key] = f"eq.{value}"

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.url}/rest/v1/{table}",
                headers=self.headers,
                params=params,
                timeout=10,
            )

            # Handle 404 gracefully if table doesn't exist yet
            if response.status_code == 404 and return_empty_on_404:
                return None if single else []

            response.raise_for_status()
            data = response.json()

            if single:
                return data[0] if data else None
            return data

    async def insert(
        self,
        table: str,
        data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Insert a row into a table.

        Args:
            table: Table name
            data: Row data

        Returns:
            Inserted row
        """
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.url}/rest/v1/{table}",
                headers=self.headers,
                json=data,
                timeout=10,
            )
            response.raise_for_status()
            result = response.json()
            return result[0] if result else data

    async def update(
        self,
        table: str,
        data: Dict[str, Any],
        filters: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """Update rows in a table.

        Args:
            table: Table name
            data: Update data
            filters: Dict of column=value filters

        Returns:
            Updated row(s)
        """
        params = {}
        for key, value in filters.items():
            params[key] = f"eq.{value}"

        async with httpx.AsyncClient() as client:
            response = await client.patch(
                f"{self.url}/rest/v1/{table}",
                headers=self.headers,
                params=params,
                json=data,
                timeout=10,
            )
            response.raise_for_status()
            result = response.json()
            return result[0] if result else None

    async def delete(
        self,
        table: str,
        filters: Dict[str, Any],
    ) -> bool:
        """Delete rows from a table.

        Args:
            table: Table name
            filters: Dict of column=value filters

        Returns:
            True if successful
        """
        params = {}
        for key, value in filters.items():
            params[key] = f"eq.{value}"

        async with httpx.AsyncClient() as client:
            response = await client.delete(
                f"{self.url}/rest/v1/{table}",
                headers=self.headers,
                params=params,
                timeout=10,
            )
            response.raise_for_status()
            return True

    async def get_user_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """Get a user by email address.

        Args:
            email: User email

        Returns:
            User data or None
        """
        return await self.select(
            "users",
            "*",
            filters={"email": email, "is_active": "true"},
            single=True,
        )

    async def query(
        self,
        table: str,
        columns: str = "*",
        filters: Optional[Dict[str, Any]] = None,
        order: Optional[str] = None,
        order_desc: bool = False,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Query rows from a table with more options.

        Args:
            table: Table name
            columns: Columns to select (default: *)
            filters: Dict of column=value filters (supports 'eq.', 'in.', 'neq.' etc)
            order: Column to order by
            order_desc: If True, order descending
            limit: Max rows to return
            offset: Number of rows to skip

        Returns:
            List of rows
        """
        params = {"select": columns}

        # Build filter query params
        if filters:
            for key, value in filters.items():
                # If value already has operator prefix, use as-is
                if isinstance(value, str) and any(value.startswith(op) for op in ['eq.', 'neq.', 'in.', 'gt.', 'gte.', 'lt.', 'lte.', 'like.', 'ilike.']):
                    params[key] = value
                else:
                    params[key] = f"eq.{value}"

        if order:
            params["order"] = f"{order}.desc" if order_desc else f"{order}.asc"

        if limit:
            params["limit"] = limit

        if offset:
            params["offset"] = offset

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.url}/rest/v1/{table}",
                headers=self.headers,
                params=params,
                timeout=10,
            )
            response.raise_for_status()
            return response.json()

    async def rpc(
        self,
        function_name: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """Call a database function via RPC.

        Args:
            function_name: Name of the function
            params: Function parameters

        Returns:
            Function result
        """
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.url}/rest/v1/rpc/{function_name}",
                headers=self.headers,
                json=params or {},
                timeout=10,
            )
            response.raise_for_status()
            return response.json()


# Singleton instance
_supabase_client: Optional[SupabaseClient] = None


def get_supabase_client() -> SupabaseClient:
    """Get the Supabase client singleton."""
    global _supabase_client
    if _supabase_client is None:
        _supabase_client = SupabaseClient()
    return _supabase_client
