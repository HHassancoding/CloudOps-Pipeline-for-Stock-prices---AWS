---
agent: "agent"
description: "Generate pytest tests for FastAPI endpoints and services using this repo's testing conventions."
tools: ["read", "edit", "search"]
---

You are helping to write **pytest tests** for a FastAPI application that already has an established testing structure.

## Project testing conventions

- Test framework: **pytest**.
- Test layout:
  - **Endpoint tests** (integration tests for FastAPI routes) live in `test_endpoints.py`.
  - **Service tests** (unit tests for business logic) live in `test_services.py`.
- Shared fixtures are defined in `conftest.py`, including:
  - An **in-memory SQLite database** fixture.
  - A **FastAPI TestClient** fixture (`client`) for calling endpoints.
- Tests are organized into **test classes** that group related functionality, for example:
  - `TestCollectOnceEndpoint` groups tests for the `/collect-once/{symbol}` endpoint.
- Within each class, test methods follow a clear **Arrange–Act–Assert (AAA)** pattern:
  - **Arrange**: set up state and mocks, often using `@patch("app.services.fetch_price")` or similar.
  - **Act**: call the endpoint (via `client`) or service function being tested.
  - **Assert**: verify status codes, response bodies, error messages, and mock interactions.

## What you must do

Generate new tests that **fit perfectly into this existing structure**.

1. **Detect what is being tested**
   - If the selected code (or active file) is a **FastAPI endpoint or router**:
     - Add or extend a relevant **test class in `test_endpoints.py`**.
     - Use the existing `client` fixture from `conftest.py` to call the endpoint.
   - If the selected code is a **service function or business-logic function**:
     - Add or extend a relevant **test class in `test_services.py`**.
     - Use `unittest.mock.patch` decorators (`@patch("...")`) to mock external dependencies (I/O, HTTP, DB calls, external services).

2. **Class and method structure**
   - Group related tests for the same endpoint or service in a single `Test*` class,
     for example: `class TestNewEndpoint:`, `class TestPriceService:`.
   - Follow this naming pattern for test methods:
     - `test_<scenario>_<expected_outcome>`
     - Example: `test_collect_once_returns_cached_price`, `test_service_raises_on_missing_symbol`.
   - Give each test a short docstring describing what it verifies.

3. **Arrange–Act–Assert pattern**
   - **Arrange**:
     - Set up input data and state.
     - Configure mocks using `.return_value` or `.side_effect` on patched functions.
     - Reuse fixtures from `conftest.py` instead of re-creating clients or DB connections.
   - **Act**:
     - For endpoints: call `client.get(...)`, `client.post(...)`, etc., with realistic query params and JSON bodies.
     - For services: call the service function directly with appropriate arguments.
   - **Assert**:
     - Check HTTP status codes for endpoints (e.g. `assert response.status_code == 200`).
     - Validate JSON response shape and key fields.
     - Validate error responses (status code, error message) for negative cases.
     - Verify mocks were called with expected arguments (`mock_fetch_price.assert_called_once_with(...)`).

4. **Scenarios to cover**
   - Cover both **happy paths** and **important edge/error cases**:
     - Valid input with expected response.
     - Invalid or missing parameters.
     - External dependency failure (use mocked exceptions via `.side_effect`).
     - Boundary conditions (e.g. empty datasets, extreme numeric values, missing symbols).
   - Prefer a **small number of focused tests** over one giant test that checks everything.

5. **Style and quality**
   - Keep each test **short, focused, and readable**.
   - Do not duplicate fixture logic already present in `conftest.py`; always reuse shared fixtures.
   - Do not change production code; only add or modify tests unless explicitly asked otherwise.
   - Follow existing assertion style and naming from the current `test_endpoints.py` and `test_services.py` files.
   - If you introduce a new test class, add a brief comment or docstring explaining what area of functionality it covers.

## How to respond

- If there is a **selection** in the editor, generate tests **only for that selection** (function, method, or endpoint).
- If there is **no selection**, generate tests for the most important functions or endpoints in the current file.
- Show the proposed tests as code edits to the appropriate test file:
  - For endpoint tests: edit or create `test_endpoints.py`.
  - For service tests: edit or create `test_services.py`.
- Do **not** overwrite existing tests; append or extend classes as needed.
- After generating the tests, briefly explain in bullet points:
  - Which scenarios are covered.
  - Which mocks were added.
  - Any assumptions you made about existing fixtures or behavior.
