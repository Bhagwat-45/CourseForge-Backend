import re
from typing import List, Dict

def extract_flashcards_from_text(text: str) -> List[Dict[str, str]]:
    """
    Deterministically extracts flashcards from text using regex patterns,
    avoiding costly LLM calls for simple extraction tasks.
    """
    if not text:
        return []
        
    flashcards = []
    
    # Common definitional patterns
    # Example: "Photosynthesis is the process by which..."
    # Example: "A function refers to a block of code..."
    patterns = [
        r'([A-Z][\w\s\-]+)\s+(?:is defined as|refers to|is essentially|can be described as)\s+([^.]+.)',
        r'(?<!\.)\s([A-Z][\w\s\-]+)\s+is\s+(?:a|an|the)\s+([^.]+.)'
    ]
    
    seen_fronts = set()
    
    for pattern in patterns:
        matches = re.finditer(pattern, text)
        for match in matches:
            front = match.group(1).strip()
            back = match.group(2).strip()
            
            # Simple heuristic to avoid matching entire paragraphs and generic words
            if len(front.split()) <= 4 and len(back.split()) > 3 and front.lower() not in ["it", "this", "that", "which"]:
                if front not in seen_fronts:
                    flashcards.append({
                        "front": f"What is {front}?",
                        "back": back
                    })
                    seen_fronts.add(front)
                
    return flashcards
