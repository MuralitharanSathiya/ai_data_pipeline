---
name: source-data-model
description: Structured source system data model for the rs schema in Azure SQL Server. Used by @source-explorer agent to answer questions about available tables, columns, relationships, and onboarding readiness. Includes business context for the waste management and recycling domain.
---

# Skill: source-data-model

## Purpose

Provide a structured, agent-readable reference of all source tables in the Azure SQL Server
`rs` schema. This skill is the single source of truth for source system metadata — table
definitions, column details, primary keys, business keys, foreign keys, watermark columns,
and recommended ingestion strategies.

This skill also provides **business context** for each table and column so that developers
and agents can understand what the data represents in the waste management domain — not
just its technical structure.

This skill is read-only. It does not generate any files.

---

## Source System

| Property | Value |
|----------|-------|
| System | Azure SQL Server |
| Database | Configured in `pipeline/config.yaml` → `source.database` |
| Schema | `rs` |
| Domain | Waste management and recycling operations |
| Table count | 5 (4 dimensions + 1 fact) |

---

## Domain Overview

This data model supports a **waste collection and recycling operations** platform. The core
business process is the **pickup event** — a scheduled or on-demand waste collection from a
customer site, along a defined route, delivered to a processing facility.

Key business questions this model answers:
- How much waste is being collected, and how much is diverted from landfills through recycling?
- Which customers, routes, or facilities handle the most volume?
- What is the **diversion rate** (recycled tons ÷ gross tons) — the industry's most critical
  sustainability KPI, often targeted at 50% or higher?
- How do collection patterns vary by material stream (waste, recycling, organics, special)?
- Which service areas generate the most tonnage, and at what container sizes?

Industry context:
- **Gross tons** = total weight collected at a pickup. This is the primary volume measure.
- **Recycled tons** = weight diverted to recycling instead of landfill. Higher is better.
- **Landfilled tons** = gross tons minus recycled tons. The goal is to minimize this.
- **Container size** is measured in **cubic yards** — the standard unit in the US waste industry.
  Commercial front-load dumpsters typically range from 2 to 8 cubic yards.
- **Service frequency** (daily, weekly, on-call) drives route planning and cost optimization.
  Route efficiency — tonnage per route, fuel per stop — is a key operational metric.
- **Facility type** determines how collected material is processed: landfills for final disposal,
  transfer stations for consolidation before transport, recycling centers for material recovery.

---

## Data Model

### Table: DimCustomer

**Business description:** Represents the organizations or individuals who contract for waste
collection services. Customers are segmented by type — **Commercial** (businesses, offices,
retail), **Residential** (households, apartment complexes), and **Municipal** (government
buildings, public facilities, parks). Customer type drives service agreements, pricing models,
container sizing, and pickup frequency. Commercial accounts typically generate higher volumes
and more diverse waste streams than residential accounts. The **Industry** field applies
mainly to commercial customers and indicates sector-specific waste patterns (e.g., restaurants
produce high organic waste; warehouses produce high cardboard/packaging volumes).

| Property | Value |
|----------|-------|
| Primary key | `CustomerId` (INT, identity, surrogate) |
| Business key | `CustomerCode` (NVARCHAR(50), unique) |
| Watermark column | `LastModifiedAt` |
| Recommended strategy | `incremental` |
| Soft delete | `IsDeleted` (BIT, default 0) |

**Columns:**

| Column | Data Type | Nullable | Business Description |
|--------|-----------|----------|----------------------|
| CustomerId | INT | No | Auto-generated surrogate key. Used as FK in FactPickupEvent. Not meaningful outside the database. |
| CustomerCode | NVARCHAR(50) | No | Unique business identifier assigned to each customer — typically an alphanumeric account number from the CRM or billing system. This is the stable key used to identify a customer across systems. |
| CustomerName | NVARCHAR(200) | No | Legal or trading name of the customer. For residential accounts, this may be the property name or HOA name rather than an individual person. |
| CustomerType | NVARCHAR(50) | No | Classification of the customer's service segment. Values: **Commercial** (businesses generating trade waste), **Residential** (household waste and recycling), **Municipal** (public sector — city buildings, parks, schools). Drives pricing tiers and service level agreements. |
| Industry | NVARCHAR(100) | Yes | The customer's industry sector — applicable primarily to Commercial customers. Examples: Hospitality, Healthcare, Manufacturing, Retail, Food Services. Null for Residential and most Municipal accounts. Useful for analyzing waste composition patterns by sector. |
| City | NVARCHAR(100) | No | City where the customer's primary service address is located. Used for geographic analysis of service coverage and route planning. |
| State | NVARCHAR(2) | No | US state abbreviation (e.g., AZ, TX, CA). Combined with City for regional reporting and regulatory compliance — waste disposal regulations vary by state. |
| PostalCode | NVARCHAR(10) | Yes | ZIP or ZIP+4 code. Nullable because some legacy records may lack this field. Useful for granular geographic segmentation and mapping to census or demographic data. |
| IsDeleted | BIT | No | Soft delete flag. When set to 1, the customer account has been deactivated (closed, merged, or terminated). Silver-layer transformations should typically filter out soft-deleted records unless historical analysis is required. |
| CreatedAt | DATETIME2(3) | No | Timestamp (UTC) when the customer record was first created in the source system. Useful for tracking customer acquisition trends. |
| LastModifiedAt | DATETIME2(3) | No | Timestamp (UTC) of the most recent update to any field in this record. This is the **watermark column** — the incremental extraction pipeline uses this to detect changed records since the last ingestion run. Indexed in the source system for efficient watermark queries. |

---

### Table: DimFacility

**Business description:** Represents the physical locations where collected waste is delivered
for processing or disposal. Every pickup event ends at a facility. The three facility types
represent distinct stages in the waste processing chain:
- **Landfill**: Final disposal site where non-recyclable, non-compostable waste is buried.
  Landfills charge **tipping fees** (typically $50–$100+ per ton in the US), making landfill
  diversion a direct cost savings lever.
- **Transfer station**: A consolidation point where waste from smaller collection trucks is
  aggregated into larger long-haul vehicles for transport to a landfill or recycling center.
  Transfer stations don't process waste — they optimize logistics.
- **Recycling center** (also called MRF — Materials Recovery Facility): A facility that sorts,
  cleans, and processes recyclable materials (paper, plastics, metals, glass) for resale to
  manufacturers. Recycling center throughput directly impacts the diversion rate.

| Property | Value |
|----------|-------|
| Primary key | `FacilityId` (INT, identity, surrogate) |
| Business key | `FacilityCode` (NVARCHAR(50), unique) |
| Watermark column | `LastModifiedAt` |
| Recommended strategy | `incremental` |
| Soft delete | `IsDeleted` (BIT, default 0) |

**Columns:**

| Column | Data Type | Nullable | Business Description |
|--------|-----------|----------|----------------------|
| FacilityId | INT | No | Auto-generated surrogate key. Used as FK in FactPickupEvent. |
| FacilityCode | NVARCHAR(50) | No | Unique business identifier for the facility — typically a site code from the operations management system. Stable across system migrations. |
| FacilityName | NVARCHAR(200) | No | Human-readable name of the facility (e.g., "Eastside Recycling Center", "Metro Transfer Station #4"). |
| FacilityType | NVARCHAR(50) | No | Classification of the facility's function in the waste processing chain. Values: **Landfill** (final disposal), **Transfer** (consolidation hub), **Recycling** (materials recovery and sorting). This field is critical for calculating diversion rates — tons delivered to Recycling facilities count as diverted; tons delivered to Landfills count as disposed. |
| City | NVARCHAR(100) | No | City where the facility is located. Used for logistics analysis — proximity to collection routes affects fuel costs and turnaround time. |
| State | NVARCHAR(2) | No | US state abbreviation. Regulatory permits and environmental compliance requirements are state-specific for waste facilities. |
| IsDeleted | BIT | No | Soft delete flag. A deactivated facility (closed, decommissioned) should be excluded from active routing but retained for historical analysis. |
| CreatedAt | DATETIME2(3) | No | Timestamp (UTC) when the facility record was first created. |
| LastModifiedAt | DATETIME2(3) | No | Watermark column for incremental extraction. Indexed in the source system. |

---

### Table: DimMaterialType

**Business description:** Classifies the type of material collected during a pickup event.
Material classification drives processing decisions, pricing, regulatory reporting, and
sustainability metrics. The **StreamType** field groups materials into four operational streams:
- **Waste**: General non-recyclable solid waste destined for landfill. Also called MSW
  (Municipal Solid Waste) or "black bag" waste.
- **Recycling**: Recoverable materials — paper, cardboard, plastics (#1–#7), glass, metals
  (aluminum, steel). Collected separately or sorted at a MRF. Revenue can be generated from
  selling recovered recyclables on commodity markets.
- **Organics**: Food waste, yard waste, and compostable materials. Increasingly regulated —
  many US states now mandate organics diversion from landfill. Processed via composting or
  anaerobic digestion.
- **Special**: Hazardous waste, electronic waste (e-waste), construction & demolition (C&D)
  debris, medical waste, or other materials requiring special handling, permits, or disposal
  procedures. Higher cost per ton due to regulatory requirements.

| Property | Value |
|----------|-------|
| Primary key | `MaterialTypeId` (INT, identity, surrogate) |
| Business key | `MaterialCode` (NVARCHAR(20), unique) |
| Watermark column | `LastModifiedAt` |
| Recommended strategy | `incremental` |
| Soft delete | `IsDeleted` (BIT, default 0) |

**Columns:**

| Column | Data Type | Nullable | Business Description |
|--------|-----------|----------|----------------------|
| MaterialTypeId | INT | No | Auto-generated surrogate key. Used as FK in FactPickupEvent. |
| MaterialCode | NVARCHAR(20) | No | Short alphanumeric code identifying the material type (e.g., "MSW", "CARD", "PLAS1", "EWASTE"). Used in operational systems and on pickup tickets. |
| MaterialName | NVARCHAR(100) | No | Full descriptive name of the material (e.g., "Municipal Solid Waste", "Cardboard/OCC", "Plastic #1 PET", "Electronic Waste"). Used in reports and dashboards. |
| StreamType | NVARCHAR(50) | No | The operational waste stream this material belongs to. Values: **Waste** (landfill-bound), **Recycling** (recoverable), **Organics** (compostable/digestible), **Special** (hazardous/regulated). This is the primary grouping dimension for diversion rate calculations — Recycling + Organics = diverted; Waste + Special (usually) = disposed. |
| IsDeleted | BIT | No | Soft delete flag. Deactivated material types may represent obsolete classifications superseded by regulatory changes. |
| CreatedAt | DATETIME2(3) | No | Timestamp (UTC) when the material type record was first created. |
| LastModifiedAt | DATETIME2(3) | No | Watermark column for incremental extraction. Indexed in the source system. |

---

### Table: DimRoute

**Business description:** Represents a scheduled waste collection route — a defined sequence of
customer stops serviced by a collection vehicle. Routes are the fundamental unit of operational
planning in waste management. Efficient route design minimizes fuel consumption, maximizes
tonnage per trip, and ensures service level agreements (SLAs) are met.

- **ServiceArea** identifies the geographic zone the route covers (e.g., "Downtown Phoenix",
  "North Scottsdale Industrial", "Mesa Residential Zone 3"). Used for capacity planning and
  workload balancing across service territories.
- **ServiceFrequency** indicates how often the route runs: **Daily** (high-volume commercial
  accounts), **Weekly** (standard residential service), or **On-Call** (event-based or
  overflow pickups). Frequency directly impacts revenue per route and fleet utilization.

| Property | Value |
|----------|-------|
| Primary key | `RouteId` (INT, identity, surrogate) |
| Business key | `RouteCode` (NVARCHAR(50), unique) |
| Watermark column | `LastModifiedAt` |
| Recommended strategy | `incremental` |
| Soft delete | `IsDeleted` (BIT, default 0) |

**Columns:**

| Column | Data Type | Nullable | Business Description |
|--------|-----------|----------|----------------------|
| RouteId | INT | No | Auto-generated surrogate key. Used as FK in FactPickupEvent. |
| RouteCode | NVARCHAR(50) | No | Unique identifier for the route — typically assigned by the dispatch or fleet management system (e.g., "RT-PHX-001", "RT-MES-W12"). |
| ServiceArea | NVARCHAR(100) | No | The geographic territory or zone this route covers. Used for regional reporting, workload analysis, and service territory mapping. A single service area may have multiple routes running at different frequencies. |
| ServiceFrequency | NVARCHAR(50) | No | How often this route is scheduled to run. Values: **Daily** (Monday–Friday or 7 days, common for large commercial accounts), **Weekly** (standard residential cadence — specific day of week), **On-Call** (dispatched as needed for overflow, special events, or bulk pickups). Drives fleet scheduling and cost-per-pickup calculations. |
| IsDeleted | BIT | No | Soft delete flag. Deactivated routes may have been merged, reassigned, or eliminated due to service territory changes. |
| CreatedAt | DATETIME2(3) | No | Timestamp (UTC) when the route record was first created. |
| LastModifiedAt | DATETIME2(3) | No | Watermark column for incremental extraction. Indexed in the source system. |

---

### Table: FactPickupEvent

**Business description:** The central fact table recording every waste collection event. Each row
represents a single pickup — one truck visiting one customer location, collecting one material
type, and delivering the collected material to one facility. This is the **transactional heart**
of the data model and the source of all operational and sustainability metrics.

Key business metrics derived from this table:
- **Diversion rate** = `SUM(RecycledTons) / SUM(GrossTons)` — the percentage of collected waste
  diverted from landfill. The single most important sustainability KPI in waste management.
  Industry targets are typically 50%+, with leading programs exceeding 75%.
- **Landfill rate** = `SUM(LandfilledTons) / SUM(GrossTons)` — the inverse of diversion rate.
  Lower is better.
- **Tonnage per route** = `SUM(GrossTons) GROUP BY RouteId` — measures collection efficiency
  and helps optimize route density.
- **Tonnage per customer** = `SUM(GrossTons) GROUP BY CustomerId` — identifies high-volume
  accounts for pricing and service optimization.
- **Container utilization** = relationship between ContainerSizeYd and GrossTons — indicates
  whether containers are right-sized for the customer's waste volume.
- **Cost analysis** — when combined with external rate cards, tonnage × facility type reveals
  landfill tipping fee exposure and recycling revenue potential.

| Property | Value |
|----------|-------|
| Primary key | `PickupId` (BIGINT, identity, surrogate) |
| Business key | `PickupExternalId` (NVARCHAR(100), unique) |
| Watermark column | `LastModifiedAt` |
| Recommended strategy | `incremental` |
| Soft delete | `IsDeleted` (BIT, default 0) |
| Grain | One row per pickup event |

**Columns:**

| Column | Data Type | Nullable | Business Description |
|--------|-----------|----------|----------------------|
| PickupId | BIGINT | No | Auto-generated surrogate key. BIGINT because pickup events accumulate at high volume over time — a busy operation may record thousands of pickups per day. |
| PickupExternalId | NVARCHAR(100) | No | The business key for the pickup event — a unique identifier assigned by the upstream operational system (e.g., a ticket number, work order ID, or GPS-triggered event ID). This is the key used to match records across systems and for customer-facing references on invoices and service reports. |
| PickupDate | DATE | No | The calendar date when the collection occurred. Primary time dimension for daily, weekly, and monthly reporting. Combined with RouteId and FacilityId, this enables analysis of collection patterns and seasonal trends. |
| PickupTime | TIME | No | The time of day when the collection occurred. Enables time-of-day analysis — e.g., early morning pickups for commercial accounts before business hours, or afternoon residential runs. Also used for SLA compliance monitoring (was the pickup within the scheduled window?). |
| CustomerId | INT | No | FK → DimCustomer.CustomerId. Identifies which customer account this pickup belongs to. Join to DimCustomer for customer name, type, industry, and location details. |
| RouteId | INT | No | FK → DimRoute.RouteId. Identifies which collection route this pickup was part of. Join to DimRoute for service area and frequency. Used to calculate tonnage per route and route efficiency metrics. |
| FacilityId | INT | No | FK → DimFacility.FacilityId. Identifies which processing facility received the collected material. Join to DimFacility for facility type — this determines whether the tonnage counts as "diverted" (Recycling) or "disposed" (Landfill). Critical for diversion rate calculations. |
| MaterialTypeId | INT | No | FK → DimMaterialType.MaterialTypeId. Identifies what type of material was collected. Join to DimMaterialType for stream type (Waste, Recycling, Organics, Special). Enables waste composition analysis and stream-level diversion reporting. |
| ContainerSizeYd | DECIMAL(5,2) | Yes | The size of the collection container in **cubic yards** — the standard US industry unit for commercial waste containers. Common values: 2, 4, 6, 8 (front-load dumpsters) or 10–40 (roll-off containers for construction/demolition). Nullable because some pickups (e.g., curbside residential carts, on-call bulky pickups) may not have a standard container size recorded. Used for container utilization analysis and right-sizing recommendations. |
| GrossTons | DECIMAL(10,3) | No | **Total weight in US tons** collected at this pickup event. This is the primary volume measure in waste management — all tonnage-based KPIs (diversion rate, cost per ton, tonnage per route) start from GrossTons. Measured at the facility weigh station (scale house) upon delivery. Precision to 3 decimal places supports accuracy for smaller pickups. |
| RecycledTons | DECIMAL(10,3) | No | **Weight in US tons diverted to recycling** from this pickup. May equal GrossTons (100% recyclable load), zero (100% landfill-bound), or anything in between (mixed load sorted at facility). RecycledTons ÷ GrossTons = the pickup-level diversion rate. This is the single most important sustainability metric in the dataset. |
| LandfilledTons | DECIMAL(10,3) | No | **Computed column**: `GrossTons - RecycledTons`. Persisted (materialized) in the source database for query performance. Represents the weight that was **not** diverted — sent to landfill for final disposal. The goal of every waste management sustainability program is to minimize this number. Note: because this is a persisted computed column, it will appear in extracts as a regular column. |
| IsDeleted | BIT | No | Soft delete flag. A deleted pickup event may represent a voided ticket (duplicate entry, data correction, cancelled service). Silver-layer transformations should filter out soft-deleted rows to avoid double-counting tonnage. |
| CreatedAt | DATETIME2(3) | No | Timestamp (UTC) when the pickup record was first created — usually shortly after the collection truck returns to the facility and the weigh ticket is processed. |
| LastModifiedAt | DATETIME2(3) | No | Watermark column for incremental extraction. Updated whenever any field is corrected (e.g., weight adjustment after reweigh, facility reassignment, or data quality fix). Indexed in the source system for efficient watermark queries. |

**Foreign Keys:**

| FK Column | References | Relationship | Business Meaning |
|-----------|------------|-------------|------------------|
| CustomerId | DimCustomer.CustomerId | Many-to-one | Each pickup serves one customer account. A customer may have hundreds or thousands of pickups over time. |
| RouteId | DimRoute.RouteId | Many-to-one | Each pickup occurred on one scheduled route. A route typically includes 20–100+ stops per run. |
| FacilityId | DimFacility.FacilityId | Many-to-one | Each pickup's collected material was delivered to one facility. The facility type determines whether the tonnage is diverted or disposed. |
| MaterialTypeId | DimMaterialType.MaterialTypeId | Many-to-one | Each pickup involves one material type. If a single truck collects both waste and recycling, those are recorded as separate pickup events. |

**Measures and Suggested Aggregations:**

| Measure | Description | Typical Aggregation | Business Use |
|---------|-------------|---------------------|--------------|
| GrossTons | Total weight collected | SUM | Total volume analysis, cost-per-ton calculations, tonnage-per-route efficiency |
| RecycledTons | Weight diverted to recycling | SUM | Diversion rate numerator: `SUM(RecycledTons) / SUM(GrossTons)` |
| LandfilledTons | Weight sent to landfill (computed) | SUM | Landfill exposure analysis, tipping fee cost estimation |
| ContainerSizeYd | Container capacity | AVG or MAX | Container utilization and right-sizing analysis |
| PickupId (COUNT) | Number of pickup events | COUNT | Service frequency analysis, SLA monitoring, route density |
| PickupExternalId (COUNT DISTINCT) | Unique pickup events | COUNT DISTINCT | Deduplication verification, cross-system reconciliation |

**Suggested Gold-layer models:**

| Model | Dimensions | Measures | Business Question |
|-------|------------|----------|-------------------|
| Daily operations summary | PickupDate | SUM(GrossTons), SUM(RecycledTons), COUNT(*) | How much did we collect today? What was our daily diversion rate? |
| Customer tonnage | CustomerId, CustomerType | SUM(GrossTons), SUM(RecycledTons), diversion rate | Who are our highest-volume customers? Which customer types recycle the most? |
| Route efficiency | RouteId, ServiceArea | SUM(GrossTons), COUNT(*), AVG(GrossTons) per pickup | Which routes are most productive? Where should we add or consolidate routes? |
| Facility throughput | FacilityId, FacilityType | SUM(GrossTons), SUM(RecycledTons) | How much tonnage flows through each facility? Are recycling centers at capacity? |
| Material stream analysis | MaterialTypeId, StreamType | SUM(GrossTons), SUM(RecycledTons), diversion rate | What's our waste composition? Which streams offer the best diversion opportunity? |
| Diversion rate trend | PickupDate (monthly), StreamType | SUM(RecycledTons) / SUM(GrossTons) | Are we improving our diversion rate over time? Are we on track for our 50%+ target? |

---

## Relationship Summary

```
DimCustomer ──────┐
DimRoute ─────────┤
DimFacility ──────┼──── FactPickupEvent
DimMaterialType ──┘
```

All four dimensions join to the fact table via surrogate integer keys.
The fact table is the only table with foreign key dependencies.
Dimension tables have no dependencies on each other.

---

## Onboarding Dependency Order

Because FactPickupEvent has foreign keys to all four dimension tables, the recommended
onboarding sequence is:

1. **DimCustomer, DimFacility, DimMaterialType, DimRoute** — independent, can be onboarded in any order or batched via `@multi-table-onboarding`
2. **FactPickupEvent** — onboard after all dimensions are in place

This ordering is a recommendation for data integrity in Gold-layer joins. Bronze ingestion
itself has no FK enforcement — tables can technically be onboarded in any order.

---

## Indexes (Source System)

| Index | Table | Column | Purpose |
|-------|-------|--------|---------|
| IX_DimCustomer_LastModifiedAt | DimCustomer | LastModifiedAt | Supports watermark-based incremental extraction |
| IX_DimFacility_LastModifiedAt | DimFacility | LastModifiedAt | Supports watermark-based incremental extraction |
| IX_DimMaterial_LastModifiedAt | DimMaterialType | LastModifiedAt | Supports watermark-based incremental extraction |
| IX_DimRoute_LastModifiedAt | DimRoute | LastModifiedAt | Supports watermark-based incremental extraction |
| IX_FactPickup_LastModifiedAt | FactPickupEvent | LastModifiedAt | Supports watermark-based incremental extraction |

All tables are indexed on the watermark column, confirming that incremental extraction
is the intended and optimized strategy for every table.

---

## Common Domain Terminology

| Term | Definition |
|------|------------|
| **Diversion rate** | Percentage of collected waste diverted from landfill (via recycling, composting, or recovery). Calculated as RecycledTons ÷ GrossTons. Industry target: 50%+. |
| **Tipping fee** | The charge per ton for disposing waste at a landfill. Typically $50–$100+ in the US. Reducing landfilled tons directly reduces tipping fee costs. |
| **MRF** | Materials Recovery Facility — a recycling center that sorts mixed recyclables into commodity streams (paper, plastic, metal, glass) for resale. |
| **MSW** | Municipal Solid Waste — general household and commercial waste, as opposed to hazardous, construction, or special waste. |
| **Right-sizing** | The practice of matching container size (cubic yards) to a customer's actual waste volume to avoid overpaying for empty capacity or underpaying and causing overflows. |
| **Route density** | Number of stops or tonnage collected per route. Higher density = more efficient operations. |
| **Weigh ticket** | The official weight record produced at a facility's scale house when a collection truck delivers its load. Source of GrossTons data. |
| **Soft delete** | A record marked as logically deleted (IsDeleted = 1) but physically retained in the database for audit and historical analysis. |

---

## Skill Rules

1. This skill is **read-only** — it never generates, modifies, or deletes any files.
2. This skill is the single source of truth for source schema metadata within this repository.
3. Agents reading this skill must not assume columns or relationships not documented here.
4. If the source schema changes, this file must be updated before onboarding new tables.
5. Column data types listed here are Azure SQL Server types — agents generating Snowflake
   DDL or dbt models should apply standard type mappings (e.g., NVARCHAR → VARCHAR, INT → NUMBER).
6. Business descriptions are provided for developer understanding and AI agent context —
   they do not affect code generation logic.