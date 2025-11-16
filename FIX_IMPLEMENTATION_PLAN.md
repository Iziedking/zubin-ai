# ROMA + Frontend Fix Implementation Plan

## Overview

This document provides detailed implementation steps for fixing the 7 critical issues identified in `CRITICAL_ISSUES_ANALYSIS.md`.

---

## Phase 1: Critical Bugs (P0) - **Immediate**

### Fix 1.1: Backend - Null final_result on Exception

**File:** `ROMA_backend/ROMA-izie_v2/src/roma_dspy/api/execution_service.py`

**Location:** Lines 185-207 (exception handler in `_run_execution`)

**Current Code:**
```python
except Exception as e:
    logger.error(f"Execution {execution_id} failed: {e}")

    await self.storage.update_execution(
        execution_id=execution_id,
        status=ExecutionStatus.FAILED.value,
        execution_metadata=merged_metadata
    )
```

**Fixed Code:**
```python
except Exception as e:
    logger.error(f"Execution {execution_id} failed: {e}")

    # Get task stats for context
    task_stats = await self._get_task_stats_with_statistics(execution_id)

    # Build user-friendly error message
    error_message = self._build_error_message(e, task_stats)

    await self.storage.update_execution(
        execution_id=execution_id,
        status=ExecutionStatus.FAILED.value,
        execution_metadata=merged_metadata,
        final_result={
            "result": error_message,
            "status": "FAILED",
            "error_type": type(e).__name__,
            "error_details": str(e)
        }
    )
```

**Add Helper Method:** (After line 248)
```python
def _build_error_message(self, error: Exception, task_stats: Dict[str, int]) -> str:
    """Build user-friendly error message from exception."""
    error_type = type(error).__name__

    # Map technical errors to user-friendly messages
    error_messages = {
        "TimeoutError": "The request took too long to process. Please try again with a simpler query.",
        "ConnectionError": "Unable to connect to required services. Please try again in a moment.",
        "ValidationError": "Invalid input detected. Please rephrase your question.",
        "RateLimitError": "Too many requests. Please wait a moment and try again.",
        "APIError": "An external service encountered an error. Please try again.",
    }

    user_message = error_messages.get(
        error_type,
        "I encountered an issue processing your request. Please try rephrasing or simplifying your question."
    )

    # Add context if tasks were processed
    if task_stats['completed_tasks'] > 0:
        user_message += f"\n\nPartially completed: {task_stats['completed_tasks']}/{task_stats['total_tasks']} tasks."

    return user_message
```

---

### Fix 1.2: Frontend - Handle Null final_result Gracefully

**File:** `dmj-chat/src/components/Chat.tsx`

**Location:** Lines 98-113

**Current Code:**
```typescript
else if (botMsg.data.status === "failed" && botMsg.data.final_result) {
  const botMessage: ChatType = {
    id: Math.floor(Math.random() * 1000000),
    sender: "assistant",
    message: botMsg.data.final_result.result,
    timestamp: new Date(),
  };
  setMessageList((prevMessages) => [...prevMessages, botMessage]);
  setIsProcessing(false);
}
```

**Fixed Code:**
```typescript
else if (botMsg.data.status === "failed") {
  // Handle both cases: with and without final_result
  const errorMessage = botMsg.data.final_result?.result ||
    "I encountered an unexpected error. Please try again or rephrase your question.";

  const botMessage: ChatType = {
    id: Math.floor(Math.random() * 1000000),
    sender: "assistant",
    message: errorMessage,
    timestamp: new Date(),
  };
  setMessageList((prevMessages) => [...prevMessages, botMessage]);
  setIsProcessing(false);
}
// Add timeout fallback for stuck "running" status
else if (botMsg.data.status === "running") {
  // Continue polling (will be enhanced in Fix 1.4)
  setTimeout(() => executions(executionId), 5000);
}
// Handle unknown status
else {
  console.error("Unknown execution status:", botMsg.data.status);
  const errorMsg: ChatType = {
    id: Math.floor(Math.random() * 1000000),
    sender: "assistant",
    message: "I encountered an unexpected status. Please try your request again.",
    timestamp: new Date(),
  };
  setMessageList((prevMessages) => [...prevMessages, errorMsg]);
  setIsProcessing(false);
}
```

---

### Fix 1.3: Frontend - Add Session Management with client_id

**File:** `dmj-chat/src/lib/session.ts` (NEW FILE)

```typescript
/**
 * Session management for maintaining conversation context
 */

const SESSION_ID_KEY = 'zubin_session_id';
const SESSION_EXPIRY_KEY = 'zubin_session_expiry';
const SESSION_DURATION_MS = 30 * 60 * 1000; // 30 minutes

/**
 * Get or create a session ID for this browser tab
 */
export function getSessionId(): string {
  // Check if we have a valid session
  const existingId = sessionStorage.getItem(SESSION_ID_KEY);
  const expiry = sessionStorage.getItem(SESSION_EXPIRY_KEY);

  if (existingId && expiry) {
    const expiryTime = parseInt(expiry, 10);
    if (Date.now() < expiryTime) {
      // Session still valid, extend expiry
      sessionStorage.setItem(
        SESSION_EXPIRY_KEY,
        (Date.now() + SESSION_DURATION_MS).toString()
      );
      return existingId;
    }
  }

  // Create new session
  const newId = `web_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
  sessionStorage.setItem(SESSION_ID_KEY, newId);
  sessionStorage.setItem(
    SESSION_EXPIRY_KEY,
    (Date.now() + SESSION_DURATION_MS).toString()
  );

  return newId;
}

/**
 * Clear the current session (e.g., on logout or reset)
 */
export function clearSession(): void {
  sessionStorage.removeItem(SESSION_ID_KEY);
  sessionStorage.removeItem(SESSION_EXPIRY_KEY);
}

/**
 * Get session info for debugging
 */
export function getSessionInfo() {
  const id = sessionStorage.getItem(SESSION_ID_KEY);
  const expiry = sessionStorage.getItem(SESSION_EXPIRY_KEY);

  if (!id || !expiry) {
    return null;
  }

  return {
    id,
    expiresAt: new Date(parseInt(expiry, 10)),
    isValid: Date.now() < parseInt(expiry, 10)
  };
}
```

**File:** `dmj-chat/src/components/Chat.tsx`

**Add import:**
```typescript
import { getSessionId } from "@/lib/session";
```

**Update API call (Lines 68-78):**
```typescript
const sessionId = getSessionId(); // Get session ID

const execute = await apiClient.post(
  "/executions",
  {
    goal: text,
    metadata: {
      client_id: sessionId,  // Add session tracking
      source: "web_chat"
    }
  },
  {
    headers: {
      "X-API-Key": process.env.NEXT_PUBLIC_ZUBIN_API_KEY || "",
      "X-Client-ID": sessionId  // Also send in header
    },
  }
);
```

---

### Fix 1.4: Backend - Use client_id from Metadata

**File:** `ROMA_backend/ROMA-izie_v2/src/roma_dspy/api/routers/executions.py`

**Location:** Lines 59-64

**Current Code:**
```python
execution_id = await app_state.execution_service.start_execution(
    goal=solve_request.goal,
    max_depth=solve_request.max_depth,
    metadata=solve_request.metadata,
    client_name=client_name
)
```

**Updated Code:**
```python
# Extract client_id from metadata if provided (for session tracking)
client_id = None
if solve_request.metadata:
    client_id = solve_request.metadata.get("client_id")

execution_id = await app_state.execution_service.start_execution(
    goal=solve_request.goal,
    max_depth=solve_request.max_depth,
    metadata=solve_request.metadata,
    client_name=client_id or client_name  # Prefer client_id from metadata
)
```

**File:** `ROMA_backend/ROMA-izie_v2/src/roma_dspy/api/execution_service.py`

**Location:** Line 100 (smart router call)

**Already correct!** The `client_name` parameter is passed to smart router:
```python
fast_result = await self.smart_router.route(goal, client_id=client_name)
```

---

### Fix 1.5: Frontend - Add Polling Timeout

**File:** `dmj-chat/src/components/Chat.tsx`

**Add state for polling:**
```typescript
const [messageList, setMessageList] = useState<ChatType[]>([]);
const [dmjmessageList, setDmjMessageList] = useState<ChatType[]>([]);
const [isProcessing, setIsProcessing] = useState<boolean>(false);
const [userMessage, setUserMessage] = useState<string>("");
const lastMsgRef = useRef<HTMLDivElement | null>(null);

// NEW: Polling timeout tracking
const pollingStartTime = useRef<number>(0);
const pollingAttemptsRef = useRef<number>(0);
const MAX_POLLING_DURATION_MS = 5 * 60 * 1000; // 5 minutes
const MAX_POLLING_ATTEMPTS = 60; // 60 attempts × 5s = 5 minutes
```

**Update executions function (Lines 80-113):**
```typescript
const executions = async (executionId: string) => {
  // Check timeout conditions
  const elapsed = Date.now() - pollingStartTime.current;
  pollingAttemptsRef.current += 1;

  if (elapsed > MAX_POLLING_DURATION_MS || pollingAttemptsRef.current > MAX_POLLING_ATTEMPTS) {
    // Timeout reached
    console.error("Execution timeout:", executionId);
    const timeoutMsg: ChatType = {
      id: Math.floor(Math.random() * 1000000),
      sender: "assistant",
      message: "This request is taking longer than expected. It may still be processing, but I'm stopping the wait to prevent freezing. Please try a simpler query or check back later.",
      timestamp: new Date(),
    };
    setMessageList((prevMessages) => [...prevMessages, timeoutMsg]);
    setIsProcessing(false);

    // Optionally cancel the execution
    try {
      await apiClient.post(`/executions/${executionId}/cancel`, {}, {
        headers: { "X-API-Key": process.env.NEXT_PUBLIC_ZUBIN_API_KEY || "" }
      });
    } catch (err) {
      console.error("Failed to cancel execution:", err);
    }

    return;
  }

  try {
    const botMsg = await apiClient.get(`/executions/${executionId}`, {
      headers: {
        "X-API-Key": process.env.NEXT_PUBLIC_ZUBIN_API_KEY || "",
      },
    });

    if (botMsg.data.status === "running") {
      // Adaptive polling interval
      const interval = pollingAttemptsRef.current < 10 ? 2000 :  // First 20s: 2s
                       pollingAttemptsRef.current < 20 ? 3000 :  // 20-60s: 3s
                       5000;                                      // 60s+: 5s

      setTimeout(() => executions(executionId), interval);
    }
    else if (botMsg.data.status === "completed") {
      const botMessage: ChatType = {
        id: Math.floor(Math.random() * 1000000),
        sender: "assistant",
        message: botMsg.data.final_result.result,
        timestamp: new Date(),
      };
      setMessageList((prevMessages) => [...prevMessages, botMessage]);
      setIsProcessing(false);
      pollingAttemptsRef.current = 0; // Reset
    }
    else if (botMsg.data.status === "failed") {
      const errorMessage = botMsg.data.final_result?.result ||
        "I encountered an unexpected error. Please try again.";

      const botMessage: ChatType = {
        id: Math.floor(Math.random() * 1000000),
        sender: "assistant",
        message: errorMessage,
        timestamp: new Date(),
      };
      setMessageList((prevMessages) => [...prevMessages, botMessage]);
      setIsProcessing(false);
      pollingAttemptsRef.current = 0; // Reset
    }
    else {
      // Unknown status
      console.error("Unknown execution status:", botMsg.data.status);
      const errorMsg: ChatType = {
        id: Math.floor(Math.random() * 1000000),
        sender: "assistant",
        message: "Received unexpected status. Please try again.",
        timestamp: new Date(),
      };
      setMessageList((prevMessages) => [...prevMessages, errorMsg]);
      setIsProcessing(false);
      pollingAttemptsRef.current = 0; // Reset
    }
  } catch (error) {
    console.error("Error polling execution:", error);
    // Network error during polling
    const errorMsg: ChatType = {
      id: Math.floor(Math.random() * 1000000),
      sender: "assistant",
      message: "Lost connection while processing. Please try again.",
      timestamp: new Date(),
    };
    setMessageList((prevMessages) => [...prevMessages, errorMsg]);
    setIsProcessing(false);
    pollingAttemptsRef.current = 0; // Reset
  }
};
```

**Update submit handler to initialize polling tracking:**
```typescript
const handleSubmit = async (e: React.FormEvent) => {
  e.preventDefault();
  if (!userMessage.trim() || isProcessing) return;

  const text = userMessage;
  setUserMessage("");
  setIsProcessing(true);

  // Reset polling tracking
  pollingStartTime.current = Date.now();
  pollingAttemptsRef.current = 0;

  // ... rest of submit logic
```

---

## Phase 2: Reliability (P1) - **High Priority**

### Fix 2.1: Add Error Display UI

**File:** `dmj-chat/src/components/ErrorMessage.tsx` (NEW FILE)

```typescript
import React from 'react';

interface ErrorMessageProps {
  message: string;
  type?: 'error' | 'warning' | 'info';
  onRetry?: () => void;
  onDismiss?: () => void;
}

export const ErrorMessage: React.FC<ErrorMessageProps> = ({
  message,
  type = 'error',
  onRetry,
  onDismiss
}) => {
  const bgColor = {
    error: 'bg-red-900/20 border-red-500',
    warning: 'bg-yellow-900/20 border-yellow-500',
    info: 'bg-blue-900/20 border-blue-500'
  }[type];

  const icon = {
    error: '❌',
    warning: '⚠️',
    info: 'ℹ️'
  }[type];

  return (
    <div className={`px-4 py-3 rounded-lg border-l-4 ${bgColor} mb-4`}>
      <div className="flex items-start gap-3">
        <span className="text-xl">{icon}</span>
        <div className="flex-1">
          <p className="text-sm text-white/90">{message}</p>
          {(onRetry || onDismiss) && (
            <div className="mt-2 flex gap-2">
              {onRetry && (
                <button
                  onClick={onRetry}
                  className="px-3 py-1 text-xs bg-white/10 hover:bg-white/20 rounded transition"
                >
                  Retry
                </button>
              )}
              {onDismiss && (
                <button
                  onClick={onDismiss}
                  className="px-3 py-1 text-xs bg-white/5 hover:bg-white/10 rounded transition"
                >
                  Dismiss
                </button>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
```

### Fix 2.2: Implement Retry Logic with Exponential Backoff

**File:** `dmj-chat/src/lib/retry.ts` (NEW FILE)

```typescript
/**
 * Retry utilities with exponential backoff
 */

interface RetryOptions {
  maxAttempts?: number;
  initialDelay?: number;
  maxDelay?: number;
  backoffMultiplier?: number;
  onRetry?: (attempt: number, error: Error) => void;
}

const DEFAULT_OPTIONS: Required<RetryOptions> = {
  maxAttempts: 3,
  initialDelay: 1000,
  maxDelay: 10000,
  backoffMultiplier: 2,
  onRetry: () => {}
};

/**
 * Retry an async function with exponential backoff
 */
export async function withRetry<T>(
  fn: () => Promise<T>,
  options: RetryOptions = {}
): Promise<T> {
  const opts = { ...DEFAULT_OPTIONS, ...options };
  let lastError: Error;

  for (let attempt = 1; attempt <= opts.maxAttempts; attempt++) {
    try {
      return await fn();
    } catch (error) {
      lastError = error as Error;

      // Don't retry on non-retryable errors
      if (!isRetryableError(error)) {
        throw error;
      }

      // Don't delay on last attempt
      if (attempt === opts.maxAttempts) {
        break;
      }

      const delay = Math.min(
        opts.initialDelay * Math.pow(opts.backoffMultiplier, attempt - 1),
        opts.maxDelay
      );

      opts.onRetry(attempt, lastError);
      await sleep(delay);
    }
  }

  throw lastError!;
}

/**
 * Determine if an error is retryable
 */
function isRetryableError(error: any): boolean {
  // Network errors
  if (error.message?.includes('network') || error.message?.includes('fetch')) {
    return true;
  }

  // HTTP status codes that are retryable
  const retryableStatus = [408, 429, 500, 502, 503, 504];
  if (error.response?.status && retryableStatus.includes(error.response.status)) {
    return true;
  }

  // Timeout errors
  if (error.code === 'ECONNABORTED' || error.message?.includes('timeout')) {
    return true;
  }

  return false;
}

function sleep(ms: number): Promise<void> {
  return new Promise(resolve => setTimeout(resolve, ms));
}
```

**Update:** `dmj-chat/src/components/Chat.tsx`

```typescript
import { withRetry } from "@/lib/retry";

// Update API call with retry
const execute = await withRetry(
  () => apiClient.post(
    "/executions",
    {
      goal: text,
      metadata: {
        client_id: sessionId,
        source: "web_chat"
      }
    },
    {
      headers: {
        "X-API-Key": process.env.NEXT_PUBLIC_ZUBIN_API_KEY || "",
        "X-Client-ID": sessionId
      },
    }
  ),
  {
    maxAttempts: 3,
    initialDelay: 2000,
    onRetry: (attempt, error) => {
      console.log(`Retry attempt ${attempt} after error:`, error.message);
    }
  }
);
```

### Fix 2.3: Backend - Add Retry Logic for Free Models

**File:** `ROMA_backend/ROMA-izie_v2/src/roma_dspy/config/schemas/agents.py`

**Update agent configs for free model optimization:**

```python
# Optimize for free tier models
ATOMIZER_CONFIG = AgentConfig(
    name="atomizer",
    agent_type=AgentType.ATOMIZER,
    llm=LLMConfig(
        model="openrouter/deepseek/deepseek-chat",  # Free tier
        temperature=0.1,
        max_tokens=800,  # Reduced for faster response
        num_retries=5,   # Increased retries for free tier
        cache=True,
        timeout=60,      # Longer timeout for free tier
    ),
    strategy="chain_of_thought",
)

EXECUTOR_CONFIG = AgentConfig(
    name="executor",
    agent_type=AgentType.EXECUTOR,
    llm=LLMConfig(
        model="openrouter/deepseek/deepseek-chat",
        temperature=0.3,  # Lower for more consistency
        max_tokens=1500,  # Reduced
        num_retries=5,
        cache=True,
        timeout=90,
    ),
    strategy="chain_of_thought",
)

AGGREGATOR_CONFIG = AgentConfig(
    name="aggregator",
    agent_type=AgentType.AGGREGATOR,
    llm=LLMConfig(
        model="openrouter/deepseek/deepseek-chat",
        temperature=0.2,
        max_tokens=2000,
        num_retries=5,
        cache=True,
        timeout=90,
    ),
    synthesis_strategy="hierarchical",
)
```

### Fix 2.4: Add Model Fallback Strategy

**File:** `ROMA_backend/ROMA-izie_v2/src/roma_dspy/config/schemas/base.py`

**Add fallback models to LLMConfig:**

```python
@dataclass
class LLMConfig:
    model: str = "gpt-4o-mini"
    temperature: float = 0.7
    max_tokens: int = 2000
    timeout: int = 30
    api_key: Optional[str] = None
    base_url: Optional[str] = None

    # DSPy-native features
    num_retries: int = 3
    cache: bool = True

    # NEW: Fallback strategy for free models
    fallback_models: List[str] = field(default_factory=lambda: [
        "openrouter/meta-llama/llama-3.1-70b-instruct:free",
        "gpt-4o-mini"
    ])
    enable_fallback: bool = True
```

**File:** `ROMA_backend/ROMA-izie_v2/src/roma_dspy/core/factory/agent_factory.py`

**Add fallback logic to agent creation:**

```python
def create_agent(self, agent_type: AgentType, config: AgentConfig) -> Any:
    """Create agent with fallback model support."""
    module_cls = self.agent_registry.get_module_class(agent_type)

    if not module_cls:
        raise ValueError(f"No module class registered for {agent_type}")

    signature = self.signature_resolver.resolve_signature(agent_type)

    # Create LM with fallback
    lm = self._create_lm_with_fallback(config.llm)

    return module_cls(signature=signature, lm=lm)

def _create_lm_with_fallback(self, llm_config: LLMConfig) -> Any:
    """Create language model with automatic fallback."""
    import dspy
    from dspy.teleprompt import BootstrapFewShot

    models_to_try = [llm_config.model]
    if llm_config.enable_fallback:
        models_to_try.extend(llm_config.fallback_models)

    last_error = None

    for model in models_to_try:
        try:
            logger.info(f"Attempting to create LM with model: {model}")

            lm = dspy.OpenAI(
                model=model,
                temperature=llm_config.temperature,
                max_tokens=llm_config.max_tokens,
                timeout=llm_config.timeout,
                api_key=llm_config.api_key,
                base_url=llm_config.base_url or "https://openrouter.ai/api/v1",
            )

            # Test the model with a simple call
            test_signature = dspy.Signature("question -> answer")
            test_module = dspy.Predict(test_signature)
            test_module.forward(question="test")

            logger.info(f"Successfully created LM with model: {model}")
            return lm

        except Exception as e:
            last_error = e
            logger.warning(f"Failed to create LM with {model}: {e}")
            continue

    # All models failed
    raise RuntimeError(
        f"Failed to create LM with all models. Last error: {last_error}"
    )
```

---

## Testing Plan

### Phase 1 Tests

**Test 1.1: Null final_result**
```bash
# Trigger exception in backend
curl -X POST http://localhost:3000/api/api/v1/executions \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-key" \
  -d '{"goal": "invalid@@@query###", "max_depth": 2}'

# Verify: final_result is set with user-friendly error message
```

**Test 1.2: Session tracking**
```javascript
// In browser console
sessionStorage.clear();
// Send message 1
// Check sessionStorage for session_id
// Send message 2
// Verify same session_id is used
```

**Test 1.3: Polling timeout**
```javascript
// Mock a stuck execution
// Verify timeout message appears after 5 minutes
// Verify isProcessing is set to false
```

### Phase 2 Tests

**Test 2.1: Error display**
```javascript
// Disconnect network
// Send message
// Verify error UI is displayed with retry button
```

**Test 2.2: Retry logic**
```javascript
// Mock intermittent failures
// Verify 3 retry attempts with exponential backoff
// Verify success on 3rd attempt
```

**Test 2.3: Model fallback**
```python
# Configure primary model to fail
# Verify automatic fallback to secondary model
# Check logs for fallback messages
```

---

## Deployment Checklist

- [ ] Backend changes deployed to staging
- [ ] Frontend changes deployed to staging
- [ ] All Phase 1 tests pass
- [ ] Session management works across tabs
- [ ] Error messages display correctly
- [ ] Polling timeout works
- [ ] Retry logic works with network issues
- [ ] Model fallback works with API failures
- [ ] Performance metrics collected (response times, error rates)
- [ ] User acceptance testing completed
- [ ] Production deployment scheduled

---

## Success Metrics

### Before Fixes
- **Error Rate:** ~15-20% (from exceptions with null final_result)
- **User Complaints:** "Stuck loading forever"
- **Follow-up Success:** 0% (no session tracking)
- **Free Model Reliability:** ~60%

### After Fixes (Expected)
- **Error Rate:** <5% (with proper error handling)
- **User Complaints:** <1% (with error messages and retry)
- **Follow-up Success:** >90% (with session tracking)
- **Free Model Reliability:** >90% (with retries + fallback)

---

## Next Actions

1. **Review this plan** - Approve or suggest changes
2. **I'll implement Phase 1** - Critical bug fixes
3. **Test in development** - Verify all fixes work
4. **Deploy to staging** - User acceptance testing
5. **Implement Phase 2** - Reliability improvements

Ready to start implementing? 🚀
