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

### Authentication Flow

WikiTree API uses a custom authentication mechanism:

1. **Login Method**: `login` action with `email` and `password` or `wpPassword`
2. **Session Management**: Returns a session cookie or token
3. **Private Data Access**: Requires valid authenticated session
4. **API Base URL**: `https://api.wikitree.com/api.php`

Key API actions needed:
- `login` - Authenticate user and establish session
- `logout` - End WikiTree session
- `getProfile` - Get profile data (public or private based on auth)
- `getPerson` - Get person details with privacy awareness

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
- [ ] Async HTTP client for WikiTree API
- [ ] `login(email, password)` method
- [ ] `logout(session_token)` method
- [ ] `get_profile(wikitree_id, session_token)` method
- [ ] `verify_session(session_token)` method
- [ ] Error handling for API failures
- [ ] Rate limiting awareness

**2. `apps/api/src/api/wikitree/session.py`** - Session management
- [ ] Encrypt/decrypt WikiTree session tokens at rest
- [ ] Store session in `wikitree_connections` table
- [ ] Check session expiration
- [ ] Refresh session if possible
- [ ] Tag all WikiTree data with provenance

**3. `apps/api/src/api/routes/wikitree.py`** - API routes
- [ ] `POST /wikitree/connect` - Initiate WikiTree connection
- [ ] `POST /wikitree/disconnect` - End WikiTree connection
- [ ] `GET /wikitree/status` - Check connection status
- [ ] `GET /wikitree/profile/{wikitree_id}` - Get WikiTree profile (requires auth)
- [ ] Require Google app session for all endpoints
- [ ] Return clear error states for auth failures

### Phase 2: Backend Tests (3 files)

**4. `apps/api/tests/test_wikitree_client.py`**
- [ ] Test successful login
- [ ] Test login failure (invalid credentials)
- [ ] Test logout
- [ ] Test session verification
- [ ] Test private profile access with valid session
- [ ] Test private profile access denied without session
- [ ] Mock WikiTree API responses

**5. `apps/api/tests/test_wikitree_session.py`**
- [ ] Test session encryption/decryption
- [ ] Test session storage in database
- [ ] Test session expiration detection
- [ ] Test connection state transitions (connected → expired → disconnected)

**6. `apps/api/tests/test_wikitree_routes.py`**
- [ ] Test connect endpoint with valid credentials
- [ ] Test connect endpoint with invalid credentials
- [ ] Test disconnect endpoint
- [ ] Test status endpoint when connected
- [ ] Test status endpoint when disconnected
- [ ] Test profile endpoint requires WikiTree auth
- [ ] Test profile endpoint with expired session shows reconnect

### Phase 3: Frontend UI (2 files)

**7. `apps/ui/src/pages/WikiTreeSettingsPage.tsx`**
- [ ] WikiTree connection status display
- [ ] Connect form (email/password input)
- [ ] Disconnect button
- [ ] Connection state indicators (connected, disconnected, expired, connecting)
- [ ] Error message display
- [ ] Reconnect flow for expired sessions

**8. `apps/ui/tests/WikiTreeSettingsPage.test.tsx`**
- [ ] Test renders connection status
- [ ] Test connect form submission
- [ ] Test disconnect action
- [ ] Test error handling
- [ ] Test expired session reconnect prompt

### Phase 4: Integration

**9. Update `apps/api/src/api/app.py`**
- [ ] Register WikiTree routes
- [ ] Add WikiTree connection status to startup checks

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
