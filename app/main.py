from __future__ import annotations
from fastapi.responses import StreamingResponse
import re
import uuid
import os
import secrets
import json
import openai
from datetime import datetime, timezone
from pathlib import Path
from dateutil import parser as date_parser
from fastapi import Depends, FastAPI, HTTPException, Request

os.environ["TOKENIZERS_PARALLELISM"] = "false"

# Local module imports
from .profile_utils import profile

from .config import get_settings

from .database import DatabaseManager
from .memory import MemoryStore
from .monitoring import install_metrics
from .pdf_generator import PDFGenerator
from .advanced_rag import AdvancedRAG
from .security import install_rate_limiter, APIKeyManager
from .admin_routes import router as admin_router
from .auth_mixins import jwt_or_api_key
from .tools import make_registry, VALID_HOTELS
from .llm_providers import (
    ModelRouter,
    LLMMessage,
    LLMToolCall,
    LLMResponse,
    OpenAIProvider,
    AnthropicProvider,
    OllamaProvider,
)
from .hallucination import HallucinationDetector
from .mlflow_tracking import MLflowTracker
from .logging_utils import (
    setup_logging,
    MonsterResortError,
    DatabaseError,
    AIServiceError,
    ValidationError,
)
from .auth import create_access_token, verify_token, hash_password, verify_password
from .users_db import users_db
from .validation import validate_message

# Initialize Logger
logger = setup_logging()


def _validate_tool_call(tool_name: str, tool_args: dict) -> tuple[bool, str]:
    """Defense 6: Validate tool call arguments against authoritative registries."""
    if tool_name == "book_room":
        hotel = tool_args.get("hotel_name", "")
        if hotel not in VALID_HOTELS:
            return False, f"Blocked: unknown hotel '{hotel}'. Not in official registry."
    return True, ""


def _build_router(settings) -> ModelRouter | None:
    """Construct LLM providers and router from settings."""
    providers = []
    priority = [
        p.strip() for p in settings.llm_provider_priority.split(",") if p.strip()
    ]

    for name in priority:
        if name == "openai":
            api_key = settings.openai_api_key or os.getenv("OPENAI_API_KEY")
            if api_key:
                providers.append(
                    OpenAIProvider(api_key=api_key, model=settings.openai_model)
                )
        elif name == "anthropic":
            api_key = settings.anthropic_api_key
            if api_key:
                providers.append(
                    AnthropicProvider(api_key=api_key, model=settings.anthropic_model)
                )
        elif name == "ollama":
            if settings.ollama_enabled:
                providers.append(
                    OllamaProvider(
                        base_url=settings.ollama_base_url, model=settings.ollama_model
                    )
                )

    if not providers:
        return None

    return ModelRouter(
        providers=providers, fallback_enabled=settings.llm_fallback_enabled
    )


def build_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, version="1.0.0")

    db = DatabaseManager(settings)
    api_key_manager = APIKeyManager(db)
    app.state.api_key_manager = api_key_manager
    pdf = PDFGenerator(settings.pdf_output_dir)

    rag = AdvancedRAG(
        settings.rag_persist_dir,
        settings.rag_collection,
        embedding_model=getattr(settings, "embedding_model", "all-MiniLM-L6-v2"),
        reranker_model="BAAI/bge-reranker-base",
        ingestion_token=settings.rag_ingestion_token,
    )

    memory = MemoryStore(db=db)
    registry = make_registry(
        db=db, pdf=pdf, rag_search_fn=lambda query, k=5: rag.search(query=query, k=k)
    )

    install_metrics(app)
    install_rate_limiter(app, settings)
    app.include_router(admin_router)

    # Build multi-model router
    router = _build_router(settings)

    # Hallucination detector
    detector = HallucinationDetector(
        high_threshold=settings.hallucination_high_threshold,
        medium_threshold=settings.hallucination_medium_threshold,
    )

    # MLflow tracker (graceful noop if disabled)
    tracker = MLflowTracker(
        tracking_uri=settings.mlflow_tracking_uri,
        experiment_name=settings.mlflow_experiment_name,
        enabled=settings.mlflow_enabled,
    )

    # --- AGENT LOGIC ---

    @profile
    async def _agent_reply(session_id: str, user_text: str) -> dict:
        try:
            print(
                f"\n=== DEBUG: USER INPUT ===\nSession: {session_id}\nMessage: {user_text}\n"
            )
            text = validate_message(user_text)

            if router is None:
                return {"message": "AI services are offline.", "tool_calls": []}

            knowledge = rag.search(user_text)
            results = knowledge.get("results", [])
            rag_contexts = [r["text"] for r in results]

            # Defense 4: Source attribution — tag each context with its source
            context_lines = []
            for r in results:
                source = r.get("meta", {}).get("source", "unknown")
                context_lines.append(f"[Source: {source}] {r['text']}")
            context_text = "\n".join(context_lines)

            current_date_str = datetime.now().strftime("%Y-%m-%d")

            system_prompt_content = (
                f"You are the 'Grand Chamberlain' of the Monster Resort. Today is {current_date_str}.\n"
                f"ACTIVE SESSION ID: {session_id}\n\n"
                "RESORT KNOWLEDGE BASE (MANDATORY - Use these details FIRST to describe the stay):\n"
                f"{context_text}\n\n"
                "MANDATORY RULES:\n"
                "1. ALWAYS base your answer on the RESORT KNOWLEDGE BASE above when it contains relevant information.\n"
                "2. DO NOT invent details that contradict or are not present in the knowledge base.\n"
                "3. If the knowledge base has information about the topic, quote or paraphrase it directly.\n"
                "4. If no relevant info is found in the knowledge base, say 'I do not have specific details on that in our records.'\n"
                "5. THE WELCOME: When 'book_room' succeeds, describe the specific atmosphere of the property from the knowledge base.\n"
                "6. THE STATUS: Use the phrase 'The dark seal has been set upon the ledger.'\n"
                "7. MANDATORY TONE: Sophisticated, gothic, ultra-luxurious. No modern slang.\n"
                "8. FAREWELL: End with 'We await your shadow' or 'May your rest be eternal (until check-out).'\n"
            )

            print(f"=== DEBUG: SYSTEM PROMPT ===\n{system_prompt_content[:500]}...\n")

            # Build LLMMessage history
            past_messages = memory.get_messages(session_id)
            chat_history: list[LLMMessage] = [
                LLMMessage(role="system", content=system_prompt_content)
            ]
            for m in past_messages:
                if m["role"] in ["user", "assistant"]:
                    chat_history.append(
                        LLMMessage(role=m["role"], content=m["content"])
                    )
            chat_history.append(LLMMessage(role="user", content=user_text))

            tool_schemas = registry.get_openai_tool_schemas()

            # Phase 1: initial LLM call (may include tool calls)
            llm_resp = await router.chat(chat_history, tools=tool_schemas)

            print(f"=== DEBUG: LLM INITIAL RESPONSE ===\n{llm_resp.content}\n")

            if llm_resp.tool_calls:
                # Add assistant message with tool calls to history
                chat_history.append(
                    LLMMessage(
                        role="assistant",
                        content=llm_resp.content,
                        tool_calls=llm_resp.tool_calls,
                    )
                )

                tool_results = []
                for tc in llm_resp.tool_calls:
                    t_name = tc.name
                    t_args = json.loads(tc.arguments)
                    print(f"DEBUG: AI calling tool '{t_name}' with args: {t_args}")

                    # Defense 6: Validate tool call before execution
                    is_valid, error_msg = _validate_tool_call(t_name, t_args)
                    if not is_valid:
                        logger.warning(f"tool_call_blocked: {t_name} — {error_msg}")
                        res = {"ok": False, "error": error_msg, "blocked": True}
                        tool_results.append({"tool": t_name, "result": res})
                        chat_history.append(
                            LLMMessage(
                                role="tool",
                                content=json.dumps(res),
                                tool_call_id=tc.id,
                            )
                        )
                        continue

                    res = await registry.async_execute_with_timing(t_name, **t_args)
                    print(f"DEBUG: Tool '{t_name}' returned: {res}")

                    tool_results.append({"tool": t_name, "result": res})
                    chat_history.append(
                        LLMMessage(
                            role="tool",
                            content=json.dumps(res),
                            tool_call_id=tc.id,
                        )
                    )

                # Phase 2: synthesis call
                llm_resp2 = await router.chat(chat_history)
                final_message = llm_resp2.content

                print(f"=== DEBUG: FINAL LLM RESPONSE AFTER TOOL ===\n{final_message}")

                # Confidence scoring
                confidence = detector.score_response(
                    final_message, rag_contexts, user_text
                )

                # Optional MLflow logging
                tracker.log_confidence_metrics(confidence, provider=llm_resp2.provider)

                return {
                    "message": final_message,
                    "tool_calls": tool_results,
                    "confidence": confidence.to_dict(),
                    "provider": llm_resp2.provider,
                }

            # No tool calls — direct response
            confidence = detector.score_response(
                llm_resp.content, rag_contexts, user_text
            )
            tracker.log_confidence_metrics(confidence, provider=llm_resp.provider)

            return {
                "message": llm_resp.content,
                "tool_calls": [],
                "confidence": confidence.to_dict(),
                "provider": llm_resp.provider,
            }

        except Exception as e:
            import traceback

            logger.error(f"Agent error: {e}")
            logger.error(f"Full traceback: {traceback.format_exc()}")
            return {"message": f"Error: {str(e)}", "ok": False}

    # --- ROUTES ---

    @app.post("/chat")
    async def chat(payload: dict, _: str = Depends(jwt_or_api_key)):
        session_id = payload.get("session_id") or str(uuid.uuid4())
        user_text = payload.get("message")

        response_data = await _agent_reply(session_id, user_text)

        memory.add_message(session_id, "user", user_text)
        memory.add_message(session_id, "assistant", response_data["message"])

        return {
            "ok": True,
            "reply": response_data["message"],
            "session_id": session_id,
            "tools_used": response_data.get("tool_calls", []),
            "confidence": response_data.get("confidence"),
            "provider": response_data.get("provider"),
        }

    # Startup Ingestion
    knowledge_path = os.path.join(os.getcwd(), "data", "knowledge")
    if os.path.exists(knowledge_path):
        logger.info(f"Ingesting knowledge from {knowledge_path}...")
        rag.ingest_folder(knowledge_path, token=settings.rag_ingestion_token)

    return app


app = build_app()
