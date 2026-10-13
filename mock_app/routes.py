"""
FastAPI route definitions for the CentrAlign mock company application.
Provides both HTML web routes (rendered via Jinja2) and JSON REST API routes.
"""

from __future__ import annotations

import logging
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request, Response, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from mock_app.models import (
    Contact,
    ExpenseCreate,
    ExpenseEntry,
    Invoice,
    InvoiceItem,
    TaskItem,
    TaskUpdate,
)
from mock_app.seed_data import get_seed_data

logger = logging.getLogger(__name__)

# Set up templates directory
TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


class InMemoryStore:
    """
    In-memory data store for the CentrAlign mock application.
    Initialized from realistic seed data and supports reset operations.
    """

    def __init__(self) -> None:
        self.invoices: dict[str, Invoice] = {}
        self.expenses: dict[str, ExpenseEntry] = {}
        self.contacts: dict[str, Contact] = {}
        self.tasks: dict[str, TaskItem] = {}
        self.reset()

    def reset(self) -> None:
        """Reset the in-memory store to initial seed data."""
        raw_seed = get_seed_data()

        self.invoices.clear()
        for item in raw_seed.get("invoices", []):
            inv = Invoice(**item)
            self.invoices[inv.id.lower()] = inv

        self.expenses.clear()
        for item in raw_seed.get("expenses", []):
            exp = ExpenseEntry(**item)
            self.expenses[exp.id.lower()] = exp

        self.contacts.clear()
        for item in raw_seed.get("contacts", []):
            cnt = Contact(**item)
            self.contacts[cnt.id.lower()] = cnt

        self.tasks.clear()
        for item in raw_seed.get("tasks", []):
            tsk = TaskItem(**item)
            self.tasks[tsk.id.lower()] = tsk

        logger.info(
            "InMemoryStore initialized with %d invoices, %d expenses, %d contacts, %d tasks",
            len(self.invoices),
            len(self.expenses),
            len(self.contacts),
            len(self.tasks),
        )

    # Invoices
    def list_invoices(self, vendor: str | None = None, query: str | None = None) -> list[Invoice]:
        """List invoices, optionally filtered by vendor name or free-text query."""
        results = list(self.invoices.values())
        if vendor:
            v_low = vendor.strip().lower()
            results = [inv for inv in results if v_low in inv.vendor_name.lower()]
        if query:
            q_low = query.strip().lower()
            results = [
                inv
                for inv in results
                if q_low in inv.vendor_name.lower()
                or q_low in inv.invoice_number.lower()
                or q_low in inv.status.lower()
                or q_low in inv.id.lower()
            ]
        return results

    def get_invoice(self, invoice_id: str) -> Invoice | None:
        """Find invoice by ID or vendor invoice number."""
        target = invoice_id.strip().lower()
        if target in self.invoices:
            return self.invoices[target]
        for inv in self.invoices.values():
            if inv.invoice_number.strip().lower() == target:
                return inv
        return None

    # Expenses
    def list_expenses(self) -> list[ExpenseEntry]:
        """List all expense entries."""
        return list(self.expenses.values())

    def get_expense(self, expense_id: str) -> ExpenseEntry | None:
        """Find expense by ID."""
        return self.expenses.get(expense_id.strip().lower())

    def add_expense(self, payload: ExpenseCreate) -> ExpenseEntry:
        """Generate next ID and record a new expense entry."""
        max_num = 0
        for exp_id in self.expenses.keys():
            if exp_id.startswith("exp-"):
                try:
                    num = int(exp_id.split("-")[1])
                    max_num = max(max_num, num)
                except ValueError:
                    pass
        new_id = f"exp-{max_num + 1:03d}"
        now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        entry = ExpenseEntry(
            id=new_id,
            description=payload.description.strip(),
            amount=round(payload.amount, 2),
            category=payload.category.strip(),
            invoice_ref=payload.invoice_ref.strip() if payload.invoice_ref else None,
            created_by=payload.created_by.strip(),
            created_at=now_iso,
            status="pending",
        )
        self.expenses[entry.id.lower()] = entry
        logger.info("Recorded new expense: %s (%s)", entry.id, entry.description)
        return entry

    # Contacts
    def list_contacts(self) -> list[Contact]:
        """List all contacts in directory."""
        return list(self.contacts.values())

    def get_contact(self, contact_id: str) -> Contact | None:
        """Find contact by ID."""
        return self.contacts.get(contact_id.strip().lower())

    # Tasks
    def list_tasks(self, status_filter: str | None = None) -> list[TaskItem]:
        """List all tasks, optionally filtered by status."""
        tasks = list(self.tasks.values())
        if status_filter:
            s_low = status_filter.strip().lower()
            tasks = [t for t in tasks if t.status.lower() == s_low]
        return tasks

    def get_task(self, task_id: str) -> TaskItem | None:
        """Find task by ID."""
        return self.tasks.get(task_id.strip().lower())

    def update_task(self, task_id: str, updates: TaskUpdate) -> TaskItem | None:
        """Apply updates to an existing task item."""
        task = self.get_task(task_id)
        if not task:
            return None

        if updates.status is not None:
            task.status = updates.status.strip()
        if updates.title is not None:
            task.title = updates.title.strip()
        if updates.description is not None:
            task.description = updates.description.strip()
        if updates.assigned_to is not None:
            task.assigned_to = updates.assigned_to.strip()
        if updates.priority is not None:
            task.priority = updates.priority.strip()

        task.updated_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        logger.info("Updated task %s: status=%s", task.id, task.status)
        return task


# Global singleton store
store = InMemoryStore()

# Create FastAPI router
router = APIRouter()


async def parse_form_body(request: Request) -> dict[str, str]:
    """
    Robust form data extractor that works both with standard
    application/x-www-form-urlencoded payloads (without python-multipart)
    and multipart form data.
    """
    try:
        form = await request.form()
        return {k: str(v) for k, v in form.items()}
    except Exception:
        body = await request.body()
        parsed = urllib.parse.parse_qs(body.decode("utf-8"))
        return {k: v[0] if v else "" for k, v in parsed.items()}


# ============================================================================
# WEB HTML ROUTES
# ============================================================================


@router.get("/", response_class=HTMLResponse)
async def dashboard_page(request: Request) -> Response:
    """Dashboard page showing high-level stats, pending invoices, and active tasks."""
    invoices = store.list_invoices()
    expenses = store.list_expenses()
    tasks = store.list_tasks()
    contacts = store.list_contacts()

    pending_invoices = [inv for inv in invoices if inv.status == "pending"]
    priority_tasks = [t for t in tasks if t.status != "done"]

    stats = {
        "total_invoices": len(invoices),
        "pending_invoices": len(pending_invoices),
        "total_invoice_amount": sum(inv.amount for inv in invoices),
        "total_expenses": len(expenses),
        "total_expenses_amount": sum(exp.amount for exp in expenses),
        "pending_expenses_amount": sum(
            exp.amount for exp in expenses if exp.status == "pending"
        ),
        "active_tasks": sum(1 for t in tasks if t.status in ("todo", "in_progress")),
        "urgent_tasks": sum(
            1 for t in tasks if t.priority == "urgent" and t.status != "done"
        ),
        "done_tasks": sum(1 for t in tasks if t.status == "done"),
        "total_contacts": len(contacts),
    }

    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={
            "stats": stats,
            "pending_invoices_list": pending_invoices[:5],
            "priority_tasks_list": priority_tasks[:5],
        },
    )


@router.get("/invoices", response_class=HTMLResponse)
async def invoices_page(request: Request, q: str | None = None) -> Response:
    """Invoices directory page with search input."""
    invoices = store.list_invoices(query=q)
    return templates.TemplateResponse(
        request=request,
        name="invoices.html",
        context={
            "invoices": invoices,
            "query": q or "",
        },
    )


@router.get("/invoices/{invoice_id}", response_class=HTMLResponse)
async def invoice_detail_page(request: Request, invoice_id: str) -> Response:
    """Detailed view for a single invoice."""
    invoice = store.get_invoice(invoice_id)
    if not invoice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Invoice '{invoice_id}' not found",
        )
    return templates.TemplateResponse(
        request=request,
        name="invoice_detail.html",
        context={
            "invoice": invoice,
        },
    )


@router.get("/expenses", response_class=HTMLResponse)
async def expenses_page(request: Request) -> Response:
    """Expense list page with cumulative summary."""
    expenses = store.list_expenses()
    total_amount = sum(e.amount for e in expenses)
    return templates.TemplateResponse(
        request=request,
        name="expenses.html",
        context={
            "expenses": expenses,
            "total_amount": total_amount,
        },
    )


@router.get("/expenses/new", response_class=HTMLResponse)
async def new_expense_page(
    request: Request, invoice_ref: str | None = None
) -> Response:
    """Form to record a new company expense entry."""
    return templates.TemplateResponse(
        request=request,
        name="expense_form.html",
        context={
            "invoice_ref": invoice_ref or "",
            "created_by": "ai-worker@centralign.io",
            "error": None,
        },
    )


@router.post("/expenses/new", response_class=HTMLResponse)
async def handle_new_expense_form(request: Request) -> Response:
    """Handle new expense submission from the HTML form."""
    form_data = await parse_form_body(request)
    description = form_data.get("description", "").strip()
    amount_str = form_data.get("amount", "").strip()
    category = form_data.get("category", "").strip()
    invoice_ref = form_data.get("invoice_ref", "").strip() or None
    created_by = form_data.get("created_by", "").strip() or "ai-worker@centralign.io"

    if not description or not amount_str or not category:
        return templates.TemplateResponse(
            request=request,
            name="expense_form.html",
            context={
                "error": "Description, amount, and category are required.",
                "invoice_ref": invoice_ref or "",
                "created_by": created_by,
            },
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    try:
        amount = float(amount_str)
        if amount <= 0:
            raise ValueError("Amount must be positive.")
    except ValueError:
        return templates.TemplateResponse(
            request=request,
            name="expense_form.html",
            context={
                "error": "Please enter a valid positive numeric amount.",
                "invoice_ref": invoice_ref or "",
                "created_by": created_by,
            },
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    payload = ExpenseCreate(
        description=description,
        amount=amount,
        category=category,
        invoice_ref=invoice_ref,
        created_by=created_by,
    )
    store.add_expense(payload)

    return RedirectResponse(url="/expenses", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/contacts", response_class=HTMLResponse)
async def contacts_page(request: Request) -> Response:
    """Company contact directory page."""
    contacts = store.list_contacts()
    return templates.TemplateResponse(
        request=request,
        name="contacts.html",
        context={
            "contacts": contacts,
        },
    )


@router.get("/tasks", response_class=HTMLResponse)
async def tasks_page(request: Request) -> Response:
    """Operations task board page."""
    tasks = store.list_tasks()
    tasks_by_status: dict[str, list[TaskItem]] = {
        "todo": [t for t in tasks if t.status == "todo"],
        "in_progress": [t for t in tasks if t.status == "in_progress"],
        "done": [t for t in tasks if t.status == "done"],
    }
    return templates.TemplateResponse(
        request=request,
        name="tasks.html",
        context={
            "tasks": tasks,
            "tasks_by_status": tasks_by_status,
        },
    )


# ============================================================================
# JSON REST API ROUTES
# ============================================================================


@router.get("/api/invoices", response_model=list[Invoice])
async def api_list_invoices(vendor: str | None = None) -> list[Invoice]:
    """
    List invoices via REST API.
    Optionally filter by vendor name (?vendor=Acme).
    """
    return store.list_invoices(vendor=vendor)


@router.get("/api/invoices/{invoice_id}", response_model=Invoice)
async def api_get_invoice(invoice_id: str) -> Invoice:
    """Get single invoice details by ID or invoice number."""
    inv = store.get_invoice(invoice_id)
    if not inv:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Invoice '{invoice_id}' not found",
        )
    return inv


@router.post(
    "/api/expenses",
    response_model=ExpenseEntry,
    status_code=status.HTTP_201_CREATED,
)
async def api_create_expense(payload: ExpenseCreate) -> ExpenseEntry:
    """Create a new expense entry via JSON REST API."""
    return store.add_expense(payload)


@router.get("/api/expenses", response_model=list[ExpenseEntry])
async def api_list_expenses() -> list[ExpenseEntry]:
    """List all expense entries via REST API."""
    return store.list_expenses()


@router.get("/api/contacts", response_model=list[Contact])
async def api_list_contacts() -> list[Contact]:
    """List all contacts via REST API."""
    return store.list_contacts()


@router.get("/api/tasks", response_model=list[TaskItem])
async def api_list_tasks(status: str | None = None) -> list[TaskItem]:
    """List all tasks via REST API, optionally filtered by status."""
    return store.list_tasks(status_filter=status)


@router.patch("/api/tasks/{task_id}", response_model=TaskItem)
async def api_update_task(task_id: str, updates: TaskUpdate) -> TaskItem:
    """Update task status or other fields via PATCH."""
    updated = store.update_task(task_id, updates)
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task '{task_id}' not found",
        )
    return updated


@router.post("/api/reset")
async def api_reset_data() -> dict[str, Any]:
    """Reset the mock database back to original seed data."""
    store.reset()
    return {"message": "In-memory database reset to seed data", "success": True}


@router.get("/health")
@router.get("/api/health")
async def health_check() -> dict[str, str]:
    """Service health check endpoint."""
    return {"status": "ok", "app": "CentrAlign Internal Portal"}
