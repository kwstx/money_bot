The FOMO Listener is the entry point of the entire platform. Its responsibility is not to perform any trading logic or analytics, but to continuously monitor the FOMO application for new notifications and transform them into structured events that the rest of the platform can consume. Treat it as an event-ingestion service whose only objective is to guarantee that every relevant notification is captured exactly once, timestamped, normalized, and delivered into the internal event pipeline with minimal latency.

The component should be implemented as a standalone microservice rather than embedded into the main application. This separation allows it to restart independently, scale independently, and continue ingesting events even if downstream services experience failures. The service should expose only a small internal API while publishing notification events to a message broker that other components subscribe to asynchronously.

## Security Architecture

The ingestion service is exposed to external inputs and operates under the following strict security design principles:

1. **Isolation & Least Privilege**: The ingestion microservice is completely isolated from the trading infrastructure. It does not load, possess, or require any database access, trading credentials, or wallet private keys.
2. **Strict Schema Validation**: All incoming payloads are validated via robust Pydantic schemas enforcing data types, dictionary structures, and maximum string limits to reject malformed or exploit payloads.
3. **Recursive Input Sanitization**: Text fields are sanitized recursively to remove HTML/script tags and escape special characters before being logged, cached, or published downstream to prevent injection attacks (e.g. XSS, command injection).
4. **Payload Size Limiting**: Incoming HTTP request sizes are strictly capped at a configurable threshold (default 64 KB) at the connection stream level, defending against resource exhaustion/Denial of Service (DoS) attacks.
5. **Sender Authentication**: The API endpoint optionally authenticates external callers using a token-based header (`X-API-Key`) validation, ensuring only trusted sources can submit notifications.

