from typing import Any, Dict
import logging
from app.core.redis_client import redis_client

logger = logging.getLogger(__name__)

class SystemMetrics:
    def __init__(self):
        self.alpha_latency = 0.1
        # Provider health defaults if Redis is empty
        self._default_health = {"huggingface": "active", "gemini": "active"}

    def _get_val(self, key: str, default: Any = 0) -> Any:
        if not redis_client: return default
        try:
            val = redis_client.get(key)
            return val if val is not None else default
        except: return default

    def check_redis_status(self) -> str:
        from app.core.redis_client import redis_manager
        return "up" if redis_manager.is_ready() else "down"

    def check_celery_status(self) -> str:
        from app.core.celery_app import celery_app
        try:
            # Inspection is heavy, use a 2-second timeout
            insp = celery_app.control.inspect(timeout=2.0)
            stats = insp.stats()
            return "active" if stats else "down"
        except Exception as e:
            logger.warning(f"[CELERY_STATUS_CHECK] Failed: {e}")
            return "down"

    def record_request(self):
        if redis_client:
            try:
                redis_client.incr("metrics:total_requests")
                # Record a snapshot every 100 requests (simple sampling) or could be time-based
                # For this implementation, we'll expose a snapshot method
            except: pass

    def take_snapshot(self):
        """Records current metrics state into a Redis list (history)."""
        if not redis_client: return
        try:
            import json, time
            report = self.get_health_report()
            report["timestamp"] = time.time()
            redis_client.lpush("metrics:history", json.dumps(report))
            redis_client.ltrim("metrics:history", 0, 100) # Keep last 100 snapshots
        except: pass

    def get_history(self, limit: int = 20):
        if not redis_client: return []
        try:
            import json
            data = redis_client.lrange("metrics:history", 0, limit - 1)
            return [json.loads(d) for d in data]
        except: return []

    def get_queue_status(self) -> Dict[str, Any]:
        """Checks Celery/Redis queue length."""
        if not redis_client: return {"queue_length": 0}
        try:
            # Default Celery queue name is 'celery'
            q_len = redis_client.llen("celery")
            return {"queue_length": q_len}
        except: return {"queue_length": 0}

    def record_success(self, latency_ms: float):
        if redis_client:
            try:
                redis_client.incr("metrics:ai_success")
                current_avg = float(self._get_val("metrics:avg_latency", 0.0))
                if current_avg == 0.0:
                    new_avg = latency_ms
                else:
                    new_avg = (self.alpha_latency * latency_ms) + ((1 - self.alpha_latency) * current_avg)
                redis_client.set("metrics:avg_latency", str(new_avg))
            except: pass

    def record_failure(self, fallback: bool = False):
        if redis_client:
            try:
                redis_client.incr("metrics:ai_failures")
                if fallback:
                    redis_client.incr("metrics:fallback_used")
            except: pass

    def update_provider_status(self, provider: str, status: str):
        if redis_client:
            try:
                redis_client.set(f"metrics:health:{provider}", status)
            except: pass

    def get_health_report(self) -> Dict[str, Any]:
        total_requests = int(self._get_val("metrics:total_requests", 0))
        ai_success = int(self._get_val("metrics:ai_success", 0))
        ai_failures = int(self._get_val("metrics:ai_failures", 0))
        fallback_used = int(self._get_val("metrics:fallback_used", 0))
        avg_latency = float(self._get_val("metrics:avg_latency", 0.0))
        
        hf_status = self._get_val("metrics:health:huggingface", "active")
        gemini_status = self._get_val("metrics:health:gemini", "active")

        total_ai_attempts = ai_success + ai_failures
        
        success_rate = 100.0
        if total_ai_attempts > 0:
            success_rate = (ai_success / total_ai_attempts) * 100
            
        fallback_rate = 0.0
        if total_ai_attempts > 0:
            fallback_rate = (fallback_used / total_ai_attempts) * 100

        q_status = self.get_queue_status()
        redis_status = self.check_redis_status()
        celery_status = self.check_celery_status()

        system_status = "healthy"
        if redis_status == "down" or celery_status == "down":
            system_status = "degraded"
            if redis_status == "down" and celery_status == "down":
                system_status = "critical (operational)"

        return {
            "ai_success_rate": f"{success_rate:.1f}%",
            "fallback_rate": f"{fallback_rate:.1f}%",
            "hf_status": hf_status,
            "gemini_status": gemini_status,
            "avg_response_time_ms": round(avg_latency, 2),
            "system_status": system_status,
            "redis_status": redis_status,
            "celery_status": celery_status,
            "total_requests": total_requests,
            "queue_length": q_status["queue_length"]
        }

# Global singleton
metrics = SystemMetrics()
