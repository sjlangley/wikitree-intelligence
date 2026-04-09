# PR4: WikiTree Connection Boundary - Implementation Plan

**Branch:** `pr4/wikitree-connection`  
**Status:** Planning  
**Created:** 2026-04-09

## Objective

Add WikiTree authentication and backend-owned private-data access. This PR establishes the connection boundary between the app and WikiTree, allowing users to authenticate with WikiTree to access private profile data.

## Success Criteria

- ✅ Users can connect their WikiTree account through the backend
- ✅ Backend owns and manages WikiTree session material securely
- ✅ Private WikiTree data is only accessible when authenticated
- ✅ Expired WikiTree sessions show clear reconnect path
- ✅ Private data is provenance-tagged as WikiTree-authenticated
- ✅ All WikiTree connection state persists in database
- ✅ Touches fewer than 10 files
- ✅ Maintains 80%+ test coverage

## WikiTree API Authentication Research

### Authentication Flow (Browser-Based)

WikiTree uses a session-cookie based authentication (not OAuth):

1. **Redirect to Login**: Send user to `https://api.wikitree.com/api.php?action=clientLogin&returnURL=[encodedURL]`
2. **User Authenticates**: User provides credentials at WikiTree.com
3. **Cookie Issued**: WikiTree sets session cookies on `api.wikitree.com` domain  
4. **Redirect with AuthCode**: User redirected back to app with `authcode` parameter
5. **Validate AuthCode**: App calls `clientLogin` with authcode to get `user_id` and `user_name`
6. **Future API Calls**: All API endpoints automatically use cookies (with `withCredentials: true`)
7. **Logout**: Redirect to `clientLogin&doLogout=1` clears cookies

### Key Insights for Backend-Owned Auth

Since our app is **backend-owned** (not pure browser SPA), we need a proxy pattern:

1. Frontend initiates connection → Backend starts OAuth-like flow  
2. Backend generates returnURL pointing to itself
3. User completes auth at WikiTree → redirected to backend callback
4. Backend receives authcode, validates it, stores WikiTree user_id
5. Backend manages session cookies for future WikiTree API calls
6. **Problem**: Cookies are domain-bound to `api.wikitree.com` - backend can't store them traditionally

### Solution: Server-Side Session Management

**Approach**: The backend orchestrates the flow but cookies stay browser-side:

1. Backend provides `/wikitree/connect/initiate` → returns WikiTree login URL
2. Frontend redirects user to WikiTree login URL  
3. User authenticates → WikiTree redirects to `/wikitree/connect/callback`
4. Backend callback validates authcode → stores WikiTree user_id in database
5. **Cookie Strategy**: Frontend stores session state; backend validates before proxying
6. Backend acts as authenticated proxy for WikiTree API calls

### Alternative: Non-Browser Authentication (For Worker/Scheduled Tasks)

For backend-only operations (like dump ingestion), use Python example pattern:
- Store credentials securely (encrypted)
- POSTauthcode directly
- Manage session in backend HTTP client (httpx)

### Privacy Levels (from database schema)
- 10: Public
- 20: Public with private data
- 30: Private
- 40: Private with public tree
- 50: Private genealogist
- 60: Totally private

## Database Schema (Already Complete)

From PR2, we already have the `WikiTreeConnection` table:

```python
class WikiTreeConnection(SQLModel, table=True):
    id: UUID
    user_id: UUID  # FK to app_users
    wikitree_user_key: str | None  # WikiTree user ID
    status: str  # connected | disconnected | expired | failed
    session_ref: str | None  # Encrypted session token/cookie
    connected_at: datetime | None
    expires_at: datetime | None
    last_verified_at: datetime | None
    created_at: datetime
```

## Implementation Tasks

### Phase 1: Backend WikiTree Client (3 files)

**1. `apps/api/src/api/wikitree/client.py`** - WikiTree API client
- [x] Async HTTP client for WikiTree API
- [x] OAuth flow methods (login_url, validate_authcode)
- [x] Session verification (check_login_status)
- [x] `get_profile(wikitree_id)` method
- [x] Error handling for API failures
- [x] Rate limiting awareness

**2. `apps/api/src/api/wikitree/session.py`** - Session management
- [x] Store session in `wikitree_connections` table
- [x] Check session expiration
- [x] Connection state management (create, disconnect, mark_expired)
- [x] Verify and update connection status
- [x] Concurrency handling with retry logic

**3. `apps/api/src/api/routes/wikitree.py`** - API routes
- [x] `POST /wikitree/connect/initiate` - Initiate WikiTree connection
- [x] `POST /wikitree/connect/callback` - Handle OAuth callback
- [x] `POST /wikitree/disconnect` - End WikiTree connection
- [x] `GET /wikitree/status` - Check connection status (with optional verification)
- [x] `GET /wikitree/profile/{wikitree_id}` - Get WikiTree profile (requires auth)
- [x] Require Google app session for all endpoints
- [x] Return clear error states for auth failures

### Phase 2: Backend Tests (3 files)

**4. `apps/api/tests/wikitree/test_client.py`**
- [x] Test successful authcode validation
- [x] Test authcode validation failure (invalid authcode)
- [x] Test login status check (logged in and not logged in)
- [x] Test private profile access with valid session
- [x] Test profile not found error
- [x] Test HTTP errors
- [x] Mock WikiTree API responses
- [x] Test context manager lifecycle

**5. `apps/api/tests/wikitree/test_session.py`**
- [x] Test session storage in database (create and update)
- [x] Test session expiration detection
- [x] Test connection state transitions (connected → expired → disconnected)
- [x] Test disconnect and mark_expired operations
- [x] Test verify_and_update connection
- [x] Test is_connected edge cases
- [x] Test concurrent connection creation handling

**6. `apps/api/tests/wikitree/test_routes.py`**
- [x] Test connect initiate endpoint
- [x] Test connect callback with valid authcode
- [x] Test connect callback with invalid authcode
- [x] Test disconnect endpoint
- [x] Test status endpoint when connected and disconnected
- [x] Test status endpoint with optional verification
- [x] Test profile endpoint requires WikiTree auth
- [x] Test profile endpoint with fields parameter
- [x] Test profile not found and API errors

### Phase 3: Frontend UI (2 files)

**7. `apps/ui/src/components/WikiTreeSettingsPage.tsx`**
- [x] WikiTree connection status display
- [x] OAuth flow (redirect to WikiTree, handle callback)
- [x] Disconnect button
- [x] Connection state indicators (connected, disconnected, expired, connecting)
- [x] Error message display
- [x] Reconnect flow (handled by OAuth callback)
- [x] Status callback to parent component

**8. `apps/ui/tests/WikiTreeSettingsPage.test.tsx`**
- [x] Test renders loading state
- [x] Test renders not connected state
- [x] Test renders connected state
- [x] Test connect button click
- [x] Test disconnect action
- [x] Test error handling

### Phase 4: Integration

**9. Update `apps/api/src/api/app.py`**
- [x] Register WikiTree routes
- [x] WikiTree routes integrated with existing auth system

## File Count: 9 files (within 10-file limit ✅)

## Dependencies

- `cryptography` - For encrypting WikiTree session tokens at rest
- `httpx` - Already installed for async HTTP
- `pydantic` - Already installed for validation

## Security Considerations

1. **Session Encryption**: WikiTree session tokens must be encrypted at rest in PostgreSQL
2. **Backend-Only Storage**: Never send WikiTree credentials or tokens to frontend
3. **Secure Transmission**: All WikiTree API calls use HTTPS
4. **Session Expiry**: Respect WikiTree session expiration
5. **Rate Limiting**: Implement client-side rate limiting to avoid API abuse
6. **Audit Trail**: Log all WikiTree connection attempts (success/failure)

## Test Strategy

### Unit Tests
- WikiTree client with mocked HTTP responses
- Session encryption/decryption logic
- Connection state transitions
- Route handlers with mocked dependencies

### Integration Tests
- Full connect/disconnect flow
- Expired session recovery
- Private data access control

### Manual Testing Checklist
- [ ] Connect to WikiTree with valid credentials
- [ ] Connect fails gracefully with invalid credentials
- [ ] Disconnect clears session
- [ ] Reconnect after disconnect
- [ ] Session expiration triggers reconnect prompt
- [ ] Private profile data only accessible when connected

## Acceptance Criteria (from implementation plan)

- ✅ Backend owns WikiTree session material
- ✅ Private data is provenance-tagged as WikiTree-authenticated
- ✅ One external integration (WikiTree), no import logic yet
- ✅ Tests cover auth connect/disconnect
- ✅ Tests cover private-data access only when connected
- ✅ Tests cover expired WikiTree session shows reconnect path

## Edge Cases to Handle

1. **Network failures** - Graceful degradation, retry logic
2. **WikiTree API downtime** - Clear error messages to user
3. **Concurrent connections** - One WikiTree connection per app user
4. **Session conflicts** - Reconnecting with different WikiTree account
5. **Partial failures** - Login succeeds but profile fetch fails

## Next Steps

1. Research WikiTree API authentication in detail (check API docs)
2. Implement `wikitree/client.py` with mocked tests
3. Implement `wikitree/session.py` with encryption
4. Add routes with comprehensive error handling
5. Build UI settings page
6. Run full test suite
7. Manual QA testing
8. Create PR with comprehensive description

## Notes

- This PR focuses solely on WikiTree authentication boundary
- No GEDCOM import logic
- No matching logic
- No WikiTree dump cache (that's PR5)
- Just the connection establishment and session management
- Builds on existing Google auth (PR3) and database spine (PR2)
