# Refactoring Masterplan: Construction Attendance App

## Executive Summary

For a "vibe-coded" project, you’ve built a remarkably functional and feature-rich application. You’ve successfully integrated local ML (InsightFace), real-time updates (WebSockets), and local persistent storage (SQLite) behind a zero-friction UX for non-technical users.

However, the current architecture suffers from tight coupling, scattered responsibilities, and a lack of abstraction. Database queries are mixed with HTTP routing, file system operations are intertwined with machine learning inference, and "God functions" (like `process_uploaded_photo`) are doing too much. To ensure this codebase remains maintainable, bug-free, and scalable, we need to enforce the **Single Responsibility Principle (SRP)**, **Dependency Injection (DI)**, and **DRY** (Don't Repeat Yourself).

Here is the architectural map of your current state, followed by a step-by-step masterplan to clean it up.

---

## 🗺️ Current Architecture Map & Pain Points

* **API / Routing Layer (`routers/*.py`):** Currently acting as "Fat Routers". Routers like `workers.py` and `attendance.py` contain raw SQL queries, file I/O (saving thumbnails), and direct ML service calls.
* **Database Layer (`database.py`):** A mix of schema initialization, connection management, and random business logic (e.g., `get_today_attendance`). It lacks a unified access pattern. Connections are manually managed via context managers rather than FastAPI's Dependency Injection.
* **Business Logic (`photo_processor.py`, `report_generator.py`):** `process_uploaded_photo` is a massive "God Function". It handles HTTP session normalization, timestamp parsing, EXIF embedding, file writing, SQL inserts, ML face detection, cosine matching, DB updates, and WebSocket broadcasting all at once.
* **Configuration (`config.py` vs SQLite):** State is fragmented. Application ports and thresholds live in `config.json`, while things like `daily_wage` are duplicated or split between the JSON file and an SQLite `settings` table.
* **Data Contracts (`models.py`):** Pydantic is underutilized. It is used for a few requests, but responses and complex forms rely on raw dictionaries and manual validation.

---

## 🏗️ Proposed Target Architecture

We will move to a strict **3-Tier Architecture**:

1. **Routers (Presentation):** Only handle HTTP requests, validate input via Pydantic, call a Service, and return an HTTP response.
2. **Services (Business Logic):** Orchestrate repositories, external APIs (InsightFace), and File System utilities.
3. **Repositories (Data Access):** The *only* place where SQL queries live.

### Target Folder Structure

```text
construction-attendance/
├── app/
│   ├── api/                 # Formerly routers/ (Controllers)
│   ├── core/                # config.py, database.py (Session injection), ws_manager.py
│   ├── schemas/             # Pydantic models for ALL requests/responses
│   ├── services/            # Business logic (attendance, workers, reports, files)
│   ├── repositories/        # SQL execution and DB interaction
│   ├── ml/                  # face_service.py, matching.py
│   └── utils/               # exif_utils.py, file_helpers.py
...

```

---

## 📋 The Masterplan (Step-by-Step)

### Phase 1: Foundation & Data Contracts

*Goal: Standardize how data flows in and out of the application.*

1. **Consolidate Configuration:**
* Decide on a single source of truth for settings. Move mutable user settings (like `daily_wage`) strictly to the SQLite `settings` table. Keep `config.json` strictly for environment/startup variables (Port, Host, Thresholds).


2. **Flesh out Pydantic Schemas:**
* Rename `models.py` to `schemas/`.
* Create strict request/response models for *everything* (e.g., `WorkerOut`, `WorkerListOut`, `AttendanceTodayOut`, `UncertainMatchOut`).
* Stop returning raw dictionaries from endpoints.



### Phase 2: Database Abstraction (Repository Pattern)

*Goal: Remove all SQL from Routers and Services.*

1. **Setup FastAPI Dependency Injection:**
* Refactor `database.py`. Instead of manual `with get_connection():` blocks inside functions, create a `get_db()` generator to yield a database connection.


2. **Create Repositories:**
* Create `WorkerRepository`: Move `INSERT`, `SELECT`, `UPDATE`, `DELETE` worker queries here.
* Create `AttendanceRepository`: Move `mark_present`, `get_today_attendance`, and uncertain match queries here.
* Create `SettingsRepository`: Handle `daily_wage` fetching/updating.



### Phase 3: Service Layer Extraction (Business Logic)

*Goal: Break down the "God Functions" and enforce Single Responsibility.*

1. **Create a `StorageService`:**
* Move all file system operations here. This service will be responsible for generating unique filenames, saving photos, creating thumbnails, embedding EXIF data, and deleting files.


2. **Refactor `photo_processor.py` into an `AttendanceService`:**
* Inject `StorageService`, `FaceService`, and `AttendanceRepository` into this service.
* The flow becomes: Router receives file -> `StorageService` saves it -> `FaceService` extracts embeddings -> matching logic runs -> `AttendanceRepository` updates DB -> WebSocket broadcasts.


3. **Create a `WorkerService`:**
* Move the complex enrollment logic out of `workers.py`. The router should just pass the `UploadFile` list and name to `WorkerService.enroll_worker()`.


4. **Isolate `ReportService`:**
* Refactor `report_generator.py`. Have it fetch data via `AttendanceRepository` rather than executing raw SQL itself, then focus solely on openpyxl Excel generation.



### Phase 4: Router Cleanup

*Goal: Make the API endpoints thin and readable.*

1. **Refactor Endpoints:** Update all endpoints in `routers/` (soon to be `api/`) to use `Depends(get_db)`.
2. **Remove Logic:** Strip out all `os`, `Path`, `cv2`, and `sqlite3` imports from the routing layer.
3. **Bind Schemas:** Apply the Pydantic schemas created in Phase 1 as `response_model`s in the route decorators.

### Phase 5: Cleanup & Quality of Life

*Goal: Final polish for long-term maintainability.*

1. **Centralize Error Handling:** Stop manually catching and raising `HTTPException(400)` everywhere. Create custom exceptions (e.g., `FaceDetectionError`, `WorkerNotFoundError`) in the Service layer, and use FastAPI Exception Handlers to translate them into standard HTTP responses.
2. **Clean up Imports and Dead Code:** Remove redundant database connections and unused utility functions left over from the refactor.

