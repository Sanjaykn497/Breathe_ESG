from django.db import models


class UserRole(models.TextChoices):
    ADMIN   = "ADMIN",   "Admin"
    ANALYST = "ANALYST", "Analyst"


class SourceType(models.TextChoices):
    SAP     = "SAP",     "SAP (Fuel & Procurement)"
    UTILITY = "UTILITY", "Utility (Electricity Bills)"
    TRAVEL  = "TRAVEL",  "Corporate Travel"


class EmissionScope(models.TextChoices):
    SCOPE_1 = "SCOPE_1", "Scope 1 — Direct"
    SCOPE_2 = "SCOPE_2", "Scope 2 — Indirect (Energy)"
    SCOPE_3 = "SCOPE_3", "Scope 3 — Value Chain"


class ReviewStatus(models.TextChoices):
    AUTO_APPROVED = "AUTO_APPROVED", "Auto-Approved"
    NEEDS_REVIEW  = "NEEDS_REVIEW",  "Needs Review"
    APPROVED      = "APPROVED",      "Approved"
    REJECTED      = "REJECTED",      "Rejected"
    LOCKED        = "LOCKED",        "Locked (Audited)"


class IngestionStatus(models.TextChoices):
    PENDING    = "PENDING",    "Pending"
    PROCESSING = "PROCESSING", "Processing"
    COMPLETED  = "COMPLETED",  "Completed"
    FAILED     = "FAILED",     "Failed"


class NormalizedUnit(models.TextChoices):
    KG_CO2E    = "kg_CO2e", "Kilograms CO₂-equivalent"
    TONNE_CO2E = "tCO2e",   "Metric Tonnes CO₂-equivalent"
    KWH        = "kWh",     "Kilowatt-hours"
    MJ         = "MJ",      "Megajoules"
    LITRE      = "L",       "Litres"
    KM         = "km",      "Kilometres"
    NIGHT      = "night",   "Hotel night"
