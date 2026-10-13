"""
Data models for the CentrAlign mock company application.
Provides Pydantic schemas for Invoices, Expenses, Contacts, and Tasks.
"""

from __future__ import annotations

from typing import Any
from pydantic import BaseModel, Field, ConfigDict


class InvoiceItem(BaseModel):
    """Line item for an invoice."""

    model_config = ConfigDict(extra="ignore")

    description: str = Field(..., description="Description of the product or service")
    quantity: int = Field(default=1, ge=1, description="Quantity of units")
    unit_price: float = Field(..., ge=0.0, description="Unit price in invoice currency")
    total: float = Field(..., ge=0.0, description="Line item total (quantity * unit_price)")


class Invoice(BaseModel):
    """Vendor invoice model."""

    model_config = ConfigDict(extra="ignore")

    id: str = Field(..., description="Unique invoice identifier (e.g., INV-001)")
    vendor_name: str = Field(..., description="Name of the billing vendor")
    invoice_number: str = Field(..., description="External vendor invoice number")
    amount: float = Field(..., ge=0.0, description="Total invoice amount")
    currency: str = Field(default="USD", description="Currency ISO code (e.g. USD, EUR)")
    due_date: str = Field(..., description="Due date in YYYY-MM-DD format")
    status: str = Field(
        default="pending",
        description="Payment status: pending, paid, overdue, or approved",
    )
    items: list[InvoiceItem] = Field(
        default_factory=list, description="Detailed line items on the invoice"
    )
    created_at: str = Field(..., description="Timestamp when invoice was recorded")


class ExpenseEntry(BaseModel):
    """Company expense entry record."""

    model_config = ConfigDict(extra="ignore")

    id: str = Field(..., description="Unique expense identifier (e.g., EXP-001)")
    description: str = Field(..., description="Purpose or description of the expense")
    amount: float = Field(..., ge=0.0, description="Expense amount in USD")
    category: str = Field(..., description="Expense category (e.g., Software, Travel, Office Supplies)")
    invoice_ref: str | None = Field(
        default=None, description="Optional invoice number or identifier reference"
    )
    created_by: str = Field(..., description="User or agent identifier who recorded the expense")
    created_at: str = Field(..., description="Timestamp when the expense was submitted")
    status: str = Field(
        default="pending",
        description="Expense approval status: pending, approved, or rejected",
    )


class ExpenseCreate(BaseModel):
    """Payload schema for creating a new expense entry."""

    model_config = ConfigDict(extra="ignore")

    description: str = Field(..., min_length=1, description="Purpose of the expense")
    amount: float = Field(..., gt=0.0, description="Amount must be greater than zero")
    category: str = Field(..., min_length=1, description="Expense category")
    invoice_ref: str | None = Field(default=None, description="Optional associated invoice ID/number")
    created_by: str = Field(default="ai-worker@centralign.io", description="Author identifier")


class Contact(BaseModel):
    """Contact entry for company employees, vendors, or partners."""

    model_config = ConfigDict(extra="ignore")

    id: str = Field(..., description="Unique contact identifier (e.g., CNT-001)")
    name: str = Field(..., description="Full name of the contact")
    email: str = Field(..., description="Email address")
    company: str = Field(..., description="Company name")
    role: str = Field(..., description="Job role or title")


class TaskItem(BaseModel):
    """Internal task item for operations and workflow tracking."""

    model_config = ConfigDict(extra="ignore")

    id: str = Field(..., description="Unique task identifier (e.g., TSK-001)")
    title: str = Field(..., description="Short task title")
    description: str = Field(..., description="Detailed task requirements or instructions")
    status: str = Field(
        default="todo",
        description="Task status: todo, in_progress, done, or blocked",
    )
    assigned_to: str = Field(..., description="Email or identifier of assignee")
    priority: str = Field(
        default="medium",
        description="Priority: low, medium, high, or urgent",
    )
    created_at: str = Field(..., description="Creation ISO timestamp")
    updated_at: str = Field(..., description="Last update ISO timestamp")


class TaskUpdate(BaseModel):
    """Payload schema for updating a task item via API."""

    model_config = ConfigDict(extra="ignore")

    status: str | None = Field(default=None, description="Updated status")
    title: str | None = Field(default=None, description="Updated title")
    description: str | None = Field(default=None, description="Updated description")
    assigned_to: str | None = Field(default=None, description="Updated assignee")
    priority: str | None = Field(default=None, description="Updated priority")
