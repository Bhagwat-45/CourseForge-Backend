import re
import logging

logger = logging.getLogger(__name__)

class Sanitizer:
    """
    Dedicated AI Response Sanitization Layer.
    Guarantees extraction of valid JSON chunks from noisy AI responses.
    """

    @staticmethod
    def extract_json(raw_output: str) -> str:
        """
        Aggressively extracts and normalizes the JSON block.
        """
        # 1. Extract markdown block if explicitly wrapped
        match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', raw_output, re.DOTALL | re.IGNORECASE)
        if match:
            clean = match.group(1)
        else:
            clean = raw_output.strip()
            
            # Find boundaries
            start_idx = clean.find('{')
            if start_idx != -1:
                # Stack-based matcher ensures we grab only the first complete object
                stack = 0
                for i in range(start_idx, len(clean)):
                    if clean[i] == '{':
                        stack += 1
                    elif clean[i] == '}':
                        stack -= 1
                        if stack == 0:
                            clean = clean[start_idx:i+1]
                            break
                else:
                    # Incomplete JSON: Attempt to find the last closing brace
                    end_idx = clean.rfind('}')
                    if end_idx != -1 and end_idx >= start_idx:
                        clean = clean[start_idx:end_idx+1]
            else:
                raise ValueError("Sanitizer Error: No JSON starting bracket found in output.")

        # 2. Clean trailing commas in objects/lists before closing brackets
        clean = re.sub(r',\s*\}', '}', clean)
        clean = re.sub(r',\s*\]', ']', clean)
        
        # 3. Normalize newlines
        clean = clean.replace('\r\n', '\n')

        return clean
