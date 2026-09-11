from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SafetyMatch:
    urgent: bool
    reason: str = ""
    immediate: bool = False
    matched_term: str = ""


EMERGENCY_GROUPS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "possible heart or breathing emergency",
        (
            "severe chest pain",
            "crushing chest pain",
            "chest pain and cannot breathe",
            "can't breathe",
            "cannot breathe",
            "blue lips",
            "胸口剧痛",
            "胸痛而且呼吸困难",
            "呼吸困难",
            "喘不上气",
            "嘴唇发紫",
            "가슴이 심하게 아프",
            "숨쉬기 어렵",
            "숨을 못",
            "입술이 파래",
        ),
    ),
    (
        "loss of consciousness or acute neurological symptoms",
        (
            "fainted",
            "passed out",
            "confusion",
            "seizure",
            "face droop",
            "one-sided weakness",
            "slurred speech",
            "昏倒",
            "晕倒",
            "意识不清",
            "抽搐",
            "口角歪斜",
            "单侧无力",
            "说话不清",
            "실신",
            "의식이 흐림",
            "경련",
            "얼굴이 처짐",
            "한쪽 힘이 빠짐",
            "말이 어눌",
        ),
    ),
    (
        "severe allergy, bleeding, or high-risk infection signs",
        (
            "severe allergic reaction",
            "throat swelling",
            "uncontrolled bleeding",
            "won't stop bleeding",
            "stiff neck with fever",
            "very high fever",
            "严重过敏",
            "喉咙肿胀",
            "止不住血",
            "发热伴颈项强直",
            "高烧不退",
            "심한 알레르기",
            "목이 붓",
            "피가 멈추지",
            "열과 목 경직",
            "고열",
        ),
    ),
    (
        "risk of self-harm",
        (
            "suicide",
            "kill myself",
            "end my life",
            "self-harm",
            "hurt myself",
            "自杀",
            "轻生",
            "结束生命",
            "自残",
            "伤害自己",
            "자살",
            "죽고 싶",
            "생을 끝",
            "자해",
            "나를 해치",
        ),
    ),
)


def check_emergency(text: str) -> SafetyMatch:
    normalised = text.casefold()
    for reason, phrases in EMERGENCY_GROUPS:
        for phrase in phrases:
            if phrase.casefold() in normalised:
                return SafetyMatch(urgent=True, reason=reason, immediate=True, matched_term=phrase)
    return SafetyMatch(urgent=False)
