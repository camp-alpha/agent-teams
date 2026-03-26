# src/agent_teams/research_lab/config.py

RESEARCH_LAB_MODELS = {
    "rigorous_reasoning": {
        "model": "gemini-1.5-pro",
        "description": "Inspired by AlphaProof, for formal logic and proof verification."
    },
    "scientific_discovery": {
        "model": "claude-3-5-sonnet",
        "description": "For creative hypothesis generation and cross-disciplinary insights."
    },
    "mathematical_computation": {
        "model": "deepseek-math-7b",  # Future API integration
        "description": "For heavy numerical and symbolic mathematical patterns."
    }
}

TARGET_UNIVERSITIES = {
    "KAIST": {
        "key_departments": [
            "Kim Jaechul Graduate School of AI",
            "College of Engineering (Mechanical, Electrical, Industrial)",
            "Graduate School of Quantum Science",
            "Bio and Brain Engineering"
        ],
        "strategic_focus": [
            "Physical AI (KAIROS)",
            "On-device AI (SoulMate)",
            "Cancer Reversion Therapy",
            "Smart Materials"
        ]
    },
    "MIT": {
        "key_departments": ["CSAIL", "Mathematics", "Physics"],
        "strategic_focus": ["AI for Science", "Quantum Computing", "Synthetic Biology"]
    }
}

RESEARCH_WORKFLOWS = [
    "Literature_Review_Automation",
    "Hypothesis_Red_Teaming",
    "Simulation_Prompt_Engineering",
    "Drafting_Research_Proposals"
]
