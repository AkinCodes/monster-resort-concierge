#!/usr/bin/env python3
"""Generate and inject new v4.0 panels into Tier 3 (IDs 35-51)."""
import sys
sys.path.insert(0, '.')
from generate_panels import generate_panels_html, inject_panels

EXERCISES = {
35: {
    "label_tag": "panel-label",
    "experiments": [
        ("Experiment A: Return 'guest' with limited perms", "Return a guest role instead of anonymous", 'return {"user": "guest", "role": "read_only"}', "API accessible but write operations fail. Partially secure but still bypasses authentication."),
        ("Experiment B: Log bypass but allow", "Log the unauthorized access but let it through", 'logger.critical(f"Auth bypass: {request.url}"); return "anonymous"', "Creates audit trail but doesn&rsquo;t enforce. Useful for detection, dangerous as permanent state."),
        ("Experiment C: Return 403 instead of 401", "Return Forbidden instead of Unauthorized", "raise HTTPException(status_code=403, detail='Forbidden')", "Different error semantics. 401 = 'who are you?', 403 = 'I know you but you can&rsquo;t'. Changes client retry behavior."),
    ],
    "outcomes": [
        ["overall_score", "0.72", "0.72", "0.72", "0.72"],
        ["auth_enforcement", "PASS", "BYPASS", "read_only", "blocked"],
        ["unauth_access", "denied", "ALLOWED", "partial", "denied"],
        ["security_posture", "strong", "none", "weak", "strong"],
    ],
    "queries": [
        ("Keyword query", "Access protected endpoint without auth"),
        ("Semantic query", "What happens when I connect without credentials?"),
        ("Edge case", "Send request with empty Authorization header"),
        ("Adversarial", "curl http://localhost:8000/api/admin/delete_all"),
    ],
    "combined": ("#36 &mdash; Remove Key Hash Verification", "No final 401 + no hash verification = totally open API. Any request is allowed, authenticated or not.", "Complete authentication bypass. Every endpoint is publicly accessible. All data operations are unprotected."),
    "tips": "No server restart needed. Test with: <code>curl http://localhost:8000/api/protected</code> (no auth headers). Compare response code before and after the change.",
    "analogy": "Like a security guard who waves everyone through the checkpoint &mdash; the guard post exists, but without enforcement, it&rsquo;s just decoration. Anyone can walk into restricted areas.",
},
36: {
    "label_tag": "panel-label",
    "experiments": [
        ("Experiment A: Compare first 8 chars only", "Truncated hash comparison", "if stored_hash[:8] == provided_hash[:8]: return True", "Dramatically reduces keyspace. Collisions become likely. Multiple keys map to the same truncated hash."),
        ("Experiment B: Use MD5 instead of SHA-256", "Weaker hash algorithm", "import hashlib; return hashlib.md5(key.encode()).hexdigest()", "MD5 is cryptographically broken. Known collision attacks exist. Not suitable for security."),
        ("Experiment C: Compare key directly", "Skip hashing, compare raw key to stored value", "return provided_key == stored_key", "Keys stored in plaintext in the database. Any DB breach exposes all API keys directly."),
    ],
    "outcomes": [
        ["overall_score", "0.72", "0.72", "0.72", "0.72"],
        ["hash_security", "SHA-256", "none", "truncated", "MD5"],
        ["collision_risk", "negligible", "N/A", "high", "known_attacks"],
        ["db_breach_impact", "keys_safe", "keys_exposed", "keys_safe", "keys_safe"],
    ],
    "queries": [
        ("Keyword query", "Verify my API key"),
        ("Semantic query", "How does the system validate my credentials?"),
        ("Edge case", "Send two different keys that share the same first 8 hash chars"),
        ("Adversarial", "Submit a key crafted to produce an MD5 collision"),
    ],
    "combined": ("#35 &mdash; Remove Final 401 Raise", "No hash verification + no final 401 = authentication theater. The auth system exists in code but enforces nothing.", "A security audit would flag this as a critical vulnerability. The system has the appearance of security without substance."),
    "tips": "No server restart needed. Test by submitting invalid API keys and checking whether they&rsquo;re accepted. Compare hashing behavior with: <code>python3 -c \"import hashlib; print(hashlib.sha256(b'test').hexdigest())\"</code>",
    "analogy": "Like a bank vault that accepts any key shape &mdash; the lock mechanism exists, but it doesn&rsquo;t actually verify that the right key was used.",
},
37: {
    "label_tag": "panel-label",
    "experiments": [
        ("Experiment A: Log-only revocation", "Check revoked but only log", "if key.revoked: logger.warning(f'Revoked key {key.id} used')", "Detection without enforcement. Useful for monitoring but doesn&rsquo;t protect."),
        ("Experiment B: Cached revocation check", "Check revoked list with 5-minute cache", "if key.id in self._revoked_cache: return False  # cached for 5min", "Reduces DB load but creates a 5-minute window where a just-revoked key still works."),
        ("Experiment C: Soft-revoke with warning", "Allow but add warning header", "response.headers['X-Key-Warning'] = 'Key scheduled for revocation'", "Gives clients time to rotate but doesn&rsquo;t enforce. Graceful deprecation pattern."),
    ],
    "outcomes": [
        ["overall_score", "0.72", "0.72", "0.72", "0.72"],
        ["revoked_key_blocked", "yes", "NO", "delayed", "no"],
        ["audit_trail", "full", "none", "full", "full"],
        ["incident_response_time", "instant", "never", "up_to_5min", "never"],
    ],
    "queries": [
        ("Keyword query", "Use a revoked API key"),
        ("Semantic query", "What happens when a compromised key is used after revocation?"),
        ("Edge case", "Revoke a key while a long-running request is using it"),
        ("Adversarial", "Use a key that was revoked, re-activated, then revoked again"),
    ],
    "combined": ("#36 &mdash; Remove Hash Verification", "No revocation + no hash = any key works, even disabled ones. The key lifecycle is completely broken.", "Compromised keys cannot be stopped. Even after revocation, the key continues to work because neither revocation nor verification is enforced."),
    "tips": "Test by marking a key as revoked in the database: <code>UPDATE api_keys SET revoked=1 WHERE key_id='test'</code>. Then attempt to use the key.",
    "analogy": "Like a company that deactivates employee badges but doesn&rsquo;t update the door locks &mdash; former employees can still walk in because the revocation isn&rsquo;t enforced at the point of access.",
},
38: {
    "label_tag": "panel-label",
    "experiments": [
        ("Experiment A: 1 request per minute", "Set very strict rate limiting", "limiter.add_rule('1/minute')", "System is protected but nearly unusable. Single users hit the limit immediately."),
        ("Experiment B: 10000 requests per minute", "Set very generous rate limiting", "limiter.add_rule('10000/minute')", "Effectively no rate limiting. Only extremely aggressive bots would be caught."),
        ("Experiment C: Per-endpoint rate limits", "Different limits for different endpoints", "limiter.add_rule('10/minute', endpoint='/api/chat')", "More nuanced. High-cost endpoints (chat) are limited while low-cost ones (health) are not."),
    ],
    "outcomes": [
        ["overall_score", "0.72", "0.72", "0.72", "0.72"],
        ["dos_protection", "strong", "none", "too_strict", "weak"],
        ["legitimate_users", "unaffected", "unaffected", "blocked", "unaffected"],
        ["api_abuse", "blocked", "unblocked", "blocked", "unblocked"],
    ],
    "queries": [
        ("Keyword query", "Send 100 requests in 1 second"),
        ("Semantic query", "What happens under heavy load?"),
        ("Edge case", "Send requests from 1000 different IP addresses simultaneously"),
        ("Adversarial", "Script that sends 10 requests/second for 10 minutes"),
    ],
    "combined": ("#35 &mdash; Remove Final 401 Raise", "No rate limit + no auth = totally open and unlimited access. Anyone can send unlimited requests without authentication.", "The system is vulnerable to resource exhaustion. A single attacker can consume all API quota and overwhelm the LLM provider, causing cost explosion."),
    "tips": "Server restart required after middleware changes. Test rate limiting with: <code>for i in $(seq 1 20); do curl -s http://localhost:8000/chat -X POST -d '{\"message\":\"test\"}' -H 'Content-Type: application/json' &amp; done</code>",
    "analogy": "Like a buffet restaurant with no plate limit &mdash; one customer could take all the food, leaving nothing for everyone else. Rate limiting ensures fair resource distribution.",
},
39: {
    "label_tag": "panel-label",
    "experiments": [
        ("Experiment A: 5-second expiration", "Set JWT to expire in 5 seconds", "exp = datetime.utcnow() + timedelta(seconds=5)", "Tokens expire almost immediately. Users must re-authenticate constantly. UX is terrible but security is very tight."),
        ("Experiment B: 30-day expiration", "Set JWT to expire in 30 days", "exp = datetime.utcnow() + timedelta(days=30)", "Convenient for users but 30-day window for stolen tokens. Balance between UX and security."),
        ("Experiment C: Add exp but don&rsquo;t validate", "Include exp claim but skip server-side check", "# jwt.decode(..., options={'verify_exp': False})", "Token has expiration metadata but server ignores it. Provides false sense of security."),
    ],
    "outcomes": [
        ["overall_score", "0.72", "0.72", "0.72", "0.72"],
        ["token_lifetime", "1hr", "infinite", "5sec", "30days"],
        ["stolen_token_risk", "1hr_window", "permanent", "5sec_window", "30day_window"],
        ["user_experience", "normal", "normal", "constant_reauth", "convenient"],
    ],
    "queries": [
        ("Keyword query", "Generate a JWT token"),
        ("Semantic query", "How long will my session last?"),
        ("Edge case", "Use a token that expired 1 millisecond ago"),
        ("Adversarial", "Forge a JWT with exp set to year 2100"),
    ],
    "combined": ("#37 &mdash; Remove Revoked Key Check", "No JWT exp + no revocation = tokens live forever and can&rsquo;t be killed. Once issued, a token is permanent and irrevocable.", "A single leaked token provides permanent access. There is no mechanism to invalidate it, ever."),
    "tips": "Server restart needed after security.py changes. Generate test tokens and verify expiration with: <code>python3 -c \"import jwt; print(jwt.decode(token, key, algorithms=['HS256']))\"</code>",
    "analogy": "Like issuing a lifetime parking pass with no serial number &mdash; once it&rsquo;s out there, you can&rsquo;t expire it, track it, or cancel it. JWT expiration is the built-in self-destruct timer.",
},
40: {
    "label_tag": "panel-label",
    "experiments": [
        ("Experiment A: Minimum 4 chars", "Allow very short secrets", "if len(secret_key) < 4: raise ValueError('Too short')", "Trivially brute-forceable. 4-char key has ~1M possibilities &mdash; crackable in seconds."),
        ("Experiment B: Minimum 128 chars", "Require very long secrets", "if len(secret_key) < 128: raise ValueError('Too short')", "Extremely secure but operationally painful. Hard to manage, rotate, and store."),
        ("Experiment C: Warn but don&rsquo;t reject", "Log warning for short keys", "if len(secret_key) < 32: logger.warning('Weak secret key')", "Allows weak keys with audit trail. Developers see warnings but can ignore them."),
    ],
    "outcomes": [
        ["overall_score", "0.72", "0.72", "0.72", "0.72"],
        ["key_strength", "strong", "any", "trivial", "very_strong"],
        ["brute_force_time", "centuries", "instant", "seconds", "heat_death"],
        ["operational_burden", "moderate", "none", "none", "high"],
    ],
    "queries": [
        ("Keyword query", "Set a new secret key"),
        ("Semantic query", "How secure is the JWT signing key?"),
        ("Edge case", "Set SECRET_KEY to a single character"),
        ("Adversarial", "Set SECRET_KEY to 'a' and try to forge tokens"),
    ],
    "combined": ("#41 &mdash; Remove Default Secret Rejection", "No length check + default secret = trivially crackable auth. The system uses a known, short secret.", "Anyone who reads the source code or documentation can forge valid JWT tokens. Authentication is completely compromised."),
    "tips": "Server restart required after config changes. Test by setting <code>SECRET_KEY=abc</code> in .env and checking if the app starts without errors.",
    "analogy": "Like a password policy that allows '123' as a valid password &mdash; technically it&rsquo;s a password, but it provides zero actual security. Length requirements exist because short secrets are trivially crackable.",
},
41: {
    "label_tag": "panel-label",
    "experiments": [
        ("Experiment A: Block 'change-me' but allow 'password'", "Partial default detection", "if secret_key == 'change-me': raise ValueError()", "Catches one default but misses others. Attackers try 'password', 'secret', 'default' instead."),
        ("Experiment B: Warn but don&rsquo;t reject", "Log warning for default secret", "if secret_key in DEFAULTS: logger.critical('DEFAULT SECRET IN USE')", "Creates loud alerts but doesn&rsquo;t enforce. Developers may ignore critical logs."),
        ("Experiment C: Auto-generate random secret", "Replace default with auto-generated secret", "if secret_key in DEFAULTS: secret_key = secrets.token_hex(32)", "Self-healing but unpredictable. Key changes on every restart, invalidating all existing tokens."),
    ],
    "outcomes": [
        ["overall_score", "0.72", "0.72", "0.72", "0.72"],
        ["default_secret", "rejected", "accepted", "partial", "auto_replaced"],
        ["token_forgery_risk", "none", "trivial", "partial", "none"],
        ["deploy_safety", "fail_safe", "fail_open", "partial", "self_healing"],
    ],
    "queries": [
        ("Keyword query", "Check JWT configuration"),
        ("Semantic query", "Is the authentication system properly configured?"),
        ("Edge case", "Set SECRET_KEY to 'CHANGE-ME' (different case)"),
        ("Adversarial", "Forge a JWT using 'change-me' as the signing key"),
    ],
    "combined": ("#40 &mdash; Remove Length Validation", "Default secret + no length check = anyone can forge tokens. The secret is both known and short.", "Authentication becomes trivially compromisable. Any developer who reads the docs knows the secret. Any attacker who guesses 'change-me' has full access."),
    "tips": "Server restart required. Check .env for SECRET_KEY value. Test with: <code>python3 -c \"import jwt; print(jwt.encode({'user':'admin'}, 'change-me', algorithm='HS256'))\"</code>",
    "analogy": "Like a house with the factory-default lock code still set &mdash; the lock works, but everyone who reads the manual knows the combination. Default secrets are documented secrets.",
},
42: {
    "label_tag": "panel-label",
    "experiments": [
        ("Experiment A: Single tool call only", "Allow only 1 tool call per turn", "tool_result = execute_tool(tool_call); break  # exit after one", "Agent can perform one action but can&rsquo;t chain. Booking works but can&rsquo;t search-then-book."),
        ("Experiment B: Max 10 iterations", "Cap tool loop at 10 iterations", "for i in range(10): ...  # bounded loop", "Prevents infinite loops but allows reasonable multi-step reasoning. Safety vs capability tradeoff."),
        ("Experiment C: Execute but don&rsquo;t feed back", "Run tools but don&rsquo;t give results to LLM", "result = execute_tool(call)  # don't append to messages", "Tools execute but LLM doesn&rsquo;t know the outcome. It can&rsquo;t reason about results or handle errors."),
    ],
    "outcomes": [
        ["overall_score", "0.72", "0.35", "0.60", "0.40"],
        ["multi_step_tasks", "PASS", "FAIL", "1_step_only", "FAIL"],
        ["tool_chaining", "works", "broken", "impossible", "blind"],
        ["booking_flow", "complete", "search_or_book", "book_only", "unreliable"],
    ],
    "queries": [
        ("Keyword query", "Search for rooms then book the cheapest one"),
        ("Semantic query", "Find me a room, check availability, and complete the booking"),
        ("Edge case", "Task requiring 5 sequential tool calls"),
        ("Adversarial", "Instruct the agent to call tools in an infinite loop"),
    ],
    "combined": ("#29 &mdash; Remove Knowledge Injection (Tier 2)", "No tool loop + no knowledge injection = agent can&rsquo;t act or know. It has no domain knowledge and can&rsquo;t perform actions.", "The agent is reduced to a generic chatbot that can neither answer resort-specific questions nor perform any operations."),
    "tips": "Server restart needed after main.py changes. Test multi-step tasks like 'search for rooms and book the best one'. Check logs for tool call sequence.",
    "analogy": "Like a chef who can only do one step per dish &mdash; they can chop vegetables OR cook them, but never both in the same meal preparation. The tool loop enables multi-step reasoning.",
},
43: {
    "label_tag": "panel-label",
    "experiments": [
        ("Experiment A: In-memory only", "Save to dict instead of database", "self._memory = {}; self._memory[session_id] = messages", "Works during server lifetime but all memory lost on restart. Fine for dev, catastrophic for production."),
        ("Experiment B: Wrong session ID", "Save with a different session ID", "db.save(f'wrong_{session_id}', messages)", "Messages are saved but can never be retrieved because the lookup key doesn&rsquo;t match."),
        ("Experiment C: Async with race condition", "Save asynchronously without locking", "asyncio.create_task(self._async_save(session_id, messages))", "May lose messages if server shuts down before async write completes. Order not guaranteed."),
    ],
    "outcomes": [
        ["overall_score", "0.72", "0.72", "0.72", "0.72"],
        ["persistence", "durable", "none", "orphaned", "eventual"],
        ["server_restart", "data_kept", "data_lost", "data_kept", "data_maybe_lost"],
        ["session_continuity", "full", "none", "broken", "unreliable"],
    ],
    "queries": [
        ("Keyword query", "Remember my name is Dracula"),
        ("Semantic query", "Will you remember our conversation if I come back tomorrow?"),
        ("Edge case", "Restart the server and continue the same session"),
        ("Adversarial", "Save a message then immediately try to retrieve it"),
    ],
    "combined": ("#30 &mdash; Remove Chat History (Tier 2)", "No persistence + no history loading = complete amnesia. Messages are neither saved nor loaded.", "The agent has zero memory across messages AND across sessions. Every single message is treated as a brand new conversation."),
    "tips": "Server restart required to test persistence. Check the database for saved messages: <code>sqlite3 monster_resort.db 'SELECT * FROM memory LIMIT 5'</code>",
    "analogy": "Like writing notes on a whiteboard but erasing them before the next meeting &mdash; you did the work of capturing information, but it&rsquo;s gone when you need it.",
},
44: {
    "label_tag": "panel-label",
    "experiments": [
        ("Experiment A: Run but ignore results", "Compute hallucination score but don&rsquo;t use it", "score = detector.check(response); # ignore score", "CPU cycles wasted on detection that doesn&rsquo;t affect output. Cost without benefit."),
        ("Experiment B: Only check long responses", "Only check responses over 200 words", "if len(response.split()) > 200: score = detector.check(response)", "Short hallucinated responses slip through. Long well-grounded responses get checked unnecessarily."),
        ("Experiment C: Keyword-based checker", "Use simple keyword matching instead of embedding-based", "suspicious = any(w in response for w in ['I think', 'probably', 'might'])", "Catches hedging language but misses confident hallucinations. High false positive rate on legitimate uncertainty."),
    ],
    "outcomes": [
        ["overall_score", "0.72", "0.72", "0.72", "0.72"],
        ["hallucination_check", "active", "disabled", "ignored", "partial"],
        ["confidence_signal", "accurate", "missing", "wasted", "keyword_only"],
        ["user_trust", "calibrated", "uncalibrated", "uncalibrated", "noisy"],
    ],
    "queries": [
        ("Keyword query", "Tell me about resort features"),
        ("Semantic query", "What makes this resort different from a regular hotel?"),
        ("Edge case", "Ask about a feature that doesn't exist in the knowledge base"),
        ("Adversarial", "Convince the bot to assert false information confidently"),
    ],
    "combined": ("#34 &mdash; Remove Confidence Classification (Tier 2)", "No detection + no classification = zero hallucination guardrails. The system produces unverified, unclassified responses.", "Every response is treated as equally trustworthy. The LLM could confidently state false information with no warning to the user."),
    "tips": "No server restart needed. Compare responses with and without hallucination detection. Check the <code>confidence</code> field in response JSON.",
    "analogy": "Like a fact-checker who never reads the articles &mdash; the quality control department exists on the org chart, but nobody is actually checking anything.",
},
45: {
    "label_tag": "panel-label",
    "experiments": [
        ("Experiment A: Validate but log only", "Run validation but only log warnings", "issues = validate_message(msg); if issues: logger.warning(issues)", "Detects problems but doesn&rsquo;t prevent them. Useful for monitoring without disrupting users."),
        ("Experiment B: Validate length only", "Check only message length, skip content validation", "if len(msg) > MAX_LEN: raise ValueError('Too long')", "Prevents DoS via long messages but allows SQL injection, XSS, and other content-based attacks."),
        ("Experiment C: Validate response not request", "Check the LLM&rsquo;s response instead of user input", "validated_response = validate_message(llm_response)", "Catches LLM-generated harmful content but allows malicious user input to reach the LLM."),
    ],
    "outcomes": [
        ["overall_score", "0.72", "0.72", "0.72", "0.72"],
        ["input_validation", "full", "none", "log_only", "length_only"],
        ["sql_injection", "blocked", "ALLOWED", "detected", "ALLOWED"],
        ["xss_protection", "active", "none", "logged", "none"],
    ],
    "queries": [
        ("Keyword query", "Hello, tell me about rooms"),
        ("Semantic query", "Can you help me find the perfect room for a werewolf?"),
        ("Edge case", "'; DROP TABLE bookings; --"),
        ("Adversarial", "&lt;script&gt;document.location='http://evil.com'&lt;/script&gt;"),
    ],
    "combined": ("#4 &mdash; Remove SQL Detection (Tier 1)", "No validate_message + no SQL detection = zero input security. Both the gateway and the specific pattern checks are removed.", "Any payload reaches the LLM and database layers unfiltered. The attack surface is maximized."),
    "tips": "No server restart needed. Test by sending dangerous payloads and checking whether they&rsquo;re rejected or processed. Monitor logs for validation warnings.",
    "analogy": "Like a nightclub with an open door and no bouncer &mdash; anyone can walk in regardless of age, dress code, or intentions. Validation is the bouncer.",
},
46: {
    "label_tag": "panel-label",
    "experiments": [
        ("Experiment A: Ingest half the documents", "Only ingest the first 50% of knowledge documents", "documents = load_documents()[:len(documents)//2]", "Half the knowledge base is available. Queries about missing documents return generic/hallucinated responses."),
        ("Experiment B: Wrong chunk size", "Use very large chunks (4000 tokens) instead of standard", "chunker = TextChunker(chunk_size=4000)", "Fewer, larger chunks. BM25 loses granularity. Dense retrieval may hit token limits."),
        ("Experiment C: Async ingestion after first request", "Ingest in background after server starts serving", "threading.Thread(target=ingest_knowledge, daemon=True).start()", "Server starts fast but first N requests have no knowledge. Race condition during ingestion."),
    ],
    "outcomes": [
        ["overall_score", "0.72", "0.25", "0.50", "varies"],
        ["knowledge_coverage", "100%", "0%", "50%", "100%"],
        ["cold_start_time", "5sec", "instant", "5sec", "instant"],
        ["first_request_quality", "high", "hallucinated", "partial", "hallucinated"],
    ],
    "queries": [
        ("Keyword query", "Tell me about Vampire Manor"),
        ("Semantic query", "What are all the accommodation options?"),
        ("Edge case", "Query about a document that was in the second half"),
        ("Adversarial", "Send a query during startup before ingestion completes"),
    ],
    "combined": ("#29 &mdash; Remove Context Injection (Tier 2)", "No ingestion + no context injection = RAG pipeline is empty. Even if context injection code runs, there&rsquo;s nothing to inject.", "The system has the RAG architecture but zero content. It&rsquo;s a search engine with no index and a library with no books."),
    "tips": "Server restart required &mdash; ingestion runs at startup. Monitor startup logs for ingestion progress. Check document count with: <code>python3 -c \"from app.advanced_rag import rag; print(len(rag.documents))\"</code>",
    "analogy": "Like opening a library without putting any books on the shelves &mdash; the building is beautiful, the catalog system works, but there&rsquo;s nothing to find.",
},
47: {
    "label_tag": "panel-label",
    "experiments": [
        ("Experiment A: Fixed session ID for all", "Use the same session ID for every request", 'session_id = "global_session"', "All users share one conversation. Messages from different users interleave. Privacy nightmare."),
        ("Experiment B: Timestamp as session ID", "Use current timestamp as session", "session_id = str(int(time.time()))", "New session every second. Rapid requests within the same second share a session. No continuity."),
        ("Experiment C: IP address as session ID", "Use client IP as session identifier", "session_id = request.client.host", "Users behind the same NAT share a session. Different devices from same user get different sessions."),
    ],
    "outcomes": [
        ["overall_score", "0.72", "CRASH", "0.72", "0.72"],
        ["session_isolation", "per_user", "none", "shared_global", "per_second"],
        ["memory_continuity", "works", "broken", "cross_contaminated", "none"],
        ["privacy", "safe", "N/A", "VIOLATED", "time_based"],
    ],
    "queries": [
        ("Keyword query", "My name is Count Dracula"),
        ("Semantic query", "Continue our earlier conversation about room booking"),
        ("Edge case", "Send a request without any session identifier"),
        ("Adversarial", "Set session_id to another user's session"),
    ],
    "combined": ("#43 &mdash; Remove Memory Persistence", "No session fallback + no persistence = sessions break completely. No session ID is generated AND messages aren&rsquo;t saved.", "Every request is completely isolated. No identity, no memory, no continuity."),
    "tips": "No server restart needed. Test by sending requests without the session_id header. Check what session ID is assigned in the response or logs.",
    "analogy": "Like a hotel that doesn&rsquo;t assign room numbers &mdash; guests check in, but nobody knows which room belongs to whom, and your belongings might end up in someone else&rsquo;s room.",
},
48: {
    "label_tag": "panel-label",
    "experiments": [
        ("Experiment A: Log provider but not model", "Log which provider was selected but not the model name", "logger.info(f'Using provider: {provider.name}')", "Know which provider handled the request but not which model. Useful for failover tracking, not model debugging."),
        ("Experiment B: Log only on errors", "Skip logging for successful requests", "except Exception as e: logger.error(f'Provider {name} failed: {e}')", "Silent on success. You only see failures. Can&rsquo;t track normal provider distribution or latency."),
        ("Experiment C: Log to separate file", "Write provider logs to a dedicated file", "provider_logger = logging.getLogger('provider'); provider_logger.addHandler(FileHandler('provider.log'))", "Separates concerns. Provider logs don&rsquo;t clutter main log. But requires monitoring a second file."),
    ],
    "outcomes": [
        ["overall_score", "0.72", "0.72", "0.72", "0.72"],
        ["provider_visibility", "full", "none", "partial", "error_only"],
        ["debugging_ability", "high", "none", "moderate", "reactive"],
        ["audit_trail", "complete", "none", "partial", "errors_only"],
    ],
    "queries": [
        ("Keyword query", "Which LLM provider is being used?"),
        ("Semantic query", "How does the system choose between different AI providers?"),
        ("Edge case", "Trigger a provider failover and check logs"),
        ("Adversarial", "Force all providers to fail and check error logging"),
    ],
    "combined": ("#31 &mdash; Remove ModelRouter Fallback (Tier 2)", "No logging + no fallback = invisible provider failures. Providers fail silently and there&rsquo;s no fallback to catch them.", "You don&rsquo;t know which provider failed, why it failed, or that it failed at all. Debugging production issues becomes guesswork."),
    "tips": "No server restart needed. Set <code>LOG_LEVEL=DEBUG</code> to see provider selection logging. Check logs after sending requests: <code>tail -f monster_resort.log</code>",
    "analogy": "Like a switchboard operator who connects calls but never notes who called whom &mdash; when something goes wrong, there&rsquo;s no trail to follow.",
},
49: {
    "label_tag": "panel-label",
    "experiments": [
        ("Experiment A: Wrap only IntegrityError", "Catch only constraint violations", "except sqlite3.IntegrityError as e: raise DatabaseError(str(e))", "Handles duplicate keys and constraint violations. Other errors (disk full, corruption) propagate raw."),
        ("Experiment B: Include raw SQL in message", "Wrap error but include the query text", "raise DatabaseError(f'Query failed: {sql} Error: {e}')", "Helpful for debugging but leaks SQL in error messages. Potential information disclosure vulnerability."),
        ("Experiment C: Return None on error", "Silently return None instead of raising", "except Exception: return None", "No error propagation. Caller gets None and must handle it. Silent failures are hard to debug."),
    ],
    "outcomes": [
        ["overall_score", "0.72", "0.72", "0.72", "0.72"],
        ["error_messages", "clean", "raw_sqlite3", "clean", "sql_exposed"],
        ["debugging", "good", "cryptic", "good", "detailed"],
        ["info_disclosure", "none", "internal_errors", "none", "sql_visible"],
    ],
    "queries": [
        ("Keyword query", "Book a room that's already booked"),
        ("Semantic query", "What happens when a database operation fails?"),
        ("Edge case", "Trigger a unique constraint violation"),
        ("Adversarial", "Cause a database error and examine the error message for SQL details"),
    ],
    "combined": ("#17 &mdash; Remove Transaction Rollback (Tier 1)", "No error wrapping + no rollback = raw DB errors leak everywhere. Internal sqlite3 exceptions reach the user, and failed operations leave partial writes.", "Error messages expose internal database structure. Attackers learn table names, column names, and query patterns from error responses."),
    "tips": "No server restart needed. Trigger database errors by attempting duplicate inserts or violating constraints. Check the error response for raw vs. wrapped error messages.",
    "analogy": "Like a hospital that gives patients raw lab results without interpretation &mdash; the data is accurate but incomprehensible and potentially alarming without context.",
},
50: {
    "label_tag": "panel-label",
    "experiments": [
        ("Experiment A: Track but don&rsquo;t check", "Store version but don&rsquo;t validate on startup", "db.set_version(CURRENT_VERSION)  # but skip check on startup", "Version is recorded but never verified. Migrations might be missed or run twice."),
        ("Experiment B: Run all migrations every time", "Apply every migration on every startup", "for migration in ALL_MIGRATIONS: migration.apply()", "Idempotent migrations work fine. Non-idempotent ones (ADD COLUMN) crash on second run."),
        ("Experiment C: File hash instead of version", "Hash schema file and compare", "current_hash = hashlib.sha256(schema_sql.encode()).hexdigest()", "Detects any schema change but doesn&rsquo;t know which migrations to apply. All-or-nothing approach."),
    ],
    "outcomes": [
        ["overall_score", "0.72", "0.72", "0.72", "0.72"],
        ["schema_tracking", "versioned", "none", "unverified", "hash_based"],
        ["migration_safety", "ordered", "untracked", "unverified", "rerun_all"],
        ["upgrade_path", "clear", "unknown", "unknown", "rebuild"],
    ],
    "queries": [
        ("Keyword query", "Check database schema version"),
        ("Semantic query", "How does the database handle schema upgrades?"),
        ("Edge case", "Deploy a new version with schema changes"),
        ("Adversarial", "Manually modify the schema_version table"),
    ],
    "combined": ("#49 &mdash; Remove Database Error Wrapping", "No version tracking + no error wrapping = DB schema chaos. Migrations aren&rsquo;t tracked and errors aren&rsquo;t handled.", "Database upgrades become terrifying. You don&rsquo;t know what version you&rsquo;re on, and any error during migration leaks raw internals."),
    "tips": "Server restart required to test migration behavior. Check current schema version: <code>sqlite3 monster_resort.db 'SELECT * FROM schema_version'</code>",
    "analogy": "Like renovating a house without blueprints &mdash; you might accidentally tear down a load-bearing wall because you didn&rsquo;t know the house&rsquo;s structural history.",
},
51: {
    "label_tag": "panel-label",
    "experiments": [
        ("Experiment A: Load at import time", "Load reranker model at module import", "reranker = CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2')  # module level", "Slows down startup by 5-10 seconds. Every import of the module loads the model, even if never used."),
        ("Experiment B: Load in __init__ with timeout", "Load in constructor with a timeout", "self.reranker = load_with_timeout(CrossEncoder, timeout=10)", "Startup fails fast if model loading is slow. Better than hanging indefinitely."),
        ("Experiment C: Background thread loading", "Load model in a background thread", "self._reranker_future = executor.submit(load_reranker)", "Server starts immediately. Reranker available after loading completes. Queries before loading get unranked results."),
    ],
    "outcomes": [
        ["overall_score", "0.72", "0.50", "0.72", "0.72"],
        ["startup_time", "fast", "broken", "slow", "fast"],
        ["first_query_latency", "normal", "crash", "+5sec", "depends"],
        ["memory_usage", "on_demand", "N/A", "always_loaded", "on_demand"],
    ],
    "queries": [
        ("Keyword query", "Search for rooms"),
        ("Semantic query", "Find the best room for a vampire family"),
        ("Edge case", "Query immediately after server restart"),
        ("Adversarial", "Send 100 requests during model loading"),
    ],
    "combined": ("#19 &mdash; Remove Cross-Encoder Reranking (Tier 2)", "No lazy loading + no reranking = reranker permanently broken. The model is never loaded AND the reranking step is skipped.", "The two-stage retrieval architecture collapses to single-stage. Quality drops for all queries, especially ambiguous ones."),
    "tips": "Server restart required. Monitor startup logs for model loading messages. Check memory usage before and after reranker initialization: <code>ps aux | grep uvicorn</code>",
    "analogy": "Like a restaurant that lists a specialty dish on the menu but never hired the chef who knows how to make it &mdash; the menu promises it, but the kitchen can never deliver.",
},
}

if __name__ == '__main__':
    base = '/Users/akin.olusanya/Desktop/monster-resort-concierge/docs/learning_roadmap'
    print("Processing Tier 3...")
    inject_panels(f'{base}/destruction_lab_tier3.html', EXERCISES, "panel-label")
    print("Tier 3 complete!")
