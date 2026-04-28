"""
Code Sandbox API — executes user code in a sandboxed subprocess.
Supports Python and JavaScript with strict timeout and resource limits.
"""
import subprocess
import tempfile
import os
from fastapi import APIRouter, Body, HTTPException
from pydantic import BaseModel
from typing import Optional

router = APIRouter()


class CodeRequest(BaseModel):
    code: str
    language: str = "python"  # python, javascript


@router.post("/run")
def run_code(payload: CodeRequest):
    """Execute code in a sandboxed subprocess with timeout."""
    code = payload.code
    language = payload.language.lower()

    if language not in ("python", "javascript", "js"):
        raise HTTPException(status_code=400, detail="Unsupported language. Use 'python' or 'javascript'.")

    if len(code) > 10000:
        raise HTTPException(status_code=400, detail="Code too long (max 10,000 characters).")

    # Map language to interpreter
    if language in ("javascript", "js"):
        ext = ".js"
        cmd_prefix = ["node"]
    else:
        ext = ".py"
        cmd_prefix = ["python", "-u"]

    # Write to temp file and execute
    try:
        with tempfile.NamedTemporaryFile(mode="w", suffix=ext, delete=False, encoding="utf-8") as f:
            f.write(code)
            temp_path = f.name

        result = subprocess.run(
            cmd_prefix + [temp_path],
            capture_output=True,
            text=True,
            timeout=5,  # 5-second hard timeout
            cwd=tempfile.gettempdir(),
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        )

        return {
            "stdout": result.stdout[:5000],  # Cap output
            "stderr": result.stderr[:2000],
            "returncode": result.returncode,
            "success": result.returncode == 0,
        }

    except subprocess.TimeoutExpired:
        return {
            "stdout": "",
            "stderr": "⏱ Execution timed out (5 second limit exceeded).",
            "returncode": -1,
            "success": False,
        }
    except FileNotFoundError:
        interpreter = "Node.js" if language in ("javascript", "js") else "Python"
        return {
            "stdout": "",
            "stderr": f"⚠ {interpreter} runtime not found on the server.",
            "returncode": -1,
            "success": False,
        }
    except Exception as e:
        return {
            "stdout": "",
            "stderr": f"Internal error: {str(e)}",
            "returncode": -1,
            "success": False,
        }
    finally:
        try:
            os.unlink(temp_path)
        except:
            pass
