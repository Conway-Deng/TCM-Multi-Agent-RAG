from __future__ import annotations

import asyncio
import hashlib
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from western.benchmark import (  # noqa: E402
    BENCHMARK_NAME,
    BENCHMARK_VERSION,
    VALID_ANSWERABILITY,
    VALID_QUESTION_TYPES,
    VALID_TOPICS,
    coverage_audit,
    leakage_audit,
    validate_benchmark,
)
from western.corpus import load_runtime_corpus  # noqa: E402
from western.retrieval import WesternRetriever  # noqa: E402
from western.schemas import WesternTopic  # noqa: E402


BUILD_COMMIT = "e6b02f6e37534008427cb18cd06ce7f086153103"
CREATED_AT = "2026-09-18T00:00:00+08:00"
METRIC_LABEL = "DRAFT DIAGNOSTIC — NOT FORMAL PAPER RESULTS"
OUT_ROOT = ROOT / "research" / "benchmarks" / "western_pilot_v0_1"
CORPUS_ROOT = ROOT / "research" / "corpus" / "west_v0_1"


def _case(
    topic: str,
    index: int,
    question_type: str,
    answerability: str,
    question: str,
    primary: list[str],
    secondary: list[str],
    points: list[str],
    notes: str,
    difficulty: str,
    lexical_notes: str,
    evidence_dispersion_notes: str,
) -> dict[str, Any]:
    short_topic = "dyspepsia" if topic == "dyspepsia_digestive_symptoms" else topic
    return {
        "case_id": f"westbench-v0.1-{short_topic}-{index:02d}",
        "topic": topic,
        "question": question,
        "question_type": question_type,
        "answerability": answerability,
        "gold_source_ids": [],
        "gold_chunk_ids": primary,
        "optional_secondary_chunk_ids": secondary,
        "expected_evidence_points": points,
        "annotation_notes": notes,
        "difficulty": difficulty,
        "lexical_notes": lexical_notes,
        "evidence_dispersion_notes": evidence_dispersion_notes,
    }


CASES = [
    _case("cough", 1, "direct_evidence", "supported",
          "Which patient-reported questionnaires were used most often to assess cough-related quality of life in asthma studies?",
          ["west-pmc-9038879-28f85582a9b4115e8640"], [],
          ["The review identifies the Leicester Cough Questionnaire as the most commonly used validated cough quality-of-life measure."],
          "Directly supported by the reviewed measurement inventory.", "focused", "Natural wording retains core measurement concepts.", "One primary context."),
    _case("cough", 2, "direct_evidence", "supported",
          "What recording durations and outcome units were reported when researchers objectively monitored cough in asthma?",
          ["west-pmc-9038879-8533223858b16f344f26"], [],
          ["Monitoring periods varied from 6 to 24 hours and studies reported several cough-frequency units."],
          "Directly supported by the cough-monitoring results.", "focused", "Uses descriptive wording rather than the section heading.", "One primary context."),
    _case("cough", 3, "direct_evidence", "supported",
          "Which outcomes improved in studies of non-drug approaches for persistent dry cough, and which outcomes did not clearly improve?",
          ["west-pmc-9397766-add0d821c6dd403b2add"], [],
          ["Some studies reported improvements in cough-related quality of life, cough frequency, and voice outcomes.",
           "The review did not find improvements for several other outcomes and emphasized imprecision and heterogeneity."],
          "The discussion directly contrasts improved and unimproved outcomes.", "focused", "Avoids naming the review or reproducing its title.", "One primary context with multiple outcomes."),
    _case("cough", 4, "direct_evidence", "supported",
          "What did the reviewed evidence report about honey for cough in children, and how certain were those findings?",
          ["west-pmc-8483994-76979379ed5f9201bad5", "west-pmc-8483994-b8e7df0692cb6f53f26c"],
          ["west-pmc-8483994-add712158df8460d7a72"],
          ["Selected pediatric cough outcomes improved in the reviewed studies.",
           "The certainty of the evidence was generally low or very low, with risk-of-bias limitations reported by the review."],
          "Primary chunks directly represent pediatric honey effects and evidence-certainty or risk-of-bias limitations; the conclusion is contextual.", "focused", "Keeps the intervention term but paraphrases the information need.", "One source, two primary contexts plus one contextual conclusion."),
    _case("cough", 5, "paraphrased_retrieval", "supported",
          "Why is it difficult to compare studies that provoke coughing with inhaled irritants?",
          ["west-pmc-9038879-2301d87b8d6502f77de8"], [],
          ["Cough-challenge studies varied in agents, delivery, concentrations, breathing methods, and protocol standardization."],
          "The question paraphrases cough-challenge methodology without naming capsaicin or test endpoints.", "lexically_challenging", "Deliberately replaces corpus terms with a functional description.", "Two contexts from one measurement review."),
    _case("cough", 6, "paraphrased_retrieval", "supported",
          "What kinds of education, breathing, speech, or behavioral components were combined in non-medicine cough programs?",
          ["west-pmc-9397766-15a55796cf9b4fa147c8"], [],
          ["Programs combined components such as cough suppression, education, laryngeal care, breathing exercises, counseling, and related therapies."],
          "Supported by the intervention-characteristics inventory.", "lexically_challenging", "Uses everyday descriptions for multi-component interventions.", "One primary context."),
    _case("cough", 7, "paraphrased_retrieval", "supported",
          "What methodological or data-related challenges does the pilot review describe for COVID-19 screening from recorded cough sounds?",
          ["west-pmc-9138020-27df07ac99d0f7a5bf32", "west-pmc-9138020-102ef6bfec46fbde2625"], [],
          ["Crowdsourced cough datasets can contain variable numbers of coughs per recording and class imbalance between COVID-19-positive and healthy samples.",
           "The reviewed systems also raised methodological concerns including possible overfitting and uncertain laboratory confirmation in some datasets."],
          "Limited to methodological and data challenges documented in the frozen pilot-corpus chunks; no stand-alone screening claim is made.", "lexically_challenging", "Uses recorded cough sounds and methodological challenges rather than the article title.", "Two primary contexts from one screening review."),
    _case("cough", 8, "multi_source_synthesis", "supported",
          "How do the asthma-measurement review and the chronic-cough intervention review use objective cough monitoring and patient-reported measures differently?",
          ["west-pmc-9038879-8533223858b16f344f26", "west-pmc-9038879-28f85582a9b4115e8640", "west-pmc-9397766-cd602e6d7d78a304dc87"],
          [],
          ["The asthma review documents objective cough monitoring and validated patient-reported cough-related quality-of-life measures.",
           "The chronic-cough intervention review uses objective cough counts as an intervention outcome."],
          "Requires measurement evidence from two separate reviews.", "distributed", "Combines measurement concepts without copying headings.", "Three primary contexts across two sources."),
    _case("cough", 9, "multi_source_synthesis", "supported",
          "Across the pilot reviews, what benefits and uncertainties were reported for behavioral or physical cough care and for honey used during respiratory illness?",
          ["west-pmc-9397766-add0d821c6dd403b2add", "west-pmc-8483994-76979379ed5f9201bad5", "west-pmc-8483994-b8e7df0692cb6f53f26c"], [],
          ["Non-drug chronic-cough studies reported selected improvements but could not support confident clinical recommendations.",
           "The reviewed pediatric honey studies reported selected cough benefits, while the overall certainty of evidence was limited or low as reported by the review."],
          "Genuine synthesis of two different intervention evidence contexts.", "distributed", "Avoids article-title phrasing.", "Two distinct sources."),
    _case("cough", 10, "multi_source_synthesis", "partially_supported",
          "What recurring study-design problems limit confidence and cross-study comparison in this pilot's cough evidence?",
          ["west-pmc-9038879-2301d87b8d6502f77de8", "west-pmc-9397766-ed5601ae85fd53f79330", "west-pmc-8483994-b8e7df0692cb6f53f26c"],
          [],
          ["Cough-challenge methods varied across protocols and delivery choices.",
           "Outcome measures varied in validation and applicability to chronic respiratory diseases.",
           "The honey review reported risk-of-bias and evidence-certainty limitations."],
          "Supported across three reviews, but the small pilot cannot characterize all cough-study limitations.", "distributed", "Abstracts limitations into a cross-review question.", "Three primary contexts across three sources."),
    _case("cough", 11, "difficult_or_insufficient", "insufficient",
          "What evidence shows that benefits of non-drug chronic-cough programs persist for a year or longer?",
          [],
          ["west-pmc-9397766-a79b94846f4fff0f1b64", "west-pmc-9397766-eb41c9beb2dcaa6414bc"],
          ["The pilot reports limited follow-up, including a three-month comparison, rather than evidence extending to a year."],
          "Insufficient within the current pilot corpus for durability at one year or longer.", "insufficient_evidence", "The requested time horizon is deliberately beyond the available follow-up.", "One source with limited related evidence."),
    _case("cough", 12, "difficult_or_insufficient", "insufficient",
          "How accurately do cough-sound screening systems generalize across ages, languages, recording devices, and independent hospitals?",
          [], ["west-pmc-9138020-f3916d9c63a2125f0979"], [],
          "Insufficient within the current pilot corpus. A related review discusses potential screening utility but does not provide a complete cross-setting external-validation comparison.",
          "insufficient_evidence", "Requests several validation dimensions not jointly covered.", "One optional topical context; no primary gold evidence."),

    _case("dyspepsia_digestive_symptoms", 1, "direct_evidence", "supported",
          "Which upper-abdominal symptoms does the pilot review use to characterize functional dyspepsia?",
          ["west-pmc-13048936-2c1f410546d3a7ce810f"],
          ["west-pmc-9276094-998ee5d43793f5cfd176"],
          ["The review characterizes the condition with upper-abdominal discomfort, bloating, early satiety, and nausea without an identifiable organic cause."],
          "Directly supported by the introductory clinical description.", "focused", "Does not reproduce the article title.", "One primary source with optional corroboration."),
    _case("dyspepsia_digestive_symptoms", 2, "direct_evidence", "supported",
          "Why did the review avoid a firm effect-size conclusion for physical approaches to functional dyspepsia?",
          ["west-pmc-13048936-e2440fb4365aab41dab8"], [],
          ["Clinical heterogeneity in interventions and outcome measurement prevented quantitative synthesis and firm conclusions."],
          "Directly supported by the review's limitations discussion.", "focused", "Uses physical approaches rather than the exact title phrase.", "One primary context."),
    _case("dyspepsia_digestive_symptoms", 3, "direct_evidence", "supported",
          "How did symptom improvement and reported adverse effects compare between acotiamide and placebo in the pooled evidence?",
          ["west-pmc-8765587-0836db1b440a419b1187"],
          ["west-pmc-8765587-8967a5ee8d664505887b"],
          ["Pooled symptom improvement favored acotiamide but did not reach statistical significance.",
           "The analyzed adverse-effect outcomes did not differ significantly from placebo."],
          "Directly supported by the meta-analytic review passage.", "focused", "Natural comparison question without dosage advice.", "One primary context."),
    _case("dyspepsia_digestive_symptoms", 4, "direct_evidence", "supported",
          "What patterns of anxiety and depression were reported among people with functional dyspepsia?",
          ["west-pmc-6863582-b8b6a36f50c61234408d"], [],
          ["The reviewed study reported frequent anxiety-depression status and associations with demographic and stress-related factors."],
          "Directly supported by a reviewed observational study summary.", "focused", "Avoids copying a source sentence.", "One primary context."),
    _case("dyspepsia_digestive_symptoms", 5, "paraphrased_retrieval", "supported",
          "How were changes in stomach discomfort and daily functioning captured in trials of movement- or body-based care?",
          ["west-pmc-13048936-33262c18fc966e88dec6"], [],
          ["Trials used several questionnaires and visual scales, with heterogeneous outcome instruments across studies."],
          "The question paraphrases physical therapy and questionnaire-based outcomes.", "lexically_challenging", "Uses stomach discomfort and body-based care instead of title vocabulary.", "One primary context."),
    _case("dyspepsia_digestive_symptoms", 6, "paraphrased_retrieval", "supported",
          "Does the pilot describe emotional distress as preceding digestive symptoms, following them, or potentially operating in both directions?",
          ["west-pmc-6863582-a6278a444810db49b1a4"], [],
          ["A prospective study summary supports both brain-to-gut and gut-to-brain pathways over follow-up."],
          "Supported by the reviewed prospective gut-brain study.", "lexically_challenging", "Expresses bidirectionality without using the source's pathway labels.", "One primary context."),
    _case("dyspepsia_digestive_symptoms", 7, "paraphrased_retrieval", "supported",
          "What limits applying the acotiamide findings broadly beyond the populations studied?",
          ["west-pmc-8765587-3c114c87a3f5d8f21749", "west-pmc-8765587-8967a5ee8d664505887b"], [],
          ["The review calls for additional evidence in other population groups before broad generalization."],
          "Directly supports a generalizability limitation.", "lexically_challenging", "Asks about transferability rather than naming geography in the question.", "Two primary contexts from one source."),
    _case("dyspepsia_digestive_symptoms", 8, "multi_source_synthesis", "supported",
          "How do the pilot sources connect stress-focused care and structured exercise with functional dyspepsia symptoms?",
          ["west-pmc-9276094-537533641e03502a852d", "west-pmc-13048936-7c59515f97a38056ad53"], [],
          ["One source frames cognitive-behavioral stress management around stress-related symptoms.",
           "Another reports that structured physical activity may improve symptoms and disease-specific quality of life."],
          "Requires two distinct non-pharmacological evidence contexts.", "distributed", "Combines concepts from two reviews.", "Two primary sources."),
    _case("dyspepsia_digestive_symptoms", 9, "multi_source_synthesis", "supported",
          "How do the certainty limitations differ between the acotiamide evidence and the evidence for physical approaches?",
          ["west-pmc-8765587-0836db1b440a419b1187", "west-pmc-13048936-e2440fb4365aab41dab8"], [],
          ["The acotiamide pooled symptom estimate did not reach statistical significance.",
           "Physical-approach evidence was too heterogeneous for a confident pooled effect."],
          "The corpus supports the two limitations but not a formal comparative certainty assessment.", "distributed", "Frames cross-review limitations rather than treatments alone.", "Two primary sources."),
    _case("dyspepsia_digestive_symptoms", 10, "multi_source_synthesis", "supported",
          "What roles do psychological stress and gut-brain interaction play across the pilot's functional-dyspepsia sources?",
          ["west-pmc-6863582-a6278a444810db49b1a4", "west-pmc-9276094-e88a5b7371723236f824"],
          ["west-pmc-13048936-91e4325b47718b511b4d"],
          ["The sources associate psychological factors and stress with symptom development or severity.",
           "They describe stress-management, relaxation, or breathing approaches as research targets."],
          "Synthesis spans prospective, behavioral, and intervention-review contexts.", "distributed", "Uses broad mechanism and management language.", "Two primary sources plus one optional context."),
    _case("dyspepsia_digestive_symptoms", 11, "difficult_or_insufficient", "insufficient",
          "What does the pilot establish about symptom benefits from physical interventions several years after treatment?",
          [], ["west-pmc-13048936-093bc121c3548052ff42"],
          ["The review identifies potential short-term adjunctive value but calls for further trials and does not establish multi-year durability."],
          "Insufficient within the current pilot corpus for multi-year durability.", "insufficient_evidence", "The multi-year horizon exceeds the reviewed evidence.", "One source with partial contextual support."),
    _case("dyspepsia_digestive_symptoms", 12, "difficult_or_insufficient", "insufficient",
          "Which non-drug strategy is superior when exercise, breathing feedback, nerve stimulation, and cognitive stress management are compared head to head?",
          [], ["west-pmc-13048936-e2440fb4365aab41dab8", "west-pmc-9276094-e88a5b7371723236f824"], [],
          "Insufficient within the current pilot corpus. Related sources discuss these approaches, but no complete head-to-head comparison establishes a superior strategy.",
          "insufficient_evidence", "Asks for a comparative ranking absent from the pilot.", "Two optional sources; no primary gold evidence."),

    _case("headache", 1, "direct_evidence", "supported",
          "What recurring visual-processing pattern did brain magnetic-recording studies report in migraine?",
          ["west-pmc-11794981-8e314d4592c444b92ec6"],
          ["west-pmc-11794981-153ace40b735f2139ef8"],
          ["Visual studies repeatedly reported increased P100m amplitude with repeated stimulation, consistent with altered sensory processing."],
          "Directly supported by the sensorimotor discussion.", "focused", "Uses brain magnetic-recording instead of the modality acronym.", "One primary context."),
    _case("headache", 2, "direct_evidence", "supported",
          "Why are findings from resting-state brain magnetic recordings hard to compare across migraine studies?",
          ["west-pmc-11794981-e9f813e5f5b063b58fe4"], [],
          ["Studies varied in migraine subtypes, clinical characteristics, timing definitions, medication reporting, and reporting standards."],
          "Directly supported by the review's limitations.", "focused", "Avoids copying the exact section heading.", "One primary context."),
    _case("headache", 3, "direct_evidence", "supported",
          "Which preventive drug classes or agents showed benefits for chronic migraine in the reviewed large trials?",
          ["west-pmc-12659810-959a4d5c0acee2aa76d6"], [],
          ["The review reports benefits for eptinezumab, onabotulinumtoxinA, fremanezumab, and galcanezumab across selected outcomes."],
          "Directly supported by the review conclusion; no prescribing or dosing is requested.", "focused", "Summarizes trial findings without copying the article title.", "One primary context."),
    _case("headache", 4, "direct_evidence", "supported",
          "How did pooled migraine and tension-type headache prevalence compare in the reviewed Chinese populations?",
          ["west-pmc-12867494-1cb508b1279f48d5958d"],
          ["west-pmc-12867494-2397d31a7d4db4bdce01", "west-pmc-12867494-9726230a3b4317351006"],
          ["The review reported a lower pooled prevalence for migraine than for tension-type headache in China."],
          "Primary discussion with optional detailed prevalence contexts.", "focused", "Uses a comparative question rather than title wording.", "One source with multiple contexts."),
    _case("headache", 5, "paraphrased_retrieval", "supported",
          "What objective sleep findings might help explain why people with migraine report poor sleep despite mixed laboratory results?",
          ["west-pmc-12857048-81541b38c2c2eee9d14e"],
          ["west-pmc-12857048-f23d7bdac2eec846ef2c"],
          ["Some studies report more awakenings, sleep fragmentation, and reduced sleep efficiency despite heterogeneous findings."],
          "Supported by the sleep review discussion and optional detailed results.", "lexically_challenging", "Uses poor sleep and laboratory results rather than architecture terminology.", "One source, two contexts."),
    _case("headache", 6, "paraphrased_retrieval", "supported",
          "How much population evidence did the pilot find for the rarer headache disorder marked by attacks in clusters?",
          ["west-pmc-12867494-8088b6cb5b898e70377f", "west-pmc-12867494-85fa80d722354ad45cbe"],
          [],
          ["Only one large study supplied prevalence data, and the review calls the evidence limited."],
          "The wording avoids using the exact disorder label as the main retrieval phrase.", "lexically_challenging", "Paraphrases cluster headache before naming population evidence.", "One source with discussion and optional numeric result."),
    _case("headache", 7, "paraphrased_retrieval", "supported",
          "Which dimensions of migraine have brain magnetic-recording studies emphasized, and which human dimension has received little attention?",
          ["west-pmc-11794981-08916fb3154950d0d2a2"], [],
          ["The literature emphasizes sensory dysfunction while the affective dimension remains comparatively underexplored."],
          "Directly supported by the review conclusion but phrased without its modality acronym.", "lexically_challenging", "Substitutes conceptual descriptions for source terminology.", "One primary context."),
    _case("headache", 8, "multi_source_synthesis", "supported",
          "Across objective brain and sleep studies, what forms of heterogeneity limit stable biomarkers for migraine?",
          ["west-pmc-11794981-898811886f00628ef49e", "west-pmc-12857048-e5b1db5478f67338c9a1"], [],
          ["Resting-state brain findings are mixed and sleep studies vary by population, phase, methods, and reporting.",
           "Both reviews call for larger or more harmonized studies."],
          "Genuine synthesis of two objective-measurement literatures.", "distributed", "Uses biomarker framing not present as a shared title phrase.", "Two distinct sources."),
    _case("headache", 9, "multi_source_synthesis", "supported",
          "How do the pilot reviews portray the burden of primary headache and the current focus of neurophysiological research?",
          ["west-pmc-12867494-784987cf4ce3d25249eb", "west-pmc-11794981-08916fb3154950d0d2a2"], [],
          ["One source describes substantial disability and societal burden from migraine and other primary headaches.",
           "Another finds that neurophysiological research has concentrated on sensory features and leaves important dimensions underexplored."],
          "Combines epidemiological burden with a research-gap context.", "distributed", "No title or identifier exposure.", "Two distinct sources."),
    _case("headache", 10, "multi_source_synthesis", "partially_supported",
          "What do the pilot sources contribute about chronic-migraine management and sleep-related impairment, and what remains uncertain?",
          ["west-pmc-12659810-959a4d5c0acee2aa76d6", "west-pmc-12857048-81541b38c2c2eee9d14e"], [],
          ["One review reports benefits for several preventive therapies in selected trials.",
           "Another reports sleep fragmentation and reduced efficiency amid heterogeneous findings."],
          "The sources cover separate management and sleep contexts but do not establish their interaction.", "distributed", "Cross-context wording tests synthesis without implying causality.", "Two distinct sources."),
    _case("headache", 11, "difficult_or_insufficient", "partially_supported",
          "Can brain magnetic-recording features currently predict which migraine treatment will work for an individual?",
          ["west-pmc-11794981-ab62ede709574b85f05d"], [],
          ["The review describes preliminary promise but says larger, adequately powered studies are needed before treatment-response prediction is established."],
          "Individual prediction is not established within the current pilot corpus.", "insufficient_evidence", "Requests predictive readiness rather than descriptive findings.", "One source with partial future-facing evidence."),
    _case("headache", 12, "difficult_or_insufficient", "insufficient",
          "Which chronic-migraine medicine is best in direct long-term comparisons across refractory and comorbid patient groups?",
          ["west-pmc-12659810-4d3c4232df85cc66571e"], [],
          ["The review identifies head-to-head comparisons and long-term outcomes as continuing research needs."],
          "Insufficient within the current pilot corpus. The related review does not establish a best therapy through direct long-term comparative evidence.",
          "insufficient_evidence", "Requests a ranking and comparison beyond the available review evidence.", "One source documents the limitation."),

    _case("constipation", 1, "direct_evidence", "supported",
          "Which symptom domains commonly appear in patient-reported constipation measures?",
          ["west-pmc-9274467-c2111b5653c70be051a9"], [],
          ["Common domains include abdominal pain, bloating, bowel-movement frequency, and straining."],
          "Directly supported by the outcome-measure inventory.", "focused", "Uses patient-reported measures without the exact section heading.", "One primary context."),
    _case("constipation", 2, "direct_evidence", "supported",
          "Which areas of daily life were covered by constipation-specific quality-of-life questionnaires?",
          ["west-pmc-9274467-cb43cb6dde16fa707aff"], [],
          ["Measures covered social relationships, treatment satisfaction, physical symptoms, diet, daily activities, and psychological state."],
          "Directly supported by the quality-of-life measure review.", "focused", "Natural educational wording.", "One primary context."),
    _case("constipation", 3, "direct_evidence", "supported",
          "Which factors were associated with variation in constipation prevalence among children across Asian studies?",
          ["west-pmc-11007433-953693e44358ee30c0c7"], [],
          ["The review reports variation by diagnostic approach, population source, age, mental health, and dietary fibre evidence."],
          "Directly supported by the review discussion.", "focused", "Avoids copying the article title.", "One primary context."),
    _case("constipation", 4, "direct_evidence", "supported",
          "What did the pooled pediatric studies report when surface electrical nerve stimulation was added to other constipation care?",
          ["west-pmc-9960109-b68f677b72c9f0f54d27"], [],
          ["The pooled studies favored transcutaneous neuromodulation used with other therapies over comparison care."],
          "Directly supported by the constipation meta-analysis result.", "focused", "Uses a descriptive intervention phrase rather than the title.", "One primary context."),
    _case("constipation", 5, "paraphrased_retrieval", "supported",
          "How have electronic diaries, handheld devices, websites, and automated telephone systems been used to collect constipation outcomes?",
          ["west-pmc-9274467-d51f99e15cdd2bcfbf7e"], [],
          ["The review describes several digital administration formats but notes limited reporting about digitization and validation procedures."],
          "Supported by the digitization results.", "lexically_challenging", "Names delivery modes rather than the formal measurement acronym.", "One primary context."),
    _case("constipation", 6, "paraphrased_retrieval", "supported",
          "Did estimates of childhood constipation differ between community samples and children recruited through clinics?",
          ["west-pmc-11007433-5d3dc00ba3de9d134e91"], [],
          ["The review reported a higher pooled prevalence in community-based than clinic-based populations."],
          "Directly supported by the population-source result.", "lexically_challenging", "Uses recruitment-setting language rather than the section label.", "One primary context."),
    _case("constipation", 7, "paraphrased_retrieval", "supported",
          "Why do the microbial-transfer findings for chronic constipation remain suggestive rather than causal?",
          ["west-pmc-12350361-4430013e63c1a6994d74"], [],
          ["Most included studies were single-arm and only one underpowered randomized trial was available, limiting causal inference."],
          "Supported by the intervention review's methodological limitation.", "lexically_challenging", "Uses microbial transfer instead of the intervention acronym.", "One primary context."),
    _case("constipation", 8, "multi_source_synthesis", "supported",
          "How do differences in diagnostic definitions and outcome questionnaires complicate comparison of constipation studies?",
          ["west-pmc-11007433-107af14f8b2f92ec741e", "west-pmc-9274467-bfe8d88a2a851dcdec78", "west-pmc-9274467-b6353bcaa4ccce5bb790"], [],
          ["The prevalence literature used differing diagnostic criteria, while the PROM review identified numerous instruments spanning different symptom or quality-of-life and administration contexts."],
          "Synthesis spans epidemiological definitions and patient-reported measurement.", "distributed", "Uses comparison framing across two evidence types.", "Two distinct sources."),
    _case("constipation", 9, "multi_source_synthesis", "supported",
          "What different questions do the pediatric prevalence review and the pediatric nerve-stimulation review answer about constipation?",
          ["west-pmc-11007433-953693e44358ee30c0c7", "west-pmc-9960109-b68f677b72c9f0f54d27"], [],
          ["The prevalence review estimates frequency and associated factors across Asian populations.",
           "The intervention review evaluates improvement when neuromodulation is added to other therapy."],
          "Tests synthesis of epidemiological and intervention evidence without conflating them.", "distributed", "Asks about evidence roles rather than article titles.", "Two distinct sources."),
    _case("constipation", 10, "multi_source_synthesis", "supported",
          "What design limitations affect confidence in the pilot's adult microbial-transfer and pediatric nerve-stimulation evidence?",
          ["west-pmc-12350361-4430013e63c1a6994d74", "west-pmc-9960109-ace43e7cc9b1742391d2"], [],
          ["The microbial-transfer evidence is dominated by single-arm studies with one underpowered randomized trial.",
           "The pediatric neuromodulation review reports a paucity of randomized trials and cannot isolate the intervention alone."],
          "Two-source limitations synthesis; broader intervention certainty remains outside this pilot.", "distributed", "Abstracts study-design limitations across age groups.", "Two distinct sources."),
    _case("constipation", 11, "difficult_or_insufficient", "partially_supported",
          "How well have digital constipation questionnaires been culturally validated across multiple Asian languages and populations?",
          ["west-pmc-9274467-fa30c2a8dfb6e32c5342", "west-pmc-9274467-d51f99e15cdd2bcfbf7e"], [],
          ["The review identifies only two measures developed and validated in Asian cultural contexts and limited reporting for digital formats."],
          "The pilot gives examples but does not establish broad multilingual cultural validation.", "insufficient_evidence", "Combines cultural and digital validation dimensions.", "Two contexts from one source."),
    _case("constipation", 12, "difficult_or_insufficient", "insufficient",
          "What is the long-term comparative effectiveness of microbial transfer, nerve stimulation, and standard therapy across children and adults?",
          ["west-pmc-12350361-4430013e63c1a6994d74", "west-pmc-9960109-ace43e7cc9b1742391d2"], [],
          ["Both intervention reviews identify important trial-design limitations and needs for stronger randomized evidence."],
          "Insufficient within the current pilot corpus. The sources do not provide a shared long-term head-to-head comparison across interventions and age groups.",
          "insufficient_evidence", "Requests a comparative longitudinal conclusion beyond the source designs.", "Two sources document related limitations."),
]


ADJUDICATION_BEFORE: dict[str, dict[str, Any]] = {
    "westbench-v0.1-cough-04": {
        "gold_chunk_ids": ["west-pmc-8483994-add712158df8460d7a72"],
        "optional_secondary_chunk_ids": ["west-pmc-8483994-76979379ed5f9201bad5"],
        "expected_evidence_points": [
            "The review reported reductions in cough duration, severity, or impact in children.",
            "Most evidence was rated low or very low certainty.",
        ],
        "annotation_notes": "Primary conclusion plus an optional detailed results context.",
        "evidence_dispersion_notes": "One source, two complementary contexts.",
    },
    "westbench-v0.1-cough-05": {
        "gold_chunk_ids": [
            "west-pmc-9038879-b3d6f4e9794c5be05447",
            "west-pmc-9038879-2301d87b8d6502f77de8",
        ],
    },
    "westbench-v0.1-cough-07": {
        "question": "What cautions does the pilot evidence raise about treating recorded cough audio as a stand-alone screen for coronavirus infection?",
        "gold_chunk_ids": ["west-pmc-9138020-f3916d9c63a2125f0979"],
        "expected_evidence_points": [
            "The review treats cough sound as potentially useful but not as the only reliable screening signal."
        ],
        "annotation_notes": "Supported by the review discussion; this is not a diagnostic recommendation.",
        "lexical_notes": "Uses recorded audio and stand-alone screening rather than the article title.",
        "evidence_dispersion_notes": "One primary context.",
    },
    "westbench-v0.1-cough-08": {
        "question": "How do objective cough counts and patient-reported impact measures complement one another in cough research?",
        "gold_chunk_ids": [
            "west-pmc-9038879-8533223858b16f344f26",
            "west-pmc-9397766-cd602e6d7d78a304dc87",
        ],
        "optional_secondary_chunk_ids": ["west-pmc-9038879-28f85582a9b4115e8640"],
        "expected_evidence_points": [
            "Objective monitoring quantifies cough frequency while questionnaires characterize perceived burden and quality of life.",
            "The two kinds of outcomes need not align closely.",
        ],
        "evidence_dispersion_notes": "Two primary sources plus one optional questionnaire context.",
    },
    "westbench-v0.1-cough-09": {
        "gold_chunk_ids": [
            "west-pmc-9397766-add0d821c6dd403b2add",
            "west-pmc-8483994-add712158df8460d7a72",
        ],
        "expected_evidence_points": [
            "Non-drug chronic-cough studies reported selected improvements but could not support confident clinical recommendations.",
            "Honey studies reported selected cough benefits alongside low-certainty evidence and mixed adult findings.",
        ],
    },
    "westbench-v0.1-cough-10": {
        "gold_source_ids": ["west-pmc-9038879", "west-pmc-9397766"],
        "gold_chunk_ids": [
            "west-pmc-9038879-5e17be79d6dbfd5a1bce",
            "west-pmc-9397766-add0d821c6dd403b2add",
        ],
        "optional_secondary_chunk_ids": ["west-pmc-8483994-b8e7df0692cb6f53f26c"],
        "expected_evidence_points": [
            "Reviews report inconsistent measurement, heterogeneous interventions or timing, small samples, imprecision, and risk-of-bias concerns."
        ],
        "evidence_dispersion_notes": "Two primary sources and one optional third source.",
    },
    "westbench-v0.1-cough-11": {
        "answerability": "partially_supported",
        "gold_source_ids": ["west-pmc-9397766"],
        "gold_chunk_ids": ["west-pmc-9397766-a79b94846f4fff0f1b64"],
        "optional_secondary_chunk_ids": ["west-pmc-9397766-eb41c9beb2dcaa6414bc"],
        "annotation_notes": "Only shorter follow-up is available; year-long durability is not established within the current pilot corpus.",
    },
    "westbench-v0.1-dyspepsia-03": {
        "optional_secondary_chunk_ids": [],
    },
    "westbench-v0.1-dyspepsia-07": {
        "gold_chunk_ids": ["west-pmc-8765587-8967a5ee8d664505887b"],
        "expected_evidence_points": [
            "Most included studies were conducted in Japanese populations, and the review calls for evidence in other populations."
        ],
        "evidence_dispersion_notes": "One primary context.",
    },
    "westbench-v0.1-dyspepsia-09": {
        "answerability": "partially_supported",
    },
    "westbench-v0.1-dyspepsia-11": {
        "answerability": "partially_supported",
        "gold_source_ids": ["west-pmc-13048936"],
        "gold_chunk_ids": ["west-pmc-13048936-093bc121c3548052ff42"],
        "optional_secondary_chunk_ids": [],
        "annotation_notes": "Long-term durability is not established within the current pilot corpus.",
    },
    "westbench-v0.1-headache-01": {
        "gold_chunk_ids": ["west-pmc-11794981-153ace40b735f2139ef8"],
        "optional_secondary_chunk_ids": [],
    },
    "westbench-v0.1-headache-06": {
        "gold_chunk_ids": ["west-pmc-12867494-85fa80d722354ad45cbe"],
        "optional_secondary_chunk_ids": ["west-pmc-12867494-8088b6cb5b898e70377f"],
    },
    "westbench-v0.1-constipation-08": {
        "gold_chunk_ids": [
            "west-pmc-11007433-107af14f8b2f92ec741e",
            "west-pmc-9274467-b6353bcaa4ccce5bb790",
        ],
        "expected_evidence_points": [
            "Prevalence estimates vary with diagnostic methods and study populations.",
            "Patient-reported measures vary in target populations, purposes, administration, and measured outcomes.",
        ],
    },
    "westbench-v0.1-constipation-10": {
        "answerability": "partially_supported",
    },
}


ADJUDICATION_RATIONALES = {
    "westbench-v0.1-cough-04": "Represent pediatric honey effects and evidence certainty or risk of bias with separate direct chunks; retain the conclusion as context.",
    "westbench-v0.1-cough-05": "Keep only the chunk that directly describes cough-challenge methodology variation as primary gold.",
    "westbench-v0.1-cough-07": "Limit the information need and gold evidence to documented methodological and data challenges in cough-sound screening.",
    "westbench-v0.1-cough-08": "Directly represent objective monitoring, patient-reported quality of life, and objective intervention outcomes without an unsupported alignment claim.",
    "westbench-v0.1-cough-09": "Use direct pediatric honey-effect and certainty or risk-of-bias evidence and remove the unsupported mixed-adult-findings phrase.",
    "westbench-v0.1-cough-10": "Represent each limitation category with direct primary evidence and remove unsupported broadening.",
    "westbench-v0.1-cough-11": "The pilot does not establish durability at one year or longer; shorter follow-up is contextual only.",
    "westbench-v0.1-dyspepsia-03": "Add explicit secondary evidence for the adverse-event component of the question.",
    "westbench-v0.1-dyspepsia-07": "Use direct evidence calling for studies in other population groups; retain the existing chunk because its full text also supports that limitation.",
    "westbench-v0.1-dyspepsia-09": "Both primary chunks directly support the two requested limitations.",
    "westbench-v0.1-dyspepsia-11": "The pilot does not establish multi-year durability; short-term or potential-benefit evidence is contextual only.",
    "westbench-v0.1-headache-01": "Promote the chunk that directly states the repeated-stimulation P100m amplitude pattern and retain the broader interpretation as context.",
    "westbench-v0.1-headache-06": "Make both the one-study prevalence evidence and limited-data interpretation primary because the question asks how much evidence exists.",
    "westbench-v0.1-constipation-08": "Directly represent differing diagnostic criteria and the number and range of PROM instruments and contexts without claiming separately quantified heterogeneity.",
    "westbench-v0.1-constipation-10": "Both existing primary chunks directly state the requested study-design limitations.",
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _materialize_cases(corpus) -> list[dict[str, Any]]:
    chunks = {item.chunk_id: item for item in corpus.chunks}
    materialized = json.loads(json.dumps(CASES))
    for case in materialized:
        case["gold_source_ids"] = sorted({chunks[item].source_id for item in case["gold_chunk_ids"] if item in chunks})
    return materialized


def _secondary_model_adjudication(cases: list[dict[str, Any]]) -> dict[str, Any]:
    cases_by_id = {case["case_id"]: case for case in cases}
    changes: list[dict[str, Any]] = []
    for case_id, before_fields in ADJUDICATION_BEFORE.items():
        case = cases_by_id[case_id]
        for field, before in before_fields.items():
            after = case[field]
            if before == after:
                raise ValueError(f"Adjudication field did not change: {case_id}.{field}")
            changes.append({
                "case_id": case_id,
                "field": field,
                "before": before,
                "after": after,
                "rationale": ADJUDICATION_RATIONALES[case_id],
            })
    return {
        "adjudicated_case_count": len(ADJUDICATION_BEFORE),
        "unchanged_case_count": len(cases) - len(ADJUDICATION_BEFORE),
        "changed_field_record_count": len(changes),
        "secondary_reviewer_type": "ai_model",
        "secondary_reviewer_model": "GPT-5.6 Sol",
        "review_basis": "frozen_pilot_corpus_review_packet",
        "human_verified": False,
        "domain_expert_verified": False,
        "changes": changes,
    }


async def _r0_diagnostic(cases: list[dict[str, Any]], corpus) -> dict[str, Any]:
    retriever = WesternRetriever(corpus=corpus)
    chunks_by_id = {item.chunk_id: item for item in corpus.chunks}
    rows: list[dict[str, Any]] = []
    eligible_rows: list[dict[str, Any]] = []
    partial_or_insufficient: list[dict[str, Any]] = []
    miss_reasons: Counter[str] = Counter()
    for case in cases:
        results = await retriever.search(case["question"], WesternTopic(case["topic"]), top_k=4)
        retrieved_ids = [item.chunk_id for item in results]
        retrieved_sources = [item.source_id for item in results]
        primary = list(case["gold_chunk_ids"])
        primary_sources = list(case["gold_source_ids"])
        chunk_hits = [item for item in primary if item in retrieved_ids]
        source_hits = [item for item in primary_sources if item in retrieved_sources]
        first_rank = next((index + 1 for index, item in enumerate(retrieved_ids) if item in set(primary)), None)
        row = {
            "case_id": case["case_id"],
            "topic": case["topic"],
            "question_type": case["question_type"],
            "answerability": case["answerability"],
            "retrieved_chunk_ids": retrieved_ids,
            "retrieved_source_ids": retrieved_sources,
            "primary_gold_chunk_count": len(primary),
            "primary_gold_chunk_hits": chunk_hits,
            "primary_gold_source_count": len(primary_sources),
            "primary_gold_source_hits": source_hits,
            "primary_gold_chunk_recall_at_4": round(len(chunk_hits) / len(primary), 6) if primary else None,
            "source_recall_at_4": round(len(source_hits) / len(primary_sources), 6) if primary_sources else None,
            "reciprocal_rank": round(1 / first_rank, 6) if first_rank else (0.0 if primary else None),
            "hit_at_4": bool(chunk_hits) if primary else None,
        }
        if case["answerability"] in {"supported", "partially_supported"} and primary:
            eligible_rows.append(row)
        if primary and len(chunk_hits) < len(primary):
            if case["question_type"] == "paraphrased_retrieval":
                reason = "A_legitimate_lexical_mismatch"
            elif case["question_type"] == "multi_source_synthesis" and chunk_hits:
                reason = "B_evidence_distributed_across_sources"
            elif case["question_type"] == "difficult_or_insufficient":
                reason = "D_ambiguous_or_deliberately_difficult_query"
            else:
                reason = "F_retrieval_weakness"
            row["likely_miss_reason"] = reason
            miss_reasons[reason] += 1
        rows.append(row)
        if case["answerability"] in {"partially_supported", "insufficient"}:
            optional = set(case["optional_secondary_chunk_ids"])
            optional_hits = [item for item in retrieved_ids if item in optional]
            if chunk_hits or optional_hits:
                observation = "returned_genuinely_useful_partial_evidence"
            elif results:
                observation = "returned_topical_but_non_answering_evidence"
            else:
                observation = "returned_no_useful_support"
            partial_or_insufficient.append({
                "case_id": case["case_id"],
                "answerability": case["answerability"],
                "observation": observation,
                "primary_hits": chunk_hits,
                "optional_secondary_hits": optional_hits,
                "false_confidence_risk": case["answerability"] == "insufficient" and bool(results),
                "note": "Topical retrieval does not change the benchmark answerability label.",
            })
    def aggregate(group: list[dict[str, Any]]) -> dict[str, Any]:
        denominator = len(group)
        total_gold = sum(row["primary_gold_chunk_count"] for row in group)
        total_hits = sum(len(row["primary_gold_chunk_hits"]) for row in group)
        total_sources = sum(row["primary_gold_source_count"] for row in group)
        total_source_hits = sum(len(row["primary_gold_source_hits"]) for row in group)
        return {
            "metric_label": METRIC_LABEL,
            "case_denominator": denominator,
            "macro_primary_gold_chunk_recall_at_4": round(
                sum(row["primary_gold_chunk_recall_at_4"] for row in group) / denominator, 6
            ),
            "aggregate_primary_gold_chunk_hits": total_hits,
            "aggregate_primary_gold_chunks": total_gold,
            "aggregate_primary_gold_chunk_recall_at_4": round(total_hits / total_gold, 6),
            "macro_source_recall_at_4": round(
                sum(row["source_recall_at_4"] for row in group) / denominator, 6
            ),
            "aggregate_primary_gold_source_hits": total_source_hits,
            "aggregate_primary_gold_sources": total_sources,
            "aggregate_source_recall_at_4": round(total_source_hits / total_sources, 6),
            "mrr": round(sum(row["reciprocal_rank"] for row in group) / denominator, 6),
            "hit_at_4": round(sum(1 for row in group if row["hit_at_4"]) / denominator, 6),
        }

    overall = aggregate(eligible_rows)
    denominator = overall["case_denominator"]
    return {
        "metric_label": METRIC_LABEL,
        "retrieval_strategy": "R0 lexical",
        "top_k": 4,
        "eligibility": "supported or partially_supported cases with at least one primary gold chunk",
        "case_denominator": denominator,
        "primary_gold_chunk_recall_at_4": {
            "metric_label": METRIC_LABEL,
            "formula": "macro mean over eligible cases of (primary gold chunks retrieved in top 4 / primary gold chunks)",
            "macro_case_recall": overall["macro_primary_gold_chunk_recall_at_4"],
            "aggregate_hits": overall["aggregate_primary_gold_chunk_hits"],
            "aggregate_primary_gold_chunks": overall["aggregate_primary_gold_chunks"],
            "aggregate_recall": overall["aggregate_primary_gold_chunk_recall_at_4"],
        },
        "source_recall_at_4": {
            "metric_label": METRIC_LABEL,
            "formula": "macro mean over eligible cases of (primary gold sources represented in top 4 / primary gold sources)",
            "macro_case_recall": overall["macro_source_recall_at_4"],
            "aggregate_hits": overall["aggregate_primary_gold_source_hits"],
            "aggregate_primary_gold_sources": overall["aggregate_primary_gold_sources"],
            "aggregate_recall": overall["aggregate_source_recall_at_4"],
        },
        "mrr": {
            "metric_label": METRIC_LABEL,
            "formula": "mean reciprocal rank of first primary gold chunk over eligible cases",
            "denominator": denominator,
            "value": overall["mrr"],
        },
        "hit_at_4": {
            "metric_label": METRIC_LABEL,
            "denominator": denominator,
            "hits": sum(1 for row in eligible_rows if row["hit_at_4"]),
            "value": overall["hit_at_4"],
        },
        "per_topic": {
            topic: aggregate([row for row in eligible_rows if row["topic"] == topic])
            for topic in VALID_TOPICS
        },
        "per_question_type": {
            question_type: aggregate([row for row in eligible_rows if row["question_type"] == question_type])
            for question_type in VALID_QUESTION_TYPES
            if any(row["question_type"] == question_type for row in eligible_rows)
        },
        "miss_reason_counts": dict(sorted(miss_reasons.items())),
        "partial_and_insufficient_observations": partial_or_insufficient,
        "cases": rows,
    }


def main() -> None:
    corpus = load_runtime_corpus(CORPUS_ROOT)
    cases = _materialize_cases(corpus)
    validation = validate_benchmark(cases, corpus.sources, corpus.chunks)
    if validation["hard_errors"]:
        raise SystemExit(json.dumps(validation, indent=2))
    leakage = leakage_audit(cases, corpus.sources, corpus.chunks)
    coverage = coverage_audit(cases, corpus.sources, corpus.chunks)
    r0 = asyncio.run(_r0_diagnostic(cases, corpus))
    adjudication = _secondary_model_adjudication(cases)

    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    benchmark_path = OUT_ROOT / "benchmark.jsonl"
    benchmark_path.write_text(
        "".join(json.dumps(item, ensure_ascii=False, sort_keys=True) + "\n" for item in cases),
        encoding="utf-8",
    )
    difficulty_counts = Counter(case["difficulty"] for case in cases)
    topic_report = {
        "benchmark_name": BENCHMARK_NAME,
        "case_count": len(cases),
        "topic_counts": validation["topic_counts"],
        "question_type_counts": validation["question_type_counts"],
        "answerability_counts": validation["answerability_counts"],
        "difficulty_metadata_counts": dict(sorted(difficulty_counts.items())),
        "difficulty_quota": "none; descriptive metadata only",
        "per_topic_question_type_counts": validation["per_topic_question_type_counts"],
        "per_topic_answerability_counts": validation["per_topic_answerability_counts"],
    }
    _write_json(OUT_ROOT / "reports" / "benchmark_validation.json", validation)
    _write_json(OUT_ROOT / "reports" / "leakage_audit.json", leakage)
    _write_json(OUT_ROOT / "reports" / "topic_distribution.json", topic_report)
    _write_json(OUT_ROOT / "reports" / "corpus_coverage.json", coverage)
    _write_json(OUT_ROOT / "reports" / "r0_retrieval_diagnostic.json", r0)
    _write_json(OUT_ROOT / "reports" / "secondary_model_adjudication.json", adjudication)
    _write_json(OUT_ROOT / "reports" / "annotation_corrections.json", {
        "correction_count": 1,
        "corrections": [{
            "case_id": "westbench-v0.1-cough-10",
            "field": "optional_secondary_chunk_ids",
            "old_annotation": "west-pmc-8483994-b8e7df0692cb6f53f26",
            "new_annotation": "west-pmc-8483994-b8e7df0692cb6f53f26c",
            "reason": "Corrected a one-character transcription error after referential-integrity validation; question and evidence meaning were unchanged.",
        }],
    })

    source_manifest = json.loads((CORPUS_ROOT / "manifest.json").read_text(encoding="utf-8"))
    manifest = {
        "benchmark_name": BENCHMARK_NAME,
        "benchmark_version": BENCHMARK_VERSION,
        "benchmark_status": "draft_for_manual_review",
        "corpus_name": source_manifest["corpus_name"],
        "corpus_version": source_manifest["corpus_version"],
        "corpus_chunks_sha256": _sha256(CORPUS_ROOT / "chunks.jsonl"),
        "corpus_source_registry_sha256": _sha256(CORPUS_ROOT / "source_registry.json"),
        "benchmark_sha256": _sha256(benchmark_path),
        "benchmark_case_count": len(cases),
        "topic_counts": validation["topic_counts"],
        "question_type_counts": validation["question_type_counts"],
        "answerability_counts": validation["answerability_counts"],
        "annotation_method": "AI-assisted draft annotation with secondary AI-model adjudication against the frozen pilot-corpus review packet; human and domain-expert verification remain pending.",
        "generation_policy": "ai_assisted_draft_secondary_model_reviewed",
        "secondary_reviewer_type": "ai_model",
        "secondary_reviewer_model": "GPT-5.6 Sol",
        "review_basis": "frozen_pilot_corpus_review_packet",
        "human_verified": False,
        "domain_expert_verified": False,
        "build_git_commit": BUILD_COMMIT,
        "created_at": CREATED_AT,
        "scientific_scope": [
            "retrieval quality within the frozen 16-source, 271-chunk Western pilot corpus",
            "future evidence-grounded answer support evaluation",
            "abstention and insufficient-evidence behavior",
            "provenance integrity",
            "future runtime reliability and latency evaluation",
        ],
        "limitations": [
            "Not a benchmark of general or comprehensive Western medical knowledge.",
            "Not a benchmark of clinical correctness, diagnosis, treatment, guideline adherence, safety, or physician performance.",
            "Draft gold annotations require manual review before any formal experiment freeze.",
            "Retrieval diagnostics are draft diagnostics and are not formal paper results.",
        ],
    }
    _write_json(OUT_ROOT / "benchmark_manifest.json", manifest)
    print(json.dumps({
        "validation": validation,
        "leakage": leakage,
        "coverage_summary": {
            "distinct_gold_sources": coverage["distinct_gold_sources"],
            "distinct_primary_gold_chunks": coverage["distinct_primary_gold_chunks"],
            "distinct_primary_or_secondary_gold_chunks": coverage["distinct_primary_or_secondary_gold_chunks"],
        },
        "r0_summary": {
            "case_denominator": r0["case_denominator"],
            "chunk_recall": r0["primary_gold_chunk_recall_at_4"],
            "source_recall": r0["source_recall_at_4"],
            "mrr": r0["mrr"],
        },
    }, indent=2))


if __name__ == "__main__":
    main()
