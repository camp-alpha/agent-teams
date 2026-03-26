# src/agent_teams/research_lab/university_searcher.py

import logging
from typing import Dict, List
from agent_teams.research_lab.config import TARGET_UNIVERSITIES
from agent_teams.notion_logger import log_conversation

logger = logging.getLogger(__name__)

class UniversitySearcher:
    """대학 연구 동향 및 생산성 병목을 탐색하는 에이전트 도구."""

    def __init__(self, university_name: str):
        self.university_name = university_name
        self.config = TARGET_UNIVERSITIES.get(university_name, {})

    def scan_departments(self) -> List[str]:
        """설정된 주요 학과 리스트를 반환."""
        return self.config.get("key_departments", [])

    def analyze_research_trends(self, department: str) -> Dict:
        """학과별 최신 연구 트렌드와 병목 지점을 분석 (시뮬레이션 포함)."""
        # 실제 환경에서는 google_web_search 도구를 호출하여 데이터를 보강해야 함
        trends = {
            "Kim Jaechul Graduate School of AI": {
                "topics": ["Efficient LLM Training", "AI for Science", "Video Generation"],
                "bottlenecks": ["Compute resource management", "Massive data curation", "Interdisciplinary bridge"]
            },
            "Bio and Brain Engineering": {
                "topics": ["Cancer Reversion", "Neural Interfaces", "Synthetic Biology"],
                "bottlenecks": ["Manual literature synthesis", "Experimental design optimization", "Large-scale sequence analysis"]
            }
        }
        return trends.get(department, {"topics": ["General Research"], "bottlenecks": ["Manual labor"]})

    def propose_agent_solutions(self, department: str, bottlenecks: List[str]) -> List[str]:
        """병목 현상을 해결할 에이전트 솔루션 제안."""
        solutions = []
        for b in bottlenecks:
            if "literature" in b.lower() or "data" in b.lower():
                solutions.append(f"Autonomous {department} Literature Agent")
            if "design" in b.lower() or "optimization" in b.lower():
                solutions.append(f"Bayesian Experiment Optimizer Agent")
            if "compute" in b.lower():
                solutions.append(f"Auto-Resource Scheduler Agent")
        return solutions or ["General Research Assistant Agent"]

    def run_full_scan(self):
        """대학 전체 스캔 및 결과 Notion 기록."""
        report = []
        for dept in self.scan_departments():
            analysis = self.analyze_research_trends(dept)
            solutions = self.propose_agent_solutions(dept, analysis["bottlenecks"])
            
            summary = f"### Department: {dept}\n"
            summary += f"- Topics: {', '.join(analysis['topics'])}\n"
            summary += f"- Bottlenecks: {', '.join(analysis['bottlenecks'])}\n"
            summary += f"- Proposed Agents: {', '.join(solutions)}\n"
            report.append(summary)

        full_report = f"# {self.university_name} Research Efficiency Report\n\n" + "\n".join(report)
        
        # Notion에 기록
        log_conversation(
            from_agent="UniversitySearcher",
            to_agent="CEO",
            message=full_report,
            team="research_lab",
            channel="discovery",
            thinking=f"{self.university_name} 전수 조사 및 에이전트 솔루션 도출 완료."
        )
        return full_report

if __name__ == "__main__":
    searcher = UniversitySearcher("KAIST")
    print(searcher.run_full_scan())
