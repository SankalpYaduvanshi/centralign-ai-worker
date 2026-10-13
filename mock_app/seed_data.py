"""
Seed data generator for the CentrAlign mock company portal.
Supplies realistic initial datasets for invoices, expenses, contacts, and tasks.
"""

from __future__ import annotations

import copy
from typing import Any


def get_seed_data() -> dict[str, list[dict[str, Any]]]:
    """
    Return a fresh deep-copied dictionary of realistic seed data.

    Returns:
        Dictionary containing lists of dict records for:
        - invoices (10 realistic vendor invoices)
        - expenses (6 realistic company expense entries)
        - contacts (6 key employee/vendor contacts)
        - tasks (6 operational workflow task items)
    """
    data: dict[str, list[dict[str, Any]]] = {
        "invoices": [
            {
                "id": "inv-001",
                "vendor_name": "Acme Corp",
                "invoice_number": "INV-ACM-2024-001",
                "amount": 4500.00,
                "currency": "USD",
                "due_date": "2024-11-15",
                "status": "pending",
                "items": [
                    {
                        "description": "Cloud Dedicated Server Hosting (Oct 2024)",
                        "quantity": 1,
                        "unit_price": 2500.00,
                        "total": 2500.00,
                    },
                    {
                        "description": "Load Balancer & CDN Bandwidth Overage",
                        "quantity": 1,
                        "unit_price": 1200.00,
                        "total": 1200.00,
                    },
                    {
                        "description": "24/7 Enterprise SLA Support Tier",
                        "quantity": 1,
                        "unit_price": 800.00,
                        "total": 800.00,
                    },
                ],
                "created_at": "2024-10-01T08:30:00Z",
            },
            {
                "id": "inv-002",
                "vendor_name": "Globex Industries",
                "invoice_number": "INV-GLX-2024-089",
                "amount": 12850.00,
                "currency": "USD",
                "due_date": "2024-10-25",
                "status": "paid",
                "items": [
                    {
                        "description": "Enterprise Cybersecurity Penetration Testing",
                        "quantity": 1,
                        "unit_price": 9500.00,
                        "total": 9500.00,
                    },
                    {
                        "description": "Threat Model Assessment & Executive Briefing",
                        "quantity": 1,
                        "unit_price": 3350.00,
                        "total": 3350.00,
                    },
                ],
                "created_at": "2024-09-25T14:10:00Z",
            },
            {
                "id": "inv-003",
                "vendor_name": "Stark Solutions",
                "invoice_number": "INV-STK-2024-412",
                "amount": 28400.00,
                "currency": "USD",
                "due_date": "2024-12-01",
                "status": "pending",
                "items": [
                    {
                        "description": "High-Density AI Neural Accelerator Units (x4)",
                        "quantity": 4,
                        "unit_price": 5500.00,
                        "total": 22000.00,
                    },
                    {
                        "description": "Custom Cooling Enclosure & Rackmount Kits",
                        "quantity": 2,
                        "unit_price": 1700.00,
                        "total": 3400.00,
                    },
                    {
                        "description": "On-site Installation & Hardware Calibration",
                        "quantity": 1,
                        "unit_price": 3000.00,
                        "total": 3000.00,
                    },
                ],
                "created_at": "2024-10-08T09:15:00Z",
            },
            {
                "id": "inv-004",
                "vendor_name": "Initech LLC",
                "invoice_number": "INV-INT-2024-104",
                "amount": 1750.00,
                "currency": "USD",
                "due_date": "2024-09-30",
                "status": "overdue",
                "items": [
                    {
                        "description": "Enterprise Office Collaboration Suites (25 Seats)",
                        "quantity": 25,
                        "unit_price": 50.00,
                        "total": 1250.00,
                    },
                    {
                        "description": "Automated TPS Reporting Module Add-on",
                        "quantity": 1,
                        "unit_price": 500.00,
                        "total": 500.00,
                    },
                ],
                "created_at": "2024-09-01T11:00:00Z",
            },
            {
                "id": "inv-005",
                "vendor_name": "Cyberdyne Systems",
                "invoice_number": "INV-CYB-2024-771",
                "amount": 9200.00,
                "currency": "USD",
                "due_date": "2024-11-20",
                "status": "paid",
                "items": [
                    {
                        "description": "Autonomous Agent Pipeline Compute Cluster (Q3)",
                        "quantity": 1,
                        "unit_price": 7500.00,
                        "total": 7500.00,
                    },
                    {
                        "description": "Automated Model Telemetry Monitoring",
                        "quantity": 1,
                        "unit_price": 1700.00,
                        "total": 1700.00,
                    },
                ],
                "created_at": "2024-09-18T16:00:00Z",
            },
            {
                "id": "inv-006",
                "vendor_name": "Wayne Enterprises",
                "invoice_number": "INV-WYN-2024-303",
                "amount": 15600.00,
                "currency": "USD",
                "due_date": "2024-11-30",
                "status": "pending",
                "items": [
                    {
                        "description": "Encrypted Satellite Backup Communication Uplink",
                        "quantity": 1,
                        "unit_price": 11000.00,
                        "total": 11000.00,
                    },
                    {
                        "description": "Zero-Trust Perimeter Hardening Appliances",
                        "quantity": 2,
                        "unit_price": 2300.00,
                        "total": 4600.00,
                    },
                ],
                "created_at": "2024-10-05T10:45:00Z",
            },
            {
                "id": "inv-007",
                "vendor_name": "Umbrella Corp",
                "invoice_number": "INV-UMB-2024-512",
                "amount": 3200.00,
                "currency": "USD",
                "due_date": "2024-10-15",
                "status": "paid",
                "items": [
                    {
                        "description": "Ergonomic Wellness Program Subscriptions",
                        "quantity": 1,
                        "unit_price": 2200.00,
                        "total": 2200.00,
                    },
                    {
                        "description": "Annual Corporate Bio-Safety Screening Kits",
                        "quantity": 20,
                        "unit_price": 50.00,
                        "total": 1000.00,
                    },
                ],
                "created_at": "2024-09-15T12:00:00Z",
            },
            {
                "id": "inv-008",
                "vendor_name": "Hooli Tech",
                "invoice_number": "INV-HLI-2024-884",
                "amount": 6450.00,
                "currency": "USD",
                "due_date": "2024-09-28",
                "status": "overdue",
                "items": [
                    {
                        "description": "Middle-Out Lossless Compression SDK Enterprise",
                        "quantity": 1,
                        "unit_price": 5500.00,
                        "total": 5500.00,
                    },
                    {
                        "description": "Developer Sandbox Seats (10 Licenses)",
                        "quantity": 10,
                        "unit_price": 95.00,
                        "total": 950.00,
                    },
                ],
                "created_at": "2024-08-28T09:00:00Z",
            },
            {
                "id": "inv-009",
                "vendor_name": "Massive Dynamic",
                "invoice_number": "INV-MAS-2024-902",
                "amount": 21000.00,
                "currency": "USD",
                "due_date": "2024-12-15",
                "status": "pending",
                "items": [
                    {
                        "description": "Quantum Simulation Engine Access (Q4)",
                        "quantity": 1,
                        "unit_price": 18000.00,
                        "total": 18000.00,
                    },
                    {
                        "description": "Specialized Algorithmic Optimization Consulting",
                        "quantity": 12,
                        "unit_price": 250.00,
                        "total": 3000.00,
                    },
                ],
                "created_at": "2024-10-09T15:30:00Z",
            },
            {
                "id": "inv-010",
                "vendor_name": "Soylent Corp",
                "invoice_number": "INV-SYL-2024-118",
                "amount": 850.00,
                "currency": "USD",
                "due_date": "2024-11-05",
                "status": "paid",
                "items": [
                    {
                        "description": "HQ Pantry Smart Beverage & Snack Dispenser Restock",
                        "quantity": 1,
                        "unit_price": 850.00,
                        "total": 850.00,
                    },
                ],
                "created_at": "2024-10-02T13:20:00Z",
            },
        ],
        "expenses": [
            {
                "id": "exp-001",
                "description": "Cloud Server Hosting - AWS Infrastructure",
                "amount": 1250.00,
                "category": "Software",
                "invoice_ref": "INV-ACM-2024-001",
                "created_by": "sarah.connor@centralign.io",
                "created_at": "2024-10-01T09:30:00Z",
                "status": "approved",
            },
            {
                "id": "exp-002",
                "description": "Annual Security Penetration Testing Engagement",
                "amount": 12850.00,
                "category": "Security",
                "invoice_ref": "INV-GLX-2024-089",
                "created_by": "alex.chen@centralign.io",
                "created_at": "2024-10-03T14:15:00Z",
                "status": "approved",
            },
            {
                "id": "exp-003",
                "description": "Engineering Team Offsite Catering & Travel",
                "amount": 3450.00,
                "category": "Travel",
                "invoice_ref": None,
                "created_by": "elena.rostova@centralign.io",
                "created_at": "2024-10-05T11:00:00Z",
                "status": "pending",
            },
            {
                "id": "exp-004",
                "description": "Ergonomic Workstations for Engineering Team",
                "amount": 4800.00,
                "category": "Office Supplies",
                "invoice_ref": "INV-UMB-2024-512",
                "created_by": "david.kim@centralign.io",
                "created_at": "2024-10-08T16:45:00Z",
                "status": "approved",
            },
            {
                "id": "exp-005",
                "description": "Q4 Marketing Campaign Ad Spend & Promotion",
                "amount": 7500.00,
                "category": "Marketing",
                "invoice_ref": None,
                "created_by": "marcus.vance@centralign.io",
                "created_at": "2024-10-10T10:20:00Z",
                "status": "pending",
            },
            {
                "id": "exp-006",
                "description": "High-performance Developer Laptops & Monitors",
                "amount": 9200.00,
                "category": "Hardware",
                "invoice_ref": "INV-CYB-2024-771",
                "created_by": "sarah.connor@centralign.io",
                "created_at": "2024-10-12T13:00:00Z",
                "status": "pending",
            },
        ],
        "contacts": [
            {
                "id": "cnt-001",
                "name": "Sarah Connor",
                "email": "sarah.connor@centralign.io",
                "company": "CentrAlign AI",
                "role": "VP of Engineering",
            },
            {
                "id": "cnt-002",
                "name": "Miles Dyson",
                "email": "miles.dyson@cyberdyne.com",
                "company": "Cyberdyne Systems",
                "role": "Chief Systems Architect",
            },
            {
                "id": "cnt-003",
                "name": "Lucius Fox",
                "email": "lfox@wayneenterprises.com",
                "company": "Wayne Enterprises",
                "role": "Head of Applied Sciences",
            },
            {
                "id": "cnt-004",
                "name": "Peter Gibbons",
                "email": "pgibbons@initech.com",
                "company": "Initech LLC",
                "role": "Lead Software Engineer",
            },
            {
                "id": "cnt-005",
                "name": "Hank Scorpio",
                "email": "hscorpio@globex.com",
                "company": "Globex Industries",
                "role": "Chief Executive Officer",
            },
            {
                "id": "cnt-006",
                "name": "Pepper Potts",
                "email": "ppotts@starkindustries.com",
                "company": "Stark Solutions",
                "role": "Chief Operating Officer",
            },
        ],
        "tasks": [
            {
                "id": "tsk-001",
                "title": "Reconcile pending vendor invoices for Q4",
                "description": "Match pending invoices against received procurement purchase orders and flag discrepancies before the billing cut-off.",
                "status": "in_progress",
                "assigned_to": "sarah.connor@centralign.io",
                "priority": "high",
                "created_at": "2024-10-10T08:00:00Z",
                "updated_at": "2024-10-11T10:30:00Z",
            },
            {
                "id": "tsk-002",
                "title": "Verify Globex Industries security audit report",
                "description": "Confirm remediation steps are verified before processing the final consulting payout.",
                "status": "done",
                "assigned_to": "alex.chen@centralign.io",
                "priority": "medium",
                "created_at": "2024-10-02T09:00:00Z",
                "updated_at": "2024-10-04T17:00:00Z",
            },
            {
                "id": "tsk-003",
                "title": "Approve Stark Solutions hardware budget allocation",
                "description": "Review Stark Solutions quote for new AI acceleration cluster and route for CFO signoff.",
                "status": "todo",
                "assigned_to": "elena.rostova@centralign.io",
                "priority": "urgent",
                "created_at": "2024-10-11T11:00:00Z",
                "updated_at": "2024-10-11T11:00:00Z",
            },
            {
                "id": "tsk-004",
                "title": "Update vendor contact details for Initech account",
                "description": "Vendor billing address and primary contact email changed to pgibbons@initech.com.",
                "status": "todo",
                "assigned_to": "david.kim@centralign.io",
                "priority": "low",
                "created_at": "2024-10-09T14:20:00Z",
                "updated_at": "2024-10-09T14:20:00Z",
            },
            {
                "id": "tsk-005",
                "title": "Audit employee expense submissions for September",
                "description": "Verify travel and meals receipts comply with corporate per-diem policy.",
                "status": "in_progress",
                "assigned_to": "marcus.vance@centralign.io",
                "priority": "medium",
                "created_at": "2024-10-06T13:00:00Z",
                "updated_at": "2024-10-08T15:30:00Z",
            },
            {
                "id": "tsk-006",
                "title": "Onboard Autonomous AI Task Worker agent credentials",
                "description": "Configure internal API access tokens, run browser smoke tests, and verify end-to-end task workflow.",
                "status": "done",
                "assigned_to": "sarah.connor@centralign.io",
                "priority": "high",
                "created_at": "2024-10-01T10:00:00Z",
                "updated_at": "2024-10-02T16:00:00Z",
            },
        ],
    }
    return copy.deepcopy(data)
