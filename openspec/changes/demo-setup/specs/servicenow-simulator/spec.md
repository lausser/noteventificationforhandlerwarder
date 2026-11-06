## ADDED Requirements

### Requirement: Simulator accepts incident creation
The servicenow simulator SHALL accept POST requests to `/api/now/table/incident` with Content-Type `application/json`. It SHALL return HTTP 201 with a JSON body containing a synthetic `sys_id` (UUID) and `number` (incrementing INC prefix) in the `result` object. It SHALL log a flattened key=value representation of the payload to its log file.

#### Scenario: Normal delivery
- **WHEN** a POST with `{"short_description": "test", "description": "test desc", "cmdb_ci": "srvblub"}` is sent to `/api/now/table/incident`
- **THEN** the response SHALL have status 201 and body `{"result": {"sys_id": "<uuid>", "number": "INC<next>"}}`
- **THEN** the log SHALL contain the line matching `short_description=test description="test desc" cmdb_ci=srvblub`

### Requirement: Simulator exposes mode control
The simulator SHALL expose POST endpoints at `/mode/<mode>` that change its behavior mode. GET `/mode` SHALL return the current mode.

#### Scenario: Overloaded mode
- **WHEN** a POST is sent to `/mode/overloaded`
- **THEN** subsequent POST requests to `/api/now/table/incident` SHALL return HTTP 503 with body `{"error": "Service Unavailable"}`
- **WHEN** a POST is sent to `/mode/normal`
- **THEN** subsequent requests SHALL return HTTP 201 again

#### Scenario: Flaky mode
- **WHEN** a POST is sent to `/mode/flaky`
- **THEN** subsequent POST requests to `/api/now/table/incident` SHALL return HTTP 201 or 503 randomly with approximately 50% probability each

#### Scenario: Slow mode
- **WHEN** a POST is sent to `/mode/slow`
- **THEN** subsequent POST requests to `/api/now/table/incident` SHALL delay between 5 and 15 seconds before returning HTTP 201

### Requirement: Simulator exposes health endpoint
The simulator SHALL expose a GET `/health` endpoint that reflects current availability. It SHALL return HTTP 200 in normal mode and HTTP 503 in any failure mode (overloaded, flaky, slow).

#### Scenario: Health check in normal mode
- **WHEN** the simulator is in normal mode
- **THEN** GET `/health` SHALL return HTTP 200

#### Scenario: Health check in overloaded mode
- **WHEN** the simulator is in overloaded mode
- **THEN** GET `/health` SHALL return HTTP 503

### Requirement: Simulator renders event history
The simulator SHALL expose a GET `/events` endpoint that returns an HTML page listing all received events in reverse chronological order. Each entry SHALL show the flattened payload fields.

#### Scenario: Event history visible
- **WHEN** 3 POST requests have been sent to `/api/now/table/incident`
- **THEN** GET `/events` SHALL return HTML containing all 3 payloads as flattened key=value rows

### Requirement: Simulator registers as OMD daemon
The simulator SHALL have an init script at `etc/init.d/servicenow` following OMD conventions (PIDFILE in `tmp/run/servicenow.pid`, using `__generic_init`). It SHALL support `omd start servicenow` and `omd stop servicenow`.

#### Scenario: Start and stop
- **WHEN** `omd start servicenow` is run
- **THEN** the process SHALL be running on port 8081 and the PID file SHALL exist at `tmp/run/servicenow.pid`
- **WHEN** `omd stop servicenow` is run
- **THEN** the process SHALL terminate and the PID file SHALL be removed
