import logging
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

class DiagramEngine:
    @staticmethod
    def generate_concept_map(title: str, subtopics: List[Dict[str, str]]) -> Dict[str, str]:
        """
        Deterministically builds a Mermaid concept map from the topic's subtopics.
        Strips away the need for the LLM to write Mermaid syntax, saving tokens.
        """
        lines = ["graph LR"]
        # Define classes for polish and safety
        lines.append("    classDef rootNode fill:#3b82f6,stroke:#2563eb,stroke-width:3px,color:#fff,rx:15,ry:15;")
        lines.append("    classDef subNode fill:#0f172a,stroke:#334155,stroke-width:1px,color:#cbd5e1,rx:8,ry:8;")
        
        clean_root = title.replace('"', "'").replace('(', '').replace(')', '')
        lines.append(f'    Root["<b>{clean_root}</b>"]:::rootNode')
        
        for idx, st in enumerate(subtopics):
            st_title = st.get("title", f"Subtopic {idx+1}")
            clean_title = st_title.replace('"', "'").replace('(', '').replace(')', '')
            node_id = f"st_{idx}"
            
            lines.append(f'    {node_id}["{clean_title}"]:::subNode')
            lines.append(f'    Root --- {node_id}')
            
        return {
            "title": f"Concept Map: {title}",
            "code": "\n".join(lines)
        }
        
    @staticmethod
    def generate_process_flow(worked_examples: List[Dict[str, str]]) -> Dict[str, str]:
        """
        Deterministically builds a process sequence diagram if worked examples are present.
        """
        if not worked_examples:
            return {}
            
        example = worked_examples[0]
        title = example.get("title", "Worked Example").replace('"', "'").replace('(', '').replace(')', '')
        
        lines = ["sequenceDiagram"]
        lines.append(f'    participant Problem')
        lines.append(f'    participant Solution')
        lines.append(f'    participant Insights')
        
        lines.append(f'    Note over Problem, Insights: {title}')
        lines.append(f'    Problem->>Solution: Apply Method')
        lines.append(f'    Solution->>Insights: Verify Result')
        
        return {
            "title": f"Process Flow: {title}",
            "code": "\n".join(lines)
        }
