---
name: source-data-model
description: Structured source system data model for the rs schema in Azure SQL Server. Used by @source-explorer and @pipeline-architect to answer questions about available tables, columns, relationships, and onboarding readiness. Includes business context for the waste management and recycling domain.
---

# Skill: source-data-model

## Purpose

Provide a structured, agent-readable reference of all source tables in the Azure SQL Server
`rs` schema. This skill is the single source of truth for source system metadata — table
definitions, column details, primary keys, foreign keys, watermark columns, and recommended
ingestion strategies.

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
| Table count | 3 (2 dimensions + 1 fact) |

---

## Domain Overview

This data model supports a **waste collection and recycling operations** platform. The core
business process is the **pickup event** — a waste collection from a customer site, performed
by a collection vehicle, with the collected load split into a recycled portion and a
landfilled portion.

Key business questions this model answers:
- How much waste is collected, and how much is diverted from landfill through recycling?
- Which customers generate the most tonnage, and which recycle the most?
- What is the **diversion rate** — the industry's most critical sustainability KPI, often
  targeted at 50% or higher?
- How do collection patterns vary by waste type (Paper, Plastic, Glass, Metal, Organic, Mixed)?
- How is the vehicle fleet utilised across depots and regions?

Industry context:
- **Weight (kg)** is the primary volume measure. All weights in this model are kilograms,
  not US tons. Divide by 1000 when a report needs to be expressed in tonnes.
- **Recycled weight** = the portion of a load diverted to recycling instead of landfill.
  Higher is better.
- **Landfill weight** = the portion sent to final disposal. `WeightKg` = `RecycledWeightKg`
  + `LandfillWeightKg`; this holds for every row in the current dataset.
- **Diversion rate** = `SUM(RecycledWeightKg) / SUM(WeightKg)`.
- **Pickup status** matters for analysis: only `Completed` pickups represent material that
  was actually collected. `Cancelled` and `Delayed` events should normally be excluded from
  tonnage measures.

---

## Data Model

### Table: DimCustomer

**Business description:** The organisations or households that contract for waste collection
services. Customers are segmented by **CustomerType** — **Commercial** (businesses, offices,
retail, hospitality), **Residential** (households), and **Industrial** (utilities,
construction, heavy manufacturing). Customer type drives service agreements, pricing, and
pickup frequency. Commercial and Industrial accounts generate higher volumes and more diverse
waste streams than Residential accounts.

| Property | Value |
|----------|-------|
| Primary key | `CustomerId` (INT, supplied by source — not an identity column) |
| Watermark column | `UpdatedAt` |
| Recommended strategy | `incremental` |
| Soft delete | `IsDeleted` (BIT) |
| Row count (current seed) | 50 |

**Columns:**

| Column | Data Type | Nullable | Business Description |
|--------|-----------|----------|----------------------|
| CustomerId | INT | No | Surrogate key. Used as FK in FactPickupEvent. |
| CustomerName | NVARCHAR(200) | Yes | Legal or trading name of the customer. |
| CustomerType | NVARCHAR(50) | Yes | Service segment. Observed values: **Commercial** (35 rows), **Residential** (7 rows), **Industrial** (8 rows). This is the filter column for commercial-only analysis. |
| Industry | NVARCHAR(100) | Yes | Sector of the customer. Observed values: Manufacturing, Retail, Healthcare, Hospitality, Technology, Logistics, Household, Utilities, Construction. Useful for waste-composition analysis by sector. |
| ContractType | NVARCHAR(50) | Yes | Commercial arrangement. Observed values: **Fixed** (scheduled recurring service) and **On-Demand** (called in as needed, typical for Residential). |
| City | NVARCHAR(100) | Yes | City of the customer's primary service address. |
| Region | NVARCHAR(50) | Yes | Sales/operations region. Observed values: North, South, East, West. |
| CreatedAt | DATETIME2(3) | Yes | Timestamp (UTC) when the customer record was created. |
| UpdatedAt | DATETIME2(3) | Yes | Timestamp (UTC) of the most recent update. This is the **watermark column** used by incremental extraction. |
| IsDeleted | BIT | Yes | Soft delete flag. Silver-layer transformations should filter `IsDeleted = 0`. |

---

### Table: DimVehicle

**Business description:** The collection fleet. Each pickup is performed by one vehicle.
Vehicle type determines what kind of container and customer the vehicle can service:
- **Rear Loader** — manual loading, typical for residential kerbside collection.
- **Front Loader** — services commercial front-load dumpsters; high throughput.
- **Side Loader** — automated arm, used for standardised kerbside carts.
- **Roll-Off** — carries large open containers for construction and industrial waste.
- **Compactor** — compresses waste in-vehicle to increase payload per trip.

**CapacityKg** enables utilisation analysis: comparing the weight actually collected on a
pickup against the vehicle's rated capacity shows whether the fleet is being used efficiently.

| Property | Value |
|----------|-------|
| Primary key | `VehicleId` (INT, supplied by source — not an identity column) |
| Watermark column | `UpdatedAt` |
| Recommended strategy | `incremental` |
| Soft delete | `IsDeleted` (BIT) |
| Row count (current seed) | 30 |

**Columns:**

| Column | Data Type | Nullable | Business Description |
|--------|-----------|----------|----------------------|
| VehicleId | INT | No | Surrogate key. Used as FK in FactPickupEvent. |
| VehicleNumber | NVARCHAR(50) | Yes | Fleet identifier painted on the vehicle (e.g. `TRK-001`). The operational business key. |
| VehicleType | NVARCHAR(50) | Yes | Body type. Observed values: Rear Loader, Front Loader, Side Loader, Roll-Off, Compactor. |
| CapacityKg | INT | Yes | Rated payload capacity in kilograms. Observed range 8,000–18,000. Used for utilisation analysis against `FactPickupEvent.WeightKg`. |
| DepotCity | NVARCHAR(100) | Yes | Depot the vehicle operates out of. Drives route planning and fuel cost analysis. |
| Region | NVARCHAR(50) | Yes | Operating region. Observed values: North, South, East, West. |
| CreatedAt | DATETIME2(3) | Yes | Timestamp (UTC) when the vehicle record was created. |
| UpdatedAt | DATETIME2(3) | Yes | Timestamp (UTC) of the most recent update. **Watermark column**. |
| IsDeleted | BIT | Yes | Soft delete flag — a retired or sold vehicle. |

---

### Table: FactPickupEvent

**Business description:** The central fact table recording every waste collection event. Each
row is a single pickup — one vehicle visiting one customer, collecting one waste type, with
the load weighed and split into recycled and landfilled portions. This is the transactional
heart of the model and the source of all operational and sustainability metrics.

Key business metrics derived from this table:
- **Diversion rate** = `SUM(RecycledWeightKg) / SUM(WeightKg)` — the percentage of collected
  material diverted from landfill. The most important sustainability KPI in waste management.
- **Total tonnage** = `SUM(WeightKg) / 1000` — convert kilograms to tonnes for reporting.
- **Tonnage per customer** = `SUM(WeightKg) GROUP BY CustomerId` — identifies high-volume
  accounts for pricing and service optimisation.
- **Vehicle utilisation** = `WeightKg` compared against `DimVehicle.CapacityKg` — shows
  whether vehicles are running full or partly empty.
- **Completion rate** = share of pickups with `PickupStatus = 'Completed'` — an SLA measure.

| Property | Value |
|----------|-------|
| Primary key | `PickupId` (INT, supplied by source — not an identity column) |
| Watermark column | `UpdatedAt` |
| Recommended strategy | `incremental` |
| Soft delete | `IsDeleted` (BIT) |
| Grain | One row per pickup event |
| Row count (current seed) | 1000 |

**Columns:**

| Column | Data Type | Nullable | Business Description |
|--------|-----------|----------|----------------------|
| PickupId | INT | No | Surrogate key for the pickup event. |
| CustomerId | INT | Yes | FK → DimCustomer.CustomerId. Join for customer name, type, industry and region. |
| VehicleId | INT | Yes | FK → DimVehicle.VehicleId. Join for vehicle type, capacity and depot. |
| PickupDate | DATE | Yes | Calendar date the collection occurred. Primary time dimension for daily/weekly/monthly reporting. |
| WasteType | NVARCHAR(50) | Yes | Material collected. Observed values: Paper, Plastic, Glass, Metal, Organic, Mixed. Enables waste-composition and stream-level diversion analysis. |
| WeightKg | FLOAT | Yes | **Total weight collected in kilograms.** The primary volume measure. Equals `RecycledWeightKg + LandfillWeightKg`. |
| RecycledWeightKg | FLOAT | Yes | **Weight diverted to recycling, in kilograms.** Numerator of the diversion rate — the single most important sustainability measure in the dataset. |
| LandfillWeightKg | FLOAT | Yes | **Weight sent to landfill, in kilograms.** The figure every sustainability programme aims to minimise. |
| PickupStatus | NVARCHAR(50) | Yes | Outcome of the scheduled pickup. Observed values: **Completed** (800 rows), **Delayed** (100 rows), **Cancelled** (100 rows). Tonnage measures should normally filter to `Completed` — cancelled pickups collected nothing. |
| CreatedAt | DATETIME2(3) | Yes | Timestamp (UTC) when the pickup record was created. |
| UpdatedAt | DATETIME2(3) | Yes | Timestamp (UTC) of the most recent update. **Watermark column**. |
| IsDeleted | BIT | Yes | Soft delete flag — a voided ticket or corrected duplicate. Filter `IsDeleted = 0` to avoid double-counting tonnage. |

**Foreign Keys:**

| FK Column | References | Relationship | Business Meaning |
|-----------|------------|-------------|------------------|
| CustomerId | DimCustomer.CustomerId | Many-to-one | Each pickup serves one customer account; a customer has many pickups over time. |
| VehicleId | DimVehicle.VehicleId | Many-to-one | Each pickup was performed by one vehicle; a vehicle performs many pickups. |

**Measures and Suggested Aggregations:**

| Measure | Description | Typical Aggregation | Business Use |
|---------|-------------|---------------------|--------------|
| WeightKg | Total weight collected | SUM | Volume analysis, cost per tonne, tonnage per customer |
| RecycledWeightKg | Weight diverted to recycling | SUM | Diversion rate numerator |
| LandfillWeightKg | Weight sent to landfill | SUM | Landfill exposure and tipping-fee cost estimation |
| PickupId | Number of pickup events | COUNT | Service frequency, SLA monitoring |
| CapacityKg (via DimVehicle) | Rated vehicle payload | AVG / MAX | Fleet utilisation against actual collected weight |

**Suggested Gold-layer models:**

| Model | Dimensions | Measures | Business Question |
|-------|------------|----------|-------------------|
| Top commercial customers | CustomerName (CustomerType = 'Commercial') | SUM(RecycledWeightKg), SUM(WeightKg), diversion rate | Who are our top commercial customers by recycled tonnage? |
| Daily operations summary | PickupDate | SUM(WeightKg), SUM(RecycledWeightKg), COUNT(*) | How much did we collect, and what was the daily diversion rate? |
| Waste composition | WasteType | SUM(WeightKg), diversion rate | Which material streams offer the best diversion opportunity? |
| Vehicle utilisation | VehicleType, DepotCity | AVG(WeightKg), AVG(WeightKg / CapacityKg) | Are our vehicles running full? Which depots are underutilised? |
| Regional performance | Region | SUM(WeightKg), diversion rate | Which regions divert the most from landfill? |

---

## Relationship Summary

```
DimCustomer ──┐
              ├──── FactPickupEvent
DimVehicle ───┘
```

Both dimensions join to the fact table via surrogate integer keys.
The fact table is the only table with foreign key dependencies.
The two dimension tables have no dependencies on each other.

---

## Onboarding Dependency Order

Because FactPickupEvent has foreign keys to both dimensions, the recommended sequence is:

1. **DimCustomer, DimVehicle** — independent; onboard in any order, or batch them with
   `@multi-table-onboarding`
2. **FactPickupEvent** — onboard after the dimensions are in place

This ordering is a recommendation for data integrity in Gold-layer joins. Bronze ingestion
itself has no FK enforcement — tables can technically be onboarded in any order.

---

## Common Domain Terminology

| Term | Definition |
|------|------------|
| **Diversion rate** | Percentage of collected waste diverted from landfill. Calculated as `SUM(RecycledWeightKg) / SUM(WeightKg)`. Industry target: 50%+. |
| **Tipping fee** | The charge per tonne for disposing waste at a landfill. Reducing landfill weight directly reduces this cost. |
| **MRF** | Materials Recovery Facility — a recycling centre that sorts mixed recyclables into commodity streams for resale. |
| **Front-load / Rear-load** | Vehicle body types. Front loaders service commercial dumpsters; rear loaders are typical for residential collection. |
| **Roll-off** | A large open container delivered and collected by a specialised vehicle, used for construction and industrial waste. |
| **Soft delete** | A record marked logically deleted (`IsDeleted = 1`) but physically retained for audit and historical analysis. |

---

## Skill Rules

1. This skill is **read-only** — it never generates, modifies, or deletes any files.
2. This skill is the single source of truth for source schema metadata within this repository.
3. Agents reading this skill must not assume columns or relationships not documented here.
   In particular, there is **no** `GrossTons`, `RecycledTons`, `LandfilledTons`,
   `LastModifiedAt`, `CustomerCode`, `DimRoute`, `DimFacility`, or `DimMaterialType` in this
   source — weights are kilograms and the watermark is `UpdatedAt`.
4. If the source schema changes, this file must be updated before onboarding new tables.
5. Column data types listed here are Azure SQL Server types — agents generating Snowflake
   DDL or dbt models should apply standard type mappings (e.g. NVARCHAR → VARCHAR, INT →
   NUMBER, FLOAT → FLOAT, BIT → BOOLEAN, DATETIME2 → TIMESTAMP_NTZ).
6. Business descriptions are provided for developer understanding and AI agent context —
   they do not affect code generation logic.
