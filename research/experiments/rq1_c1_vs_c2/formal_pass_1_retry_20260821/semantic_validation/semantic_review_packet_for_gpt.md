# External GPT semantic review instructions

This packet contains the existing frozen 60-item blinded sample. Do not change item_id values.

The reviewer is NOT evaluating whether the TCM/medical information is clinically true.

The only question is:

"Does the supplied ANSWER express the meaning of the supplied GOLD ATOMIC FACT?"

Use only the Question, Gold atomic fact, supplied evidence, and Answer. Do NOT use external medical knowledge.

Labels:

- SUPPORTED: The answer clearly expresses the full substantive meaning of the Gold fact. Paraphrases are allowed.
- PARTIALLY_SUPPORTED: The answer expresses a meaningful part of the Gold fact but omits an important component.
- NOT_SUPPORTED: The Gold fact is absent from the answer.
- CONTRADICTED: The answer states something incompatible with the Gold fact.
- UNRESOLVED: The comparison is genuinely ambiguous.

For each item return item_id, review_label, short review_reason, and confidence (HIGH, MEDIUM, or LOW). Leave no item out and do not alter item_id. Do not infer an herb–syndrome relationship that is not established by the supplied material.

This is AI-assisted semantic review, not automatically human validation. A later owner confirmation must be recorded separately.

## Review packet

### HV-001

- Anonymous system label: SYSTEM_A
- Domain: syndrome_differentiation
- Difficulty: easy
- Question: What does the TCM Research Corpus record about febrile symptoms?
- Gold atomic fact: The source defines febrile symptoms as: 是指感受热邪、或阳盛阴虚,人体的机能活动亢进所表现的证候。.

**Supplied Gold evidence excerpt**

Source entity: febrile symptoms. Pinyin: Re Zheng. Source definition: 是指感受热邪、或阳盛阴虚,人体的机能活动亢进所表现的证候。. Source text: Syndrome: febrile symptoms. Pinyin: Re Zheng. Source definition: 是指感受热邪、或阳盛阴虚,人体的机能活动亢进所表现的证候。.

**Answer**

TCM educational synthesis: The TCM Research Corpus records that febrile symptoms, or Re Zheng, refer to conditions arising from exposure to heat pathogen or from excessive yang energy and deficient yin, leading to heightened bodily functions. It also mentions Febrile disease early, or Wen Bing Chu Qi, as a category of acute infectious diseases caused by warm pathogens. The corpus does not provide specific details on the relationship between febrile symptoms and other syndromes like wind syndromes of cold type with damp symptoms. [tcmv1-00ce7010e21abde6e2cd45bd] [tcmv1-a5f2d5d725f5e670903b7d7a] [tcmv1-296b65d43ad677943104bd0c]

**Return fields**: item_id, review_label, review_reason, confidence

---

### HV-002

- Anonymous system label: SYSTEM_B
- Domain: syndrome_differentiation
- Difficulty: easy
- Question: What does the TCM Research Corpus record about Damp Phlegm?
- Gold atomic fact: The source defines Damp Phlegm as: 痰湿内阻,以咳吐多量黏稠痰,痰滑易咯,肢体困重,胸脘痞闷,食少口腻,苔白腻,脉濡缓或滑等为常见症的证候。.

**Supplied Gold evidence excerpt**

Source entity: Damp Phlegm. Pinyin: Shi Tan. Source definition: 痰湿内阻,以咳吐多量黏稠痰,痰滑易咯,肢体困重,胸脘痞闷,食少口腻,苔白腻,脉濡缓或滑等为常见症的证候。. Source text: Syndrome: Damp Phlegm. Pinyin: Shi Tan. Source definition: 痰湿内阻,以咳吐多量黏稠痰,痰滑易咯,肢体困重,胸脘痞闷,食少口腻,苔白腻,脉濡缓或滑等为常见症的证候。.

**Answer**

TCM educational synthesis: The TCM Research Corpus records that Damp Phlegm, or Shi Tan, is characterized by symptoms such as coughing up large amounts of sticky, thick phlegm, easy expectoration, heavy limbs, chest and upper abdomen discomfort, reduced appetite and a feeling of fullness in the mouth, white and greasy tongue coating, and a slow or slippery pulse. It does not mention relationships with other syndromes like phlegm fire or adverse rising of phlegm. [tcmv1-1b901c76fc3776d09fd384eb] [tcmv1-107a2889e2902e72f08feaa2] [tcmv1-efe38d5d3ed4558ed3d6213a]

**Return fields**: item_id, review_label, review_reason, confidence

---

### HV-003

- Anonymous system label: SYSTEM_B
- Domain: syndrome_differentiation
- Difficulty: easy
- Question: What does the TCM Research Corpus record about febrile symptoms?
- Gold atomic fact: The source defines febrile symptoms as: 是指感受热邪、或阳盛阴虚,人体的机能活动亢进所表现的证候。.

**Supplied Gold evidence excerpt**

Source entity: febrile symptoms. Pinyin: Re Zheng. Source definition: 是指感受热邪、或阳盛阴虚,人体的机能活动亢进所表现的证候。. Source text: Syndrome: febrile symptoms. Pinyin: Re Zheng. Source definition: 是指感受热邪、或阳盛阴虚,人体的机能活动亢进所表现的证候。.

**Answer**

TCM educational synthesis: Syndrome Differentiation Agent: The TCM Research Corpus records that febrile symptoms, or Re Zheng, refer to conditions arising from exposure to heat pathogen or from excessive yang energy and deficient yin, leading to heightened bodily functions. It also mentions wind syndromes of cold type with damp symptoms, or Feng Han Xie Shi, as a combination of wind, cold, and damp pathogenic factors. Additionally, it describes febrile disease early, or Wen Bing Chu Qi, as a category of acute infectious diseases caused by warm pathogens. [tcmv1-00ce7010e21abde6e2cd45bd] [tcmv1-a5f2d5d725f5e670903b7d7a] [tcmv1-296b65d43ad677943104bd0c]

**Return fields**: item_id, review_label, review_reason, confidence

---

### HV-004

- Anonymous system label: SYSTEM_A
- Domain: herbal_medicine + syndrome_differentiation
- Difficulty: hard
- Question: How are Sharpspur Corydalis and retention of phlegm in the interior represented in the TCM corpus, and what evidence is recorded for each?
- Gold atomic fact: The source records this function for Sharpspur Corydalis: To quicken blood and relieve pain, clear heat and resolve toxin..

**Supplied Gold evidence excerpt**

Source entity: Sharpspur Corydalis. Pinyin: JIAN JU ZI JIN. Latin name: Corydalis suaveolens [Syn. Corydalis sheareri]. Used part: whole herb or tuber. Source-recorded function: To quicken blood and relieve pain, clear heat and resolve toxin.. Source-recorded indication: Stomachache, abdominal pain and diarrhea, knocks and falls, swelling toxin of welling abscess and sore, red eyes with gall.. Source text: Herb: Sharpspur Corydalis. Pinyin: JIAN JU ZI JIN. Latin name: Corydalis suaveolens [Syn. Corydalis sheareri]. Used part: whole herb or tuber. Source-recorded function: To quicken blood and relieve pain, clear heat and resolve toxin.. Source-recorded indication: Stomachache, abdominal pain and diarrhea, knocks and falls, swelling toxin of welling abscess and sore, red eyes with gall..

**Answer**

TCM educational synthesis: Syndrome Differentiation Agent: retention of phlegm in the interior is characterized by the accumulation or movement of phlegm within the internal organs and tissues. The evidence reports that this syndrome presents clinically with symptoms such as excessive phlegm, chest tightness, nausea, dizziness, obesity, and the presence of masses. These manifestations are described as central to the identification of retention of phlegm in the interior according to traditional TCM definitions. [tcmv1-0bfff608da9589346d9947ed] [tcmv1-a1c80f8b5aba229e968a09b2] Herbal Knowledge Agent: Sharpspur Corydalis: The supplied evidence records that the herb, known as JIAN JU ZI JIN in pinyin and Corydalis suaveolens [Syn. Corydalis sheareri] in Latin, is used in traditional Chinese medicine. Its source-recorded functions include quickening blood and relieving pain, as well as clearing heat and resolving toxin. The indications noted are stomachache, abdominal pain and diarrhea, knocks and falls, swelling toxin of welling abscess and sore, and red eyes with gall. [tcmv1-02e39e2ba1eeacc6aa4f8f3d] The retrieved evidence describes these topics separately and does not establish an explicit relationship between them.

**Return fields**: item_id, review_label, review_reason, confidence

---

### HV-005

- Anonymous system label: SYSTEM_B
- Domain: herbal_medicine
- Difficulty: medium
- Question: What source-recorded functions and indications are listed for Tuberose?
- Gold atomic fact: The source records these indications for Tuberose: Swelling toxin of welling abscess and sore..

**Supplied Gold evidence excerpt**

Source entity: Tuberose. Pinyin: WAN XIANG YU. Latin name: Polianthes tuberosa. Used part: root. Source-recorded function: To clear heat and resolve toxin.. Source-recorded indication: Swelling toxin of welling abscess and sore.. Source text: Herb: Tuberose. Pinyin: WAN XIANG YU. Latin name: Polianthes tuberosa. Used part: root. Source-recorded function: To clear heat and resolve toxin.. Source-recorded indication: Swelling toxin of welling abscess and sore..

**Answer**

TCM educational synthesis: Herbal Knowledge Agent: Tuberose: The supplied evidence records that Tuberose, with the pinyin name Wan Xiang Yu and Latin name Polianthes tuberosa, is used in traditional Chinese medicine with the part root. It is source-reported to have the function of clearing heat and resolving toxin, and is indicated for swelling toxin of welling abscess and sore. [tcmv1-00dc3ac72ad6cfdc35663262] The retrieved evidence describes these topics separately and does not establish an explicit relationship between them.

**Return fields**: item_id, review_label, review_reason, confidence

---

### HV-006

- Anonymous system label: SYSTEM_A
- Domain: herbal_medicine + syndrome_differentiation
- Difficulty: hard
- Question: How are Creeping Skyflower Leaf and excessiveness of the stomach-fire represented in the TCM corpus, and what evidence is recorded for each?
- Gold atomic fact: The source defines excessiveness of the stomach-fire as: 指胃热炽盛化火的病变。.

**Supplied Gold evidence excerpt**

Source entity: excessiveness of the stomach-fire. Pinyin: Wei Huo Kang Sheng. Source definition: 指胃热炽盛化火的病变。. Source text: Syndrome: excessiveness of the stomach-fire. Pinyin: Wei Huo Kang Sheng. Source definition: 指胃热炽盛化火的病变。.

**Answer**

TCM educational synthesis: Syndrome Differentiation Agent: excessiveness of the stomach-fire: evidence-supported facts for this target only  
The supplied evidence records that excessiveness of the stomach-fire refers to a pathological condition where the stomach's heat becomes excessive and transforms into fire, described as "指胃热炽盛化火的病变。" This indicates an internal imbalance characterized by intense heat in the stomach leading to fiery symptoms, according to traditional TCM content. [tcmv1-1cd87a03ad55655b2e3d2ad2] Herbal Knowledge Agent: Creeping Skyflower Leaf, with the pinyin name JIA LIAN QIAO YE and Latin name Duranta repens, is recorded in traditional sources as being used for its function to dissipate stasis and resolve toxin. It is indicated for conditions such as stasis swelling resulting from knocks and falls, and swollen welling abscess. The evidence provided does not specify any other properties or relationships regarding this herb. [tcmv1-0417ced3f85a819d3be20a8f] The retrieved evidence describes these topics separately and does not establish an explicit relationship between them.

**Return fields**: item_id, review_label, review_reason, confidence

---

### HV-007

- Anonymous system label: SYSTEM_B
- Domain: herbal_medicine + syndrome_differentiation
- Difficulty: hard
- Question: How are Garden Millingtonia and indigestion with food retention represented in the TCM corpus, and what evidence is recorded for each?
- Gold atomic fact: The source defines indigestion with food retention as: 是指由于饮食不节,损伤脾胃而出现的证候。.

**Supplied Gold evidence excerpt**

Source entity: indigestion with food retention. Pinyin: Shi Ji Bu Xiao. Source definition: 是指由于饮食不节,损伤脾胃而出现的证候。. Source text: Syndrome: indigestion with food retention. Pinyin: Shi Ji Bu Xiao. Source definition: 是指由于饮食不节,损伤脾胃而出现的证候。.

**Answer**

TCM educational synthesis: Syndrome Differentiation Agent: indigestion with food retention: evidence-supported facts for this target only  
The supplied evidence records that indigestion with food retention, known as Shi Ji Bu Xiao in pinyin, is described as a syndrome resulting from dietary indiscretion that damages the spleen and stomach, leading to the manifestation of specific symptoms. The evidence does not provide further details on the symptoms or treatment associated with this condition. [tcmv1-1bbf7362e507b0843a4eb22d] Herbal Knowledge Agent: Garden Millingtonia, with the pinyin name ZI MEI SHU and Latin name Millingtonia hortensis, is traditionally used in TCM for its bark or leaf. The source records indicate it is employed to dispel wind and relieve itch, resolve toxin and kill worms, and suppress cough and transform phlegm. It is associated with conditions such as eczema, urticaria, ascariasis, cough of phlegm asthma, and leptochroa. [tcmv1-0401fa4b74693418cc12569d] The retrieved evidence describes these topics separately and does not establish an explicit relationship between them.

**Return fields**: item_id, review_label, review_reason, confidence

---

### HV-008

- Anonymous system label: SYSTEM_B
- Domain: herbal_medicine + syndrome_differentiation
- Difficulty: hard
- Question: How are Puncturevine Caltrop Fruit;Tribulus terrestris and accumulation of cold and stasis of qi represented in the TCM corpus, and what evidence is recorded for each?
- Gold atomic fact: The source records these indications for Puncturevine Caltrop Fruit;Tribulus terrestris: 1. Antitussive, expectorant and antiasthmatic. 2. Its alcoholic infusion exerts hypotensive effect in anesthetized animals..

**Supplied Gold evidence excerpt**

Source entity: Puncturevine Caltrop Fruit;Tribulus terrestris. Pinyin: JI LI. Latin name: Fructus Tribuli. Traditional class: Liver-Pacifying Wind-Extinguishing Medicinal. Source-recorded function: To subdue hyperactivity of the liver, to promote blood circulation, to dispel wind, to clear the eye of opacity, and to arrest itching.. Source-recorded indication: 1. Antitussive, expectorant and antiasthmatic. 2. Its alcoholic infusion exerts hypotensive effect in anesthetized animals.. Source text: Herb: Puncturevine Caltrop Fruit;Tribulus terrestris. Pinyin: JI LI. Latin name: Fructus Tribuli. Source-recorded function: To subdue hyperactivity of the liver, to promote blood circulation, to dispel wind, to clear the eye of opacity, and to arrest itching.. Source-recorded indication: 1. Antitussive, expectorant and antiasthmatic. 2. Its alcoholic infusion exerts hypotensive effect in anesthetized animals.. Clinical manifestations: 1. Antitussive, expectorant and antiasthmatic. 2. Its alcoholic infusion exerts hypotensive effect in anesthetized animals..

**Answer**

TCM educational synthesis: Puncturevine Caltrop Fruit;Tribulus terrestris: Source records indicate its function to subdue hyperactivity of the liver, promote blood circulation, dispel wind, clear the eye of opacity, and arrest itching. It is also noted to have antitussive, expectorant, and antiasthmatic effects, with an alcoholic infusion showing hypotensive effects in anesthetized animals.

accumulation of cold and stasis of qi: The syndrome is defined as a condition where yin cold pathogenic factors invade the body, damage yang energy, and cause cold pathogens to stagnate, leading to external cold symptoms. [tcmv1-016497976f79ae613dd5dcaa] [tcmv1-0bbe236eedf374b329081c2e] The retrieved evidence describes these topics separately and does not establish an explicit relationship between them.

**Return fields**: item_id, review_label, review_reason, confidence

---

### HV-009

- Anonymous system label: SYSTEM_A
- Domain: syndrome_differentiation
- Difficulty: easy
- Question: What does the TCM Research Corpus record about floating of weak yang?
- Gold atomic fact: The source defines floating of weak yang as: 指体内阳气极虚,导致阴寒之气偏盛,格阳于外,阴阳寒热格拒,表现为内真寒外假热的证候。.

**Supplied Gold evidence excerpt**

Source entity: floating of weak yang. Pinyin: Xu Yang Shang Fu. Source definition: 指体内阳气极虚,导致阴寒之气偏盛,格阳于外,阴阳寒热格拒,表现为内真寒外假热的证候。. Source text: Syndrome: floating of weak yang. Pinyin: Xu Yang Shang Fu. Source definition: 指体内阳气极虚,导致阴寒之气偏盛,格阳于外,阴阳寒热格拒,表现为内真寒外假热的证候。.

**Answer**

TCM educational synthesis: The TCM Research Corpus records that the syndrome "floating of weak yang" (Xu Yang Shang Fu) refers to a condition where internal yang energy is extremely deficient, leading to an excess of yin cold, causing a separation of yang from the body. This results in a false exterior heat and true internal cold, with symptoms indicating such a conflict between internal and external manifestations. [tcmv1-04b855d6b3623548c98c6648] [tcmv1-079919868955bcf05c3c24e8] [tcmv1-42803fcad95a4dcaab207d45]

**Return fields**: item_id, review_label, review_reason, confidence

---

### HV-010

- Anonymous system label: SYSTEM_A
- Domain: herbal_medicine
- Difficulty: medium
- Question: What source-recorded functions and indications are listed for Creeping Oxalis?
- Gold atomic fact: The source records these indications for Creeping Oxalis: Damp-heat diarrhea, dysentery, jaundice, st rangury syndro me, vaginal discharge, blood ejection, spontaneous external bleeding, hematuria, menstrual disorder, knocks and falls, swelling pain in throat, swollen welling abscess and clove sores, erysipelas, eczema, scab and lichen, hemorrhoids, measles papules, burns and scalds, snake or insect bites..

**Supplied Gold evidence excerpt**

Source entity: Creeping Oxalis. Pinyin: ZUO JIANG CAO. Latin name: Oxalis corniculata [Syn. Oxalis repens]. Used part: whole herb. Source-recorded function: To clear heat and disinhibit damp, cool blood and dissipate stasis, resolve toxin and disperse swelling.. Source-recorded indication: Damp-heat diarrhea, dysentery, jaundice, st rangury syndro me, vaginal discharge, blood ejection, spontaneous external bleeding, hematuria, menstrual disorder, knocks and falls, swelling pain in throat, swollen welling abscess and clove sores, erysipelas, eczema, scab and lichen, hemorrhoids, measles papules, burns and scalds, snake or insect bites.. Source text: Herb: Creeping Oxalis. Pinyin: ZUO JIANG CAO. Latin name: Oxalis corniculata [Syn. Oxalis repens]. Used part: whole herb. Source-recorded function: To clear heat and disinhibit damp, cool blood and dissipate stasis, resolve toxin and disperse swelling.. Source-recorded indication: Damp-heat diarrhea, dysentery, jaundice, st rangury syndro me, vaginal discharge, blood ejection, spontaneous external bleeding, hematuria, menstrual disorder, knocks and falls, swelling pain in throat, swollen welling abscess and clove sores, erysipelas, eczema, scab and lichen, hemorrhoids, measles papules, burns and scalds, snake or insect bites..

**Answer**

TCM educational synthesis: Creeping Oxalis: The supplied evidence records that Creeping Oxalis, with the pinyin name Zuo Jiang Cao and Latin name Oxalis corniculata [Syn. Oxalis repens], is used as a whole herb in traditional Chinese medicine. It is source-recorded to clear heat and disinhibit damp, cool blood and dissipate stasis, resolve toxin and disperse swelling. Its indications include damp-heat diarrhea, dysentery, jaundice, strangury syndrome, vaginal discharge, blood ejection, spontaneous external bleeding, hematuria, menstrual disorder, knocks and falls, swelling pain in throat, swollen welling abscess and clove sores, erysipelas, eczema, scab and lichen, hemorrhoids, measles papules, burns and scalds, and snake or insect bites. [tcmv1-00f199ea21ecaf4cf99289b6] The retrieved evidence describes these topics separately and does not establish an explicit relationship between them.

**Return fields**: item_id, review_label, review_reason, confidence

---

### HV-011

- Anonymous system label: SYSTEM_A
- Domain: syndrome_differentiation
- Difficulty: easy
- Question: What does the TCM Research Corpus record about sinking of the middle qi?
- Gold atomic fact: The source defines sinking of the middle qi as: 脾虚气陷证是指脾气虚弱,升举无力而反下陷,以眩晕、泄泻、脘腹重坠、内脏下垂及气虚症状为主要表现的证。脾虚气陷证又名中气下陷证。.

**Supplied Gold evidence excerpt**

Source entity: sinking of the middle qi. Pinyin: Zhong Qi Xia Xian. Source definition: 脾虚气陷证是指脾气虚弱,升举无力而反下陷,以眩晕、泄泻、脘腹重坠、内脏下垂及气虚症状为主要表现的证。脾虚气陷证又名中气下陷证。. Source text: Syndrome: sinking of the middle qi. Pinyin: Zhong Qi Xia Xian. Source definition: 脾虚气陷证是指脾气虚弱,升举无力而反下陷,以眩晕、泄泻、脘腹重坠、内脏下垂及气虚症状为主要表现的证。脾虚气陷证又名中气下陷证。.

**Answer**

TCM educational synthesis: Syndrome Differentiation Agent: The TCM Research Corpus records that the syndrome of sinking of the middle qi, known as 脾虚气陷证 or 中气下陷证, is characterized by脾气虚弱,升举无力而反下陷, with main manifestations including眩晕,泄泻,脘腹重坠,内脏下垂, and symptoms of qi deficiency. [tcmv1-0706ebfe864b6c856d901961] [tcmv1-6768cbf7f9fc3b8ef9b67b63] [tcmv1-45cfd6aea2cb1bee0cc8c879]

**Return fields**: item_id, review_label, review_reason, confidence

---

### HV-012

- Anonymous system label: SYSTEM_B
- Domain: herbal_medicine
- Difficulty: medium
- Question: What source-recorded functions and indications are listed for Root-tuber Cremanthodium?
- Gold atomic fact: The source records this function for Root-tuber Cremanthodium: To relieve cough and dispel phlegm, loosen chest and disinhibit qi..

**Supplied Gold evidence excerpt**

Source entity: Root-tuber Cremanthodium. Pinyin: KUAI GEN CHUI TOU JU. Latin name: Cremanthodium ellisii. Used part: whole herb. Source-recorded function: To relieve cough and dispel phlegm, loosen chest and disinhibit qi.. Source-recorded indication: Cough of phlegm asthma, taxation damage, senile vacuity weakness headache.. Source text: Herb: Root-tuber Cremanthodium. Pinyin: KUAI GEN CHUI TOU JU. Latin name: Cremanthodium ellisii. Used part: whole herb. Source-recorded function: To relieve cough and dispel phlegm, loosen chest and disinhibit qi.. Source-recorded indication: Cough of phlegm asthma, taxation damage, senile vacuity weakness headache..

**Answer**

TCM educational synthesis: Root-tuber Cremanthodium: The supplied evidence records that it is used as a whole herb in traditional Chinese medicine. Its source-reported functions include relieving cough and dispelling phlegm, as well as loosening the chest and disinhibiting qi. The indications mentioned are cough with phlegm, asthma, taxation damage, senile vacuity weakness, and headache. No further details are provided regarding its properties or usage. [tcmv1-004107401e93b6689c0cd7b1] The retrieved evidence describes these topics separately and does not establish an explicit relationship between them.

**Return fields**: item_id, review_label, review_reason, confidence

---

### HV-013

- Anonymous system label: SYSTEM_B
- Domain: herbal_medicine + syndrome_differentiation
- Difficulty: hard
- Question: How are Bloodflower Milkweed and deficiency of body fluid with dryness in the intestines represented in the TCM corpus, and what evidence is recorded for each?
- Gold atomic fact: The source records this function for Bloodflower Milkweed: To clear heat and resolve toxin, quicken blood and stanch bleeding, disperse swelling and relieve pain..

**Supplied Gold evidence excerpt**

Source entity: Bloodflower Milkweed. Pinyin: LIAN SHENG GUI ZI HUA. Latin name: Asclepias curassavica. Used part: herb. Source-recorded function: To clear heat and resolve toxin, quicken blood and stanch bleeding, disperse swelling and relieve pain.. Source-recorded indication: Swelling pain in throat, lung heat cough, heat strangury, amenorrhea, flooding and spotting, vaginal discharge, swelling toxin of welling abscess and sore, eczema, intractable lichen, bleeding due to external injury.. Source text: Herb: Bloodflower Milkweed. Pinyin: LIAN SHENG GUI ZI HUA. Latin name: Asclepias curassavica. Used part: herb. Source-recorded function: To clear heat and resolve toxin, quicken blood and stanch bleeding, disperse swelling and relieve pain.. Source-recorded indication: Swelling pain in throat, lung heat cough, heat strangury, amenorrhea, flooding and spotting, vaginal discharge, swelling toxin of welling abscess and sore, eczema, intractable lichen, bleeding due to external injury..

**Answer**

TCM educational synthesis: Syndrome Differentiation Agent: deficiency of body fluid with dryness in the intestines: evidence-supported facts for this target only  
The supplied evidence records that deficiency of body fluid with dryness in the intestines, referred to as 肠燥津亏证, is characterized by the depletion of body fluids leading to insufficient nourishment of the intestines. This results in impaired intestinal function, specifically manifested as difficulty in bowel movements with dry, hard stools. Additionally, it presents symptoms associated with fluid deficiency, such as dry mouth and throat, and reduced body moisture. The condition is described as a syndrome where the intestines lose their lubrication due to the loss of body fluids. [tcmv1-11bfd329971d541729b08392] Herbal Knowledge Agent: Bloodflower Milkweed, with the pinyin name Lian Sheng Gui Zi Hua and Latin name Asclepias curassavica, is recorded as an herb used in traditional Chinese medicine. Its source-recorded functions include clearing heat and resolving toxin, quickening blood and stanching bleeding, dispersing swelling, and relieving pain. It is indicated for conditions such as swelling pain in throat, lung heat cough, heat strangury, amenorrhea, flooding and spotting, vaginal discharge, swelling toxin of welling abscess and sore, eczema, intractable lichen, and bleeding due to external injury. [tcmv1-0280afee372cda5ead10df6d] The retrieved evidence describes these topics separately and does not establish an explicit relationship between them.

**Return fields**: item_id, review_label, review_reason, confidence

---

### HV-014

- Anonymous system label: SYSTEM_A
- Domain: herbal_medicine + syndrome_differentiation
- Difficulty: hard
- Question: How are Garden Millingtonia and indigestion with food retention represented in the TCM corpus, and what evidence is recorded for each?
- Gold atomic fact: The source defines indigestion with food retention as: 是指由于饮食不节,损伤脾胃而出现的证候。.

**Supplied Gold evidence excerpt**

Source entity: indigestion with food retention. Pinyin: Shi Ji Bu Xiao. Source definition: 是指由于饮食不节,损伤脾胃而出现的证候。. Source text: Syndrome: indigestion with food retention. Pinyin: Shi Ji Bu Xiao. Source definition: 是指由于饮食不节,损伤脾胃而出现的证候。.

**Answer**

TCM educational synthesis: indigestion with food retention: The syndrome is described as resulting from dietary indiscretion that damages the spleen and stomach, leading to specific symptoms. It is recorded in the TCM corpus with the pinyin name Shi Ji Bu Xiao.

Garden Millingtonia: The herb is noted for its use in treating conditions such as eczema, urticaria, ascariasis, cough of phlegm asthma, and leptochroa. Its source-recorded functions include dispelling wind, relieving itch, resolving toxin and killing worms, suppressing cough, and transforming phlegm. [tcmv1-1bbf7362e507b0843a4eb22d] [tcmv1-0401fa4b74693418cc12569d] The retrieved evidence describes these topics separately and does not establish an explicit relationship between them.

**Return fields**: item_id, review_label, review_reason, confidence

---

### HV-015

- Anonymous system label: SYSTEM_B
- Domain: herbal_medicine
- Difficulty: easy
- Question: What traditional properties, meridians, and class are recorded for Peach Seed?
- Gold atomic fact: The source associates Peach Seed with these meridians: Heart,Liver,Large Intestine.

**Supplied Gold evidence excerpt**

Source entity: Peach Seed. Pinyin: Taoren. Latin name: Persicae Semen,Semen Persicae. Traditional properties: Bitter,Sweet,Calm. Meridians: Heart,Liver,Large Intestine. Traditional class: Blood Activating Stasis Removing Drugs. Source text: Herb: Peach Seed. Pinyin: Taoren. Latin name: Persicae Semen,Semen Persicae. Traditional properties: Bitter,Sweet,Calm. Meridians: Heart,Liver,Large Intestine. Traditional class: Blood Activating Stasis Removing Drugs. Used part: seed.

**Answer**

TCM educational synthesis: Peach Seed is recorded in traditional Chinese medicine with properties of mild, sweet, and bitter. It is associated with the Large Intestine, Liver, and Heart meridians. Its traditional class is Blood Activating Stasis Removing Drugs. The used part is the seed. It is traditionally used to promote blood circulation, eliminate phlegm, and relax the bowels. The source-recorded indications include amenorrhea, dysmenorrhea, concretion and conglomeration, lump glomus, knocks and falls, and intestinal dryness leading to constipation. Peach Seed is noted as slightly toxic. [tcmv1-98ead1a0f804f86de85925ff] [tcmv1-02a39a628010de96f81ba8bc] [tcmv1-f78d59d1400a1496c5362311]

**Return fields**: item_id, review_label, review_reason, confidence

---

### HV-016

- Anonymous system label: SYSTEM_B
- Domain: herbal_medicine
- Difficulty: medium
- Question: What source-recorded functions and indications are listed for Woods Lcaquertree Leaf?
- Gold atomic fact: The source records this function for Woods Lcaquertree Leaf: To dispel stasis and disperse swelling, kill worms, resolve toxin..

**Supplied Gold evidence excerpt**

Source entity: Woods Lcaquertree Leaf. Pinyin: YE QI SHU YE. Latin name: Rhus sylvestris. Used part: leaf. Source-recorded function: To dispel stasis and disperse swelling, kill worms, resolve toxin.. Source-recorded indication: Knocks and falls, bleeding due to external injury, ancylostomiasis, scab and lichen, sore toxin, poisonous snake bite.. Source text: Herb: Woods Lcaquertree Leaf. Pinyin: YE QI SHU YE. Latin name: Rhus sylvestris. Used part: leaf. Source-recorded function: To dispel stasis and disperse swelling, kill worms, resolve toxin.. Source-recorded indication: Knocks and falls, bleeding due to external injury, ancylostomiasis, scab and lichen, sore toxin, poisonous snake bite..

**Answer**

TCM educational synthesis: Woods Lcaquertree Leaf: The supplied evidence records that it is used in traditional Chinese medicine, with the source-recorded function to dispel stasis, disperse swelling, kill worms, and resolve toxin. It is indicated for conditions such as knocks and falls, bleeding from external injury, ancylostomiasis, scab and lichen, sore toxin, and poisonous snake bite. The herb's pinyin is YE QI SHU YE, and its Latin name is Rhus sylvestris. The used part is the leaf. [tcmv1-0039ac43934e87be99852a7e] The retrieved evidence describes these topics separately and does not establish an explicit relationship between them.

**Return fields**: item_id, review_label, review_reason, confidence

---

### HV-017

- Anonymous system label: SYSTEM_B
- Domain: herbal_medicine
- Difficulty: medium
- Question: What source-recorded functions and indications are listed for Silktree Albizia Bark?
- Gold atomic fact: The source records this function for Silktree Albizia Bark: To quiet spirit and resolve depression, quicken blood and disperse welling abscess..

**Supplied Gold evidence excerpt**

Source entity: Silktree Albizia Bark. Pinyin: HE HUAN PI. Latin name: Albizzia julibrissin. Traditional properties: Mild; Sweet. Meridians: Liver; Heart. Traditional class: Spirit calming. Used part: bark. Source-recorded function: To quiet spirit and resolve depression, quicken blood and disperse welling abscess.. Source-recorded indication: Disquieted heart spirit, depression, insomnia, welling abscess and sores, knocks and falls.. Source text: Herb: Silktree Albizia Bark. Pinyin: HE HUAN PI. Latin name: Albizzia julibrissin. Traditional properties: Mild; Sweet. Meridians: Liver; Heart. Used part: bark. Source-recorded function: To quiet spirit and resolve depression, quicken blood and disperse welling abscess.. Source-recorded indication: Disquieted heart spirit, depression, insomnia, welling abscess and sores, knocks and falls.. Clinical manifestations: 1. Tranquilizing. 2. Promoting blood circulation. 3. Analgesic..

**Answer**

TCM educational synthesis: Silktree Albizia Bark, with the pinyin name He Huan Pi, is traditionally associated with the Latin name Albizzia julibrissin. It is characterized by mild and sweet properties and is linked to the Liver and Heart meridians. The bark is used in TCM for its source-recorded functions of quieting the spirit, resolving depression, quickening blood circulation, and dispersing welling abscesses. Its traditional indications include disquieted heart spirit, depression, insomnia, welling abscesses and sores, as well as knocks and falls. The clinical manifestations reported are tranquilizing effects, promotion of blood circulation, and analgesic properties. [tcmv1-03ed105c1801871066130409] The retrieved evidence describes these topics separately and does not establish an explicit relationship between them.

**Return fields**: item_id, review_label, review_reason, confidence

---

### HV-018

- Anonymous system label: SYSTEM_A
- Domain: syndrome_differentiation
- Difficulty: easy
- Question: What does the TCM Research Corpus record about distending pain of the hypochondrium due to gallblsdder disorder?
- Gold atomic fact: The source defines distending pain of the hypochondrium due to gallblsdder disorder as: 胆胀是指胆腑气郁,胆失通降所引起的以右胁胀痛为主要临床表现的一种疾病。.

**Supplied Gold evidence excerpt**

Source entity: distending pain of the hypochondrium due to gallblsdder disorder. Pinyin: Dan Zhang. Source definition: 胆胀是指胆腑气郁,胆失通降所引起的以右胁胀痛为主要临床表现的一种疾病。. Source text: Syndrome: distending pain of the hypochondrium due to gallblsdder disorder. Pinyin: Dan Zhang. Source definition: 胆胀是指胆腑气郁,胆失通降所引起的以右胁胀痛为主要临床表现的一种疾病。.

**Answer**

TCM educational synthesis: The TCM Research Corpus records that distending pain of the hypochondrium due to gallbladder disorder, referred to as Dan Zhang, is characterized by right hypochondriac distending pain caused by gall腑气郁 and impaired bile descent. No further details about its treatment or associated symptoms are provided in the evidence. [tcmv1-02a9808fa683d6a36d31577c] [tcmv1-3b6a01c206d43113d61a1095] [tcmv1-66b005bd46779c54980e96e3]

**Return fields**: item_id, review_label, review_reason, confidence

---

### HV-019

- Anonymous system label: SYSTEM_A
- Domain: herbal_medicine + syndrome_differentiation
- Difficulty: hard
- Question: How are Garden Millingtonia and indigestion with food retention represented in the TCM corpus, and what evidence is recorded for each?
- Gold atomic fact: The source records this function for Garden Millingtonia: To dispel wind and relieve itch, resolve toxin and kill worms, suppress cough and transform phlegm..

**Supplied Gold evidence excerpt**

Source entity: Garden Millingtonia. Pinyin: ZI MEI SHU. Latin name: Millingtonia hortensis. Used part: bark or leaf. Source-recorded function: To dispel wind and relieve itch, resolve toxin and kill worms, suppress cough and transform phlegm.. Source-recorded indication: Eczema, urticaria, ascariasis, cough of phlegm asthma, leptochroa.. Source text: Herb: Garden Millingtonia. Pinyin: ZI MEI SHU. Latin name: Millingtonia hortensis. Used part: bark or leaf. Source-recorded function: To dispel wind and relieve itch, resolve toxin and kill worms, suppress cough and transform phlegm.. Source-recorded indication: Eczema, urticaria, ascariasis, cough of phlegm asthma, leptochroa..

**Answer**

TCM educational synthesis: indigestion with food retention: The syndrome is described as resulting from dietary indiscretion that damages the spleen and stomach, leading to specific symptoms. It is recorded in the TCM corpus with the pinyin name Shi Ji Bu Xiao.

Garden Millingtonia: The herb is noted for its use in treating conditions such as eczema, urticaria, ascariasis, cough of phlegm asthma, and leptochroa. Its source-recorded functions include dispelling wind, relieving itch, resolving toxin and killing worms, suppressing cough, and transforming phlegm. [tcmv1-1bbf7362e507b0843a4eb22d] [tcmv1-0401fa4b74693418cc12569d] The retrieved evidence describes these topics separately and does not establish an explicit relationship between them.

**Return fields**: item_id, review_label, review_reason, confidence

---

### HV-020

- Anonymous system label: SYSTEM_A
- Domain: syndrome_differentiation
- Difficulty: easy
- Question: What does the TCM Research Corpus record about the heat attacts the pericardium?
- Gold atomic fact: The source defines the heat attacts the pericardium as: 温热病内陷营血阶段的证型之一。主要证候有高热、神昏、谵语、甚则昏迷不醒、四肢厥逆、或见抽搐等。.

**Supplied Gold evidence excerpt**

Source entity: the heat attacts the pericardium. Pinyin: Re Ru Xin Bao. Source definition: 温热病内陷营血阶段的证型之一。主要证候有高热、神昏、谵语、甚则昏迷不醒、四肢厥逆、或见抽搐等。. Source text: Syndrome: the heat attacts the pericardium. Pinyin: Re Ru Xin Bao. Source definition: 温热病内陷营血阶段的证型之一。主要证候有高热、神昏、谵语、甚则昏迷不醒、四肢厥逆、或见抽搐等。.

**Answer**

TCM educational synthesis: Syndrome Differentiation Agent: The TCM Research Corpus records that the heat attacts the pericardium is a syndrome characterized by high fever, mental confusion, delirium, and even coma, along with cold limbs or convulsions. It is described as one of the syndrome types in the stage of internal invasion of warm and hot pathogens into the blood and營. The corpus also mentions another syndrome, breakdowm of the normal physiological coordination between the heart and the kidney, which presents with symptoms like heart烦, insomnia, dreams of emission, tinnitus, and lower back weakness. Additionally, it notes heat invading the blood phase as a condition marked by bleeding and actual heat symptoms. [tcmv1-01521362972e12b896c42873] [tcmv1-596c7423935c2e0e03c2badb] [tcmv1-2dca5534e46709d7f6e08b2f]

**Return fields**: item_id, review_label, review_reason, confidence

---

### HV-021

- Anonymous system label: SYSTEM_B
- Domain: syndrome_differentiation
- Difficulty: easy
- Question: What does the TCM Research Corpus record about retention of phlegm?
- Gold atomic fact: The source defines retention of phlegm as: 是指因嗜酒无度,过食肥甘厚味,损伤脾胃,以致健运失司,水湿内停,积聚生痰,痰阻中焦,清阳不升,头窍失养所表现出来的眩晕,头重昏蒙,舌苔白腻,脉濡滑的一类病证。.

**Supplied Gold evidence excerpt**

Source entity: retention of phlegm. Pinyin: Tan Zu. Source definition: 是指因嗜酒无度,过食肥甘厚味,损伤脾胃,以致健运失司,水湿内停,积聚生痰,痰阻中焦,清阳不升,头窍失养所表现出来的眩晕,头重昏蒙,舌苔白腻,脉濡滑的一类病证。. Source text: Syndrome: retention of phlegm. Pinyin: Tan Zu. Source definition: 是指因嗜酒无度,过食肥甘厚味,损伤脾胃,以致健运失司,水湿内停,积聚生痰,痰阻中焦,清阳不升,头窍失养所表现出来的眩晕,头重昏蒙,舌苔白腻,脉濡滑的一类病证。.

**Answer**

TCM educational synthesis: The TCM Research Corpus records that retention of phlegm refers to "坚结胶固之痰," also known as "老痰、结痰、郁痰." It describes phlegm retention as a condition where "痰浊停聚或流窜于脏腑、组织之间," leading to clinical manifestations such as "痰多、胸闷、呕恶、眩晕、体胖、包块." The term "retention of phlegm in the interior" is similarly defined, emphasizing the internal accumulation and movement of phlegm. [tcmv1-f885046af4e64e116fe259fa] [tcmv1-de7cea176037d44011e3a175] [tcmv1-0bfff608da9589346d9947ed]

**Return fields**: item_id, review_label, review_reason, confidence

---

### HV-022

- Anonymous system label: SYSTEM_A
- Domain: herbal_medicine + syndrome_differentiation
- Difficulty: hard
- Question: How are Sharpspur Corydalis and retention of phlegm in the interior represented in the TCM corpus, and what evidence is recorded for each?
- Gold atomic fact: The source records these indications for Sharpspur Corydalis: Stomachache, abdominal pain and diarrhea, knocks and falls, swelling toxin of welling abscess and sore, red eyes with gall..

**Supplied Gold evidence excerpt**

Source entity: Sharpspur Corydalis. Pinyin: JIAN JU ZI JIN. Latin name: Corydalis suaveolens [Syn. Corydalis sheareri]. Used part: whole herb or tuber. Source-recorded function: To quicken blood and relieve pain, clear heat and resolve toxin.. Source-recorded indication: Stomachache, abdominal pain and diarrhea, knocks and falls, swelling toxin of welling abscess and sore, red eyes with gall.. Source text: Herb: Sharpspur Corydalis. Pinyin: JIAN JU ZI JIN. Latin name: Corydalis suaveolens [Syn. Corydalis sheareri]. Used part: whole herb or tuber. Source-recorded function: To quicken blood and relieve pain, clear heat and resolve toxin.. Source-recorded indication: Stomachache, abdominal pain and diarrhea, knocks and falls, swelling toxin of welling abscess and sore, red eyes with gall..

**Answer**

TCM educational synthesis: Syndrome Differentiation Agent: retention of phlegm in the interior is characterized by the accumulation or movement of phlegm within the internal organs and tissues. The evidence reports that this syndrome presents clinically with symptoms such as excessive phlegm, chest tightness, nausea, dizziness, obesity, and the presence of masses. These manifestations are described as central to the identification of retention of phlegm in the interior according to traditional TCM definitions. [tcmv1-0bfff608da9589346d9947ed] [tcmv1-a1c80f8b5aba229e968a09b2] Herbal Knowledge Agent: Sharpspur Corydalis: The supplied evidence records that the herb, known as JIAN JU ZI JIN in pinyin and Corydalis suaveolens [Syn. Corydalis sheareri] in Latin, is used in traditional Chinese medicine. Its source-recorded functions include quickening blood and relieving pain, as well as clearing heat and resolving toxin. The indications noted are stomachache, abdominal pain and diarrhea, knocks and falls, swelling toxin of welling abscess and sore, and red eyes with gall. [tcmv1-02e39e2ba1eeacc6aa4f8f3d] The retrieved evidence describes these topics separately and does not establish an explicit relationship between them.

**Return fields**: item_id, review_label, review_reason, confidence

---

### HV-023

- Anonymous system label: SYSTEM_B
- Domain: syndrome_differentiation
- Difficulty: easy
- Question: What does the TCM Research Corpus record about deficiency of the stomach-yin?
- Gold atomic fact: The source defines deficiency of the stomach-yin as: 是指因饮食不节,过食辛辣厚味,积热于内,或热病后期伤津,或情志不畅,气郁化火伤阴,致胃失和降所表现出来的恶心、呕吐或呃逆,口燥咽干,舌红少苔,脉细数一类病证。.

**Supplied Gold evidence excerpt**

Source entity: deficiency of the stomach-yin. Pinyin: Wei Yin Bu Zu. Source definition: 是指因饮食不节,过食辛辣厚味,积热于内,或热病后期伤津,或情志不畅,气郁化火伤阴,致胃失和降所表现出来的恶心、呕吐或呃逆,口燥咽干,舌红少苔,脉细数一类病证。. Source text: Syndrome: deficiency of the stomach-yin. Pinyin: Wei Yin Bu Zu. Source definition: 是指因饮食不节,过食辛辣厚味,积热于内,或热病后期伤津,或情志不畅,气郁化火伤阴,致胃失和降所表现出来的恶心、呕吐或呃逆,口燥咽干,舌红少苔,脉细数一类病证。.

**Answer**

TCM educational synthesis: Syndrome Differentiation Agent: The TCM Research Corpus records that deficiency of the stomach-yin, or Wei Yin Bu Zu, is characterized by symptoms such as nausea, vomiting, or hiccups, along with dry mouth and throat, a red tongue with little coating, and a fine rapid pulse. These manifestations are attributed to internal heat from overindulgence in spicy or rich foods, residual heat from a fever, or emotional stress leading to fire damage of yin. [tcmv1-06c0961a827ac3ff880171b5] [tcmv1-2cd2df2bbe0d12636c4ed744] [tcmv1-bcfdda38f974d9fc3ae44923]

**Return fields**: item_id, review_label, review_reason, confidence

---

### HV-024

- Anonymous system label: SYSTEM_A
- Domain: herbal_medicine
- Difficulty: easy
- Question: What traditional properties, meridians, and class are recorded for Vinegar?
- Gold atomic fact: The source records Vinegar as having these traditional properties: Warm; Sour; Bitter.

**Supplied Gold evidence excerpt**

Source entity: Vinegar. Pinyin: CU. Latin name: Vinegar. Traditional properties: Warm; Sour; Bitter. Meridians: Stomach; Liver. Traditional class: Blood activation and stasis removal. Source-recorded function: To stanch bleeding and dissipate stasis, resolve toxin and kill worms.. Source-recorded indication: Postpartum blood dizziness, concretion and conglomeration, jaundice, yellow sweating, blood ejection, spontaneous external bleeding, hematochezia, itching in genital region, swelling of welling abscess, welling abscess and flat abscess with swelling sore.. Source text: Herb: Vinegar. Pinyin: CU. Latin name: Vinegar. Traditional properties: Warm; Sour; Bitter. Meridians: Stomach; Liver. Source-recorded function: To stanch bleeding and dissipate stasis, resolve toxin and kill worms.. Source-recorded indication: Postpartum blood dizziness, concretion and conglomeration, jaundice, yellow sweating, blood ejection, spontaneous external bleeding, hematochezia, itching in genital region, swelling of welling abscess, welling abscess and flat abscess with swelling sore..

**Answer**

TCM educational synthesis: Herbal Knowledge Agent: Vinegar is recorded in traditional Chinese medicine with properties of Warm, Sour, and Bitter. It is associated with the Stomach and Liver meridians. Its source-recorded function includes stanching bleeding, dissipating stasis, resolving toxin, and killing worms. The traditional class of Vinegar encompasses Medicinal For Detoxification, Parasiticide, Drying Dampness And Relieving Itching. [tcmv1-eb2e2c2f3754db103b883172] [tcmv1-038e7c75d6a96b7b8a2cd307] [tcmv1-008bc5af3eced1bdcca7a904]

**Return fields**: item_id, review_label, review_reason, confidence

---

### HV-025

- Anonymous system label: SYSTEM_A
- Domain: syndrome_differentiation
- Difficulty: medium
- Question: How does the corpus define Exteriat Syndrome of Deficiency, and what source wording is provided?
- Gold atomic fact: The source defines Exteriat Syndrome of Deficiency as: 外邪袭表,腠理不固,营卫之气不和所致的表证。.

**Supplied Gold evidence excerpt**

Source entity: Exteriat Syndrome of Deficiency. Pinyin: Biao Xu. Source definition: 外邪袭表,腠理不固,营卫之气不和所致的表证。. Source text: Syndrome: Exteriat Syndrome of Deficiency. Pinyin: Biao Xu. Source definition: 外邪袭表,腠理不固,营卫之气不和所致的表证。.

**Answer**

TCM educational synthesis: The corpus defines Exteriat Syndrome of Deficiency as a condition caused by external pathogens invading the body surface and impairing the defensive qi, leading to disharmony of the营卫 (nutritive and defensive energies). The source wording states: "外邪袭表,腠理不固,营卫之气不和所致的表证。" No other sources are provided for this syndrome. [tcmv1-0742a8f9694c37bd1e70a65a] [tcmv1-2cd2df2bbe0d12636c4ed744] [tcmv1-bcfdda38f974d9fc3ae44923]

**Return fields**: item_id, review_label, review_reason, confidence

---

### HV-026

- Anonymous system label: SYSTEM_B
- Domain: herbal_medicine + syndrome_differentiation
- Difficulty: hard
- Question: How are Garden Millingtonia and indigestion with food retention represented in the TCM corpus, and what evidence is recorded for each?
- Gold atomic fact: The source records this function for Garden Millingtonia: To dispel wind and relieve itch, resolve toxin and kill worms, suppress cough and transform phlegm..

**Supplied Gold evidence excerpt**

Source entity: Garden Millingtonia. Pinyin: ZI MEI SHU. Latin name: Millingtonia hortensis. Used part: bark or leaf. Source-recorded function: To dispel wind and relieve itch, resolve toxin and kill worms, suppress cough and transform phlegm.. Source-recorded indication: Eczema, urticaria, ascariasis, cough of phlegm asthma, leptochroa.. Source text: Herb: Garden Millingtonia. Pinyin: ZI MEI SHU. Latin name: Millingtonia hortensis. Used part: bark or leaf. Source-recorded function: To dispel wind and relieve itch, resolve toxin and kill worms, suppress cough and transform phlegm.. Source-recorded indication: Eczema, urticaria, ascariasis, cough of phlegm asthma, leptochroa..

**Answer**

TCM educational synthesis: Syndrome Differentiation Agent: indigestion with food retention: evidence-supported facts for this target only  
The supplied evidence records that indigestion with food retention, known as Shi Ji Bu Xiao in pinyin, is described as a syndrome resulting from dietary indiscretion that damages the spleen and stomach, leading to the manifestation of specific symptoms. The evidence does not provide further details on the symptoms or treatment associated with this condition. [tcmv1-1bbf7362e507b0843a4eb22d] Herbal Knowledge Agent: Garden Millingtonia, with the pinyin name ZI MEI SHU and Latin name Millingtonia hortensis, is traditionally used in TCM for its bark or leaf. The source records indicate it is employed to dispel wind and relieve itch, resolve toxin and kill worms, and suppress cough and transform phlegm. It is associated with conditions such as eczema, urticaria, ascariasis, cough of phlegm asthma, and leptochroa. [tcmv1-0401fa4b74693418cc12569d] The retrieved evidence describes these topics separately and does not establish an explicit relationship between them.

**Return fields**: item_id, review_label, review_reason, confidence

---

### HV-027

- Anonymous system label: SYSTEM_B
- Domain: herbal_medicine + syndrome_differentiation
- Difficulty: hard
- Question: How are Sharpspur Corydalis and retention of phlegm in the interior represented in the TCM corpus, and what evidence is recorded for each?
- Gold atomic fact: The source records these indications for Sharpspur Corydalis: Stomachache, abdominal pain and diarrhea, knocks and falls, swelling toxin of welling abscess and sore, red eyes with gall..

**Supplied Gold evidence excerpt**

Source entity: Sharpspur Corydalis. Pinyin: JIAN JU ZI JIN. Latin name: Corydalis suaveolens [Syn. Corydalis sheareri]. Used part: whole herb or tuber. Source-recorded function: To quicken blood and relieve pain, clear heat and resolve toxin.. Source-recorded indication: Stomachache, abdominal pain and diarrhea, knocks and falls, swelling toxin of welling abscess and sore, red eyes with gall.. Source text: Herb: Sharpspur Corydalis. Pinyin: JIAN JU ZI JIN. Latin name: Corydalis suaveolens [Syn. Corydalis sheareri]. Used part: whole herb or tuber. Source-recorded function: To quicken blood and relieve pain, clear heat and resolve toxin.. Source-recorded indication: Stomachache, abdominal pain and diarrhea, knocks and falls, swelling toxin of welling abscess and sore, red eyes with gall..

**Answer**

TCM educational synthesis: retention of phlegm in the interior: The TCM corpus records retention of phlegm in the interior as a syndrome characterized by symptoms such as痰多, 胸闷, 呕恶, 眩晕, 体胖, and 包块. It is defined as the condition where phlegm dampness stagnates or moves within the internal organs and tissues.

Sharpspur Corydalis: Sharpspur Corydalis is documented in the TCM corpus as an herb used for its functions of quickening blood and relieving pain, as well as clearing heat and resolving toxins. It is indicated for treating conditions like stomachache, abdominal pain and diarrhea, knocks and falls, swelling toxin of welling abscess and sore, and red eyes with gall. [tcmv1-0bfff608da9589346d9947ed] [tcmv1-02e39e2ba1eeacc6aa4f8f3d] The retrieved evidence describes these topics separately and does not establish an explicit relationship between them.

**Return fields**: item_id, review_label, review_reason, confidence

---

### HV-028

- Anonymous system label: SYSTEM_B
- Domain: syndrome_differentiation
- Difficulty: medium
- Question: How does the corpus define weak spleen and stomach, and what source wording is provided?
- Gold atomic fact: The source defines weak spleen and stomach as: 脾胃气虚,中焦失运,以食欲不振,脘腹痞胀,食后尤甚,大便溏泻,神疲肢倦,舌淡,脉弱等为常见症的证候。.

**Supplied Gold evidence excerpt**

Source entity: weak spleen and stomach. Pinyin: Pi Wei Xu. Source definition: 脾胃气虚,中焦失运,以食欲不振,脘腹痞胀,食后尤甚,大便溏泻,神疲肢倦,舌淡,脉弱等为常见症的证候。. Source text: Syndrome: weak spleen and stomach. Pinyin: Pi Wei Xu. Source definition: 脾胃气虚,中焦失运,以食欲不振,脘腹痞胀,食后尤甚,大便溏泻,神疲肢倦,舌淡,脉弱等为常见症的证候。.

**Answer**

TCM educational synthesis: The corpus defines weak spleen and stomach as 脾胃气虚,中焦失运, characterized by symptoms such as appetite loss,痞胀 in the upper abdomen, worsening after eating, loose stools, fatigue, limb weakness, a pale tongue, and weak pulse. This source wording is consistently reported across different pinyin variations (Pi Wei Xu, Pi Wei Yu Xu, Pi Wei Xu Ruo) in the provided evidence. [tcmv1-079919868955bcf05c3c24e8] [tcmv1-42803fcad95a4dcaab207d45] [tcmv1-da630dcb4969176335c13f9a]

**Return fields**: item_id, review_label, review_reason, confidence

---

### HV-029

- Anonymous system label: SYSTEM_A
- Domain: herbal_medicine
- Difficulty: medium
- Question: What source-recorded functions and indications are listed for Common Buckwheat Stem?
- Gold atomic fact: The source records this function for Common Buckwheat Stem: To precipitate qi and disperse accumulation, clear heat and resolve toxin, stanch bleeding, lower blood pressure..

**Supplied Gold evidence excerpt**

Source entity: Common Buckwheat Stem. Pinyin: QIAO MAI JIE. Latin name: Fagopyrum esculentum. Used part: stem-leaf. Source-recorded function: To precipitate qi and disperse accumulation, clear heat and resolve toxin, stanch bleeding, lower blood pressure.. Source-recorded indication: Dysphagia-occlusion, indigestion, dysentery, vaginal discharge, swollen welling abscess, scalds, hemoptysis, purpura, hypertension.. Source text: Herb: Common Buckwheat Stem. Pinyin: QIAO MAI JIE. Latin name: Fagopyrum esculentum. Used part: stem-leaf. Source-recorded function: To precipitate qi and disperse accumulation, clear heat and resolve toxin, stanch bleeding, lower blood pressure.. Source-recorded indication: Dysphagia-occlusion, indigestion, dysentery, vaginal discharge, swollen welling abscess, scalds, hemoptysis, purpura, hypertension..

**Answer**

TCM educational synthesis: Common Buckwheat Stem, known as QIAO MAI JIE in pinyin, is sourced from Fagopyrum esculentum. The evidence records that the used part includes stem-leaf. Its source-recorded functions are to precipitate qi and disperse accumulation, clear heat and resolve toxin, stanch bleeding, and lower blood pressure. The indications listed are dysphagia-occlusion, indigestion, dysentery, vaginal discharge, swollen welling abscess, scalds, hemoptysis, purpura, and hypertension. [tcmv1-00c56d1c0b9e352aeb429ef7] The retrieved evidence describes these topics separately and does not establish an explicit relationship between them.

**Return fields**: item_id, review_label, review_reason, confidence

---

### HV-030

- Anonymous system label: SYSTEM_A
- Domain: syndrome_differentiation
- Difficulty: medium
- Question: How does the corpus define weak spleen and stomach, and what source wording is provided?
- Gold atomic fact: The source defines weak spleen and stomach as: 脾胃气虚,中焦失运,以食欲不振,脘腹痞胀,食后尤甚,大便溏泻,神疲肢倦,舌淡,脉弱等为常见症的证候。.

**Supplied Gold evidence excerpt**

Source entity: weak spleen and stomach. Pinyin: Pi Wei Xu. Source definition: 脾胃气虚,中焦失运,以食欲不振,脘腹痞胀,食后尤甚,大便溏泻,神疲肢倦,舌淡,脉弱等为常见症的证候。. Source text: Syndrome: weak spleen and stomach. Pinyin: Pi Wei Xu. Source definition: 脾胃气虚,中焦失运,以食欲不振,脘腹痞胀,食后尤甚,大便溏泻,神疲肢倦,舌淡,脉弱等为常见症的证候。.

**Answer**

TCM educational synthesis: Syndrome Differentiation Agent: The corpus defines weak spleen and stomach as "脾胃气虚,中焦失运," characterized by symptoms such as appetite loss, epigastric痞胀, worsening after eating, loose stools, fatigue, limb weakness, a pale tongue, and weak pulse. This source wording is consistently reported across different pinyin labels: Pi Wei Xu, Pi Wei Yu Xu, and Pi Wei Xu Ruo. [tcmv1-079919868955bcf05c3c24e8] [tcmv1-42803fcad95a4dcaab207d45] [tcmv1-da630dcb4969176335c13f9a]

**Return fields**: item_id, review_label, review_reason, confidence

---

### HV-031

- Anonymous system label: SYSTEM_B
- Domain: herbal_medicine + syndrome_differentiation
- Difficulty: hard
- Question: How are Puncturevine Caltrop Fruit;Tribulus terrestris and accumulation of cold and stasis of qi represented in the TCM corpus, and what evidence is recorded for each?
- Gold atomic fact: The source records this function for Puncturevine Caltrop Fruit;Tribulus terrestris: To subdue hyperactivity of the liver, to promote blood circulation, to dispel wind, to clear the eye of opacity, and to arrest itching..

**Supplied Gold evidence excerpt**

Source entity: Puncturevine Caltrop Fruit;Tribulus terrestris. Pinyin: JI LI. Latin name: Fructus Tribuli. Traditional class: Liver-Pacifying Wind-Extinguishing Medicinal. Source-recorded function: To subdue hyperactivity of the liver, to promote blood circulation, to dispel wind, to clear the eye of opacity, and to arrest itching.. Source-recorded indication: 1. Antitussive, expectorant and antiasthmatic. 2. Its alcoholic infusion exerts hypotensive effect in anesthetized animals.. Source text: Herb: Puncturevine Caltrop Fruit;Tribulus terrestris. Pinyin: JI LI. Latin name: Fructus Tribuli. Source-recorded function: To subdue hyperactivity of the liver, to promote blood circulation, to dispel wind, to clear the eye of opacity, and to arrest itching.. Source-recorded indication: 1. Antitussive, expectorant and antiasthmatic. 2. Its alcoholic infusion exerts hypotensive effect in anesthetized animals.. Clinical manifestations: 1. Antitussive, expectorant and antiasthmatic. 2. Its alcoholic infusion exerts hypotensive effect in anesthetized animals..

**Answer**

TCM educational synthesis: Puncturevine Caltrop Fruit;Tribulus terrestris: Source records indicate its function to subdue hyperactivity of the liver, promote blood circulation, dispel wind, clear the eye of opacity, and arrest itching. It is also noted to have antitussive, expectorant, and antiasthmatic effects, with an alcoholic infusion showing hypotensive effects in anesthetized animals.

accumulation of cold and stasis of qi: The syndrome is defined as a condition where yin cold pathogenic factors invade the body, damage yang energy, and cause cold pathogens to stagnate, leading to external cold symptoms. [tcmv1-016497976f79ae613dd5dcaa] [tcmv1-0bbe236eedf374b329081c2e] The retrieved evidence describes these topics separately and does not establish an explicit relationship between them.

**Return fields**: item_id, review_label, review_reason, confidence

---

### HV-032

- Anonymous system label: SYSTEM_A
- Domain: syndrome_differentiation
- Difficulty: easy
- Question: What does the TCM Research Corpus record about Damp Phlegm?
- Gold atomic fact: The source defines Damp Phlegm as: 痰湿内阻,以咳吐多量黏稠痰,痰滑易咯,肢体困重,胸脘痞闷,食少口腻,苔白腻,脉濡缓或滑等为常见症的证候。.

**Supplied Gold evidence excerpt**

Source entity: Damp Phlegm. Pinyin: Shi Tan. Source definition: 痰湿内阻,以咳吐多量黏稠痰,痰滑易咯,肢体困重,胸脘痞闷,食少口腻,苔白腻,脉濡缓或滑等为常见症的证候。. Source text: Syndrome: Damp Phlegm. Pinyin: Shi Tan. Source definition: 痰湿内阻,以咳吐多量黏稠痰,痰滑易咯,肢体困重,胸脘痞闷,食少口腻,苔白腻,脉濡缓或滑等为常见症的证候。.

**Answer**

TCM educational synthesis: Syndrome Differentiation Agent: The TCM Research Corpus records that Damp Phlegm, or Shi Tan, is characterized by symptoms such as coughing up a large amount of sticky, thick phlegm, easy expectoration, heavy limbs, chest and upper abdomen discomfort, reduced appetite and a feeling of dampness in the mouth, white greasy tongue coating, and a slow or slippery pulse. It does not mention relationships with other syndromes like phlegm fire or adverse rising of phlegm. [tcmv1-1b901c76fc3776d09fd384eb] [tcmv1-107a2889e2902e72f08feaa2] [tcmv1-efe38d5d3ed4558ed3d6213a]

**Return fields**: item_id, review_label, review_reason, confidence

---

### HV-033

- Anonymous system label: SYSTEM_B
- Domain: herbal_medicine
- Difficulty: medium
- Question: What source-recorded functions and indications are listed for Lily Magnolia Bark?
- Gold atomic fact: The source records these indications for Lily Magnolia Bark: Liquor jaundice, damp itchy in genitals, lai, double tongue, welling abscess and flat abscess, edema..

**Supplied Gold evidence excerpt**

Source entity: Lily Magnolia Bark. Pinyin: ZI YU LAN PI. Latin name: Magnolia liliflora. Used part: bark. Source-recorded function: To rectify qi and eliminate damp, calm asthma.. Source-recorded indication: Liquor jaundice, damp itchy in genitals, lai, double tongue, welling abscess and flat abscess, edema.. Source text: Herb: Lily Magnolia Bark. Pinyin: ZI YU LAN PI. Latin name: Magnolia liliflora. Used part: bark. Source-recorded function: To rectify qi and eliminate damp, calm asthma.. Source-recorded indication: Liquor jaundice, damp itchy in genitals, lai, double tongue, welling abscess and flat abscess, edema..

**Answer**

TCM educational synthesis: Herbal Knowledge Agent: Lily Magnolia Bark, with the pinyin ZI YU LAN PI and Latin name Magnolia liliflora, is used in TCM as the bark. The source records its function to rectify qi and eliminate damp, calm asthma. It is indicated for conditions such as liquor jaundice, damp itchy in genitals, lai, double tongue, welling abscess and flat abscess, and edema. [tcmv1-0122eff9b074138cc8ab869a] The retrieved evidence describes these topics separately and does not establish an explicit relationship between them.

**Return fields**: item_id, review_label, review_reason, confidence

---

### HV-034

- Anonymous system label: SYSTEM_A
- Domain: herbal_medicine
- Difficulty: easy
- Question: What traditional properties, meridians, and class are recorded for Luganshi?
- Gold atomic fact: The source lists Luganshi in this traditional class: External Medicinal (Draw Out Toxin, Resolve Putridity).

**Supplied Gold evidence excerpt**

Source entity: Luganshi. Pinyin: Luganshi. Latin name: Calamina. Traditional properties: Sweet,Calm. Meridians: Liver,Spleen. Traditional class: External Medicinal (Draw Out Toxin, Resolve Putridity). Source text: Herb: Luganshi. Pinyin: Luganshi. Latin name: Calamina. Traditional properties: Sweet,Calm. Meridians: Liver,Spleen. Traditional class: External Medicinal (Draw Out Toxin, Resolve Putridity).

**Answer**

TCM educational synthesis: Luganshi is recorded with traditional properties of Sweet and Calm, and it affects the Liver and Spleen meridians. Its traditional class is categorized as External Medicinal, specifically for Draw Out Toxin and Resolve Putridity. [tcmv1-00ae7b90991a0ec6b5f3e13e] [tcmv1-008bc5af3eced1bdcca7a904] [tcmv1-15d4c2e795991b5a1e7d3d60]

**Return fields**: item_id, review_label, review_reason, confidence

---

### HV-035

- Anonymous system label: SYSTEM_A
- Domain: herbal_medicine
- Difficulty: medium
- Question: What source-recorded functions and indications are listed for root Pilose Asiabell; Pilose Asiabell?
- Gold atomic fact: The source records this function for root Pilose Asiabell; Pilose Asiabell: To reinforce qi and invigorate the function of the spleen and the lung..

**Supplied Gold evidence excerpt**

Source entity: root Pilose Asiabell; Pilose Asiabell. Pinyin: DANG SHEN. Latin name: Radix Codonopsis pilosulae. Traditional properties: Mild; Sweet. Meridians: Lung; Spleen. Traditional class: Qi Reinforcing Drugs. Used part: root. Source-recorded function: To reinforce qi and invigorate the function of the spleen and the lung.. Source-recorded indication: Spleen-stomach vacuity, reduced food intake and sloppy stool, lassitude in limbs, cough and asthma due to lung vacuity, shortness of breath and spontaneous sweating, qi-blood depletion.. Source text: Herb: root Pilose Asiabell; Pilose Asiabell. Pinyin: DANG SHEN. Latin name: Radix Codonopsis pilosulae. Traditional properties: Mild; Sweet. Meridians: Lung; Spleen. Used part: root. Source-recorded function: To reinforce qi and invigorate the function of the spleen and the lung.. Source-recorded indication: Spleen-stomach vacuity, reduced food intake and sloppy stool, lassitude in limbs, cough and asthma due to lung vacuity, shortness of breath and spontaneous sweating, qi-blood depletion..

**Answer**

TCM educational synthesis: Herbal Knowledge Agent: root Pilose Asiabell; Pilose Asiabell is recorded in traditional Chinese medicine as having mild and sweet properties, acting on the Lung and Spleen meridians. Its source-recorded function includes reinforcing qi and invigorating the spleen and lung functions. It is traditionally used for conditions such as spleen-stomach vacuity, reduced food intake with sloppy stool, lassitude in limbs, cough and asthma due to lung vacuity, shortness of breath, spontaneous sweating, and qi-blood depletion. The evidence provided does not specify any additional details about its use or properties. [tcmv1-02a05dcc00fb6b1ce8a72741] The retrieved evidence describes these topics separately and does not establish an explicit relationship between them.

**Return fields**: item_id, review_label, review_reason, confidence

---

### HV-036

- Anonymous system label: SYSTEM_A
- Domain: herbal_medicine
- Difficulty: medium
- Question: What source-recorded functions and indications are listed for Threeflower Clematis?
- Gold atomic fact: The source records these indications for Threeflower Clematis: Wind-damp impediment pain, swelling toxin of clove sore, throat impediment, snake bite, dog bite, blood ejection, hemoptysis, flooding and spotting..

**Supplied Gold evidence excerpt**

Source entity: Threeflower Clematis. Pinyin: BAI HUA TENG. Latin name: Clematis terniflora [Syn. Clematis maximowicziana]. Used part: root. Source-recorded function: To dispel wind and eliminate damp, resolve toxin and disperse swelling, cool blood and stanch bleeding.. Source-recorded indication: Wind-damp impediment pain, swelling toxin of clove sore, throat impediment, snake bite, dog bite, blood ejection, hemoptysis, flooding and spotting.. Source text: Herb: Threeflower Clematis. Pinyin: BAI HUA TENG. Latin name: Clematis terniflora [Syn. Clematis maximowicziana]. Used part: root. Source-recorded function: To dispel wind and eliminate damp, resolve toxin and disperse swelling, cool blood and stanch bleeding.. Source-recorded indication: Wind-damp impediment pain, swelling toxin of clove sore, throat impediment, snake bite, dog bite, blood ejection, hemoptysis, flooding and spotting..

**Answer**

TCM educational synthesis: Herbal Knowledge Agent: Threeflower Clematis: The supplied evidence records that the herb is known as BAI HUA TENG in pinyin, with the Latin name Clematis terniflora [Syn. Clematis maximowicziana]. It is used for its root, and according to traditional sources, it is claimed to dispel wind and eliminate damp, resolve toxin and disperse swelling, cool blood and stanch bleeding. The source also mentions its traditional use for conditions such as wind-damp impediment pain, swelling toxin of clove sore, throat impediment, snake bite, dog bite, blood ejection, hemoptysis, flooding and spotting. [tcmv1-011b27a3b7a84a1c105fa057] The retrieved evidence describes these topics separately and does not establish an explicit relationship between them.

**Return fields**: item_id, review_label, review_reason, confidence

---

### HV-037

- Anonymous system label: SYSTEM_B
- Domain: syndrome_differentiation
- Difficulty: easy
- Question: What does the TCM Research Corpus record about the heat attacts the pericardium?
- Gold atomic fact: The source defines the heat attacts the pericardium as: 温热病内陷营血阶段的证型之一。主要证候有高热、神昏、谵语、甚则昏迷不醒、四肢厥逆、或见抽搐等。.

**Supplied Gold evidence excerpt**

Source entity: the heat attacts the pericardium. Pinyin: Re Ru Xin Bao. Source definition: 温热病内陷营血阶段的证型之一。主要证候有高热、神昏、谵语、甚则昏迷不醒、四肢厥逆、或见抽搐等。. Source text: Syndrome: the heat attacts the pericardium. Pinyin: Re Ru Xin Bao. Source definition: 温热病内陷营血阶段的证型之一。主要证候有高热、神昏、谵语、甚则昏迷不醒、四肢厥逆、或见抽搐等。.

**Answer**

TCM educational synthesis: The TCM Research Corpus records that the heat attacts the pericardium is a syndrome characterized by high fever, mental confusion, delirium, and possibly coma, along with cold limbs or convulsions. It is described as one of the syndrome types in the stage of internal invasion of warm and hot pathogens into the blood and營 (nutritive) stage. The corpus does not provide further details on its relationship with other syndromes or specific treatments. [tcmv1-01521362972e12b896c42873] [tcmv1-596c7423935c2e0e03c2badb] [tcmv1-2dca5534e46709d7f6e08b2f]

**Return fields**: item_id, review_label, review_reason, confidence

---

### HV-038

- Anonymous system label: SYSTEM_A
- Domain: syndrome_differentiation
- Difficulty: easy
- Question: What does the TCM Research Corpus record about deficiency of the stomach-yin?
- Gold atomic fact: The source defines deficiency of the stomach-yin as: 是指因饮食不节,过食辛辣厚味,积热于内,或热病后期伤津,或情志不畅,气郁化火伤阴,致胃失和降所表现出来的恶心、呕吐或呃逆,口燥咽干,舌红少苔,脉细数一类病证。.

**Supplied Gold evidence excerpt**

Source entity: deficiency of the stomach-yin. Pinyin: Wei Yin Bu Zu. Source definition: 是指因饮食不节,过食辛辣厚味,积热于内,或热病后期伤津,或情志不畅,气郁化火伤阴,致胃失和降所表现出来的恶心、呕吐或呃逆,口燥咽干,舌红少苔,脉细数一类病证。. Source text: Syndrome: deficiency of the stomach-yin. Pinyin: Wei Yin Bu Zu. Source definition: 是指因饮食不节,过食辛辣厚味,积热于内,或热病后期伤津,或情志不畅,气郁化火伤阴,致胃失和降所表现出来的恶心、呕吐或呃逆,口燥咽干,舌红少苔,脉细数一类病证。.

**Answer**

TCM educational synthesis: The TCM Research Corpus records that deficiency of the stomach-yin, or Wei Yin Bu Zu, is associated with symptoms such as nausea, vomiting, or hiccups, along with dry mouth and throat, a red tongue with little coating, and a fine rapid pulse. This condition is attributed to factors like overconsumption of spicy or rich foods, internal heat from illness, or emotional stress leading to fire damage of yin. [tcmv1-06c0961a827ac3ff880171b5] [tcmv1-2cd2df2bbe0d12636c4ed744] [tcmv1-bcfdda38f974d9fc3ae44923]

**Return fields**: item_id, review_label, review_reason, confidence

---

### HV-039

- Anonymous system label: SYSTEM_B
- Domain: herbal_medicine
- Difficulty: medium
- Question: What source-recorded functions and indications are listed for Common Buckwheat Stem?
- Gold atomic fact: The source records these indications for Common Buckwheat Stem: Dysphagia-occlusion, indigestion, dysentery, vaginal discharge, swollen welling abscess, scalds, hemoptysis, purpura, hypertension..

**Supplied Gold evidence excerpt**

Source entity: Common Buckwheat Stem. Pinyin: QIAO MAI JIE. Latin name: Fagopyrum esculentum. Used part: stem-leaf. Source-recorded function: To precipitate qi and disperse accumulation, clear heat and resolve toxin, stanch bleeding, lower blood pressure.. Source-recorded indication: Dysphagia-occlusion, indigestion, dysentery, vaginal discharge, swollen welling abscess, scalds, hemoptysis, purpura, hypertension.. Source text: Herb: Common Buckwheat Stem. Pinyin: QIAO MAI JIE. Latin name: Fagopyrum esculentum. Used part: stem-leaf. Source-recorded function: To precipitate qi and disperse accumulation, clear heat and resolve toxin, stanch bleeding, lower blood pressure.. Source-recorded indication: Dysphagia-occlusion, indigestion, dysentery, vaginal discharge, swollen welling abscess, scalds, hemoptysis, purpura, hypertension..

**Answer**

TCM educational synthesis: Herbal Knowledge Agent: Common Buckwheat Stem, known as QIAO MAI JIE in pinyin, is sourced from Fagopyrum esculentum. The evidence records that it is used in traditional Chinese medicine for its functions of precipitating qi and dispersing accumulation, clearing heat and resolving toxin, stanching bleeding, and lowering blood pressure. It is traditionally indicated for conditions such as dysphagia-occlusion, indigestion, dysentery, vaginal discharge, swollen abscesses, scalds, hemoptysis, purpura, and hypertension. [tcmv1-00c56d1c0b9e352aeb429ef7] The retrieved evidence describes these topics separately and does not establish an explicit relationship between them.

**Return fields**: item_id, review_label, review_reason, confidence

---

### HV-040

- Anonymous system label: SYSTEM_A
- Domain: herbal_medicine + syndrome_differentiation
- Difficulty: hard
- Question: How are Puncturevine Caltrop Fruit;Tribulus terrestris and accumulation of cold and stasis of qi represented in the TCM corpus, and what evidence is recorded for each?
- Gold atomic fact: The source records this function for Puncturevine Caltrop Fruit;Tribulus terrestris: To subdue hyperactivity of the liver, to promote blood circulation, to dispel wind, to clear the eye of opacity, and to arrest itching..

**Supplied Gold evidence excerpt**

Source entity: Puncturevine Caltrop Fruit;Tribulus terrestris. Pinyin: JI LI. Latin name: Fructus Tribuli. Traditional class: Liver-Pacifying Wind-Extinguishing Medicinal. Source-recorded function: To subdue hyperactivity of the liver, to promote blood circulation, to dispel wind, to clear the eye of opacity, and to arrest itching.. Source-recorded indication: 1. Antitussive, expectorant and antiasthmatic. 2. Its alcoholic infusion exerts hypotensive effect in anesthetized animals.. Source text: Herb: Puncturevine Caltrop Fruit;Tribulus terrestris. Pinyin: JI LI. Latin name: Fructus Tribuli. Source-recorded function: To subdue hyperactivity of the liver, to promote blood circulation, to dispel wind, to clear the eye of opacity, and to arrest itching.. Source-recorded indication: 1. Antitussive, expectorant and antiasthmatic. 2. Its alcoholic infusion exerts hypotensive effect in anesthetized animals.. Clinical manifestations: 1. Antitussive, expectorant and antiasthmatic. 2. Its alcoholic infusion exerts hypotensive effect in anesthetized animals..

**Answer**

TCM educational synthesis: Syndrome Differentiation Agent: accumulation of cold and stasis of qi: evidence-supported facts for this target only  
The supplied evidence records that accumulation of cold and stasis of qi is defined as a syndrome where external cold pathogenic factors invade the body, injure yang energy, and remain stagnant, leading to the manifestation of cold-related symptoms. The condition is described as a result of the lingering cold pathogen and impaired qi movement. [tcmv1-0bbe236eedf374b329081c2e] Herbal Knowledge Agent: Puncturevine Caltrop Fruit;Tribulus terrestris is recorded in traditional Chinese medicine as having the function to subdue hyperactivity of the liver, promote blood circulation, dispel wind, clear the eye of opacity, and arrest itching. Its indications include antitussive, expectorant, and antiasthmatic effects, with clinical manifestations noting that its alcoholic infusion exerts hypotensive effects in anesthetized animals. [tcmv1-016497976f79ae613dd5dcaa] The retrieved evidence describes these topics separately and does not establish an explicit relationship between them.

**Return fields**: item_id, review_label, review_reason, confidence

---

### HV-041

- Anonymous system label: SYSTEM_A
- Domain: syndrome_differentiation
- Difficulty: easy
- Question: What does the TCM Research Corpus record about retention of phlegm?
- Gold atomic fact: The source defines retention of phlegm as: 是指因嗜酒无度,过食肥甘厚味,损伤脾胃,以致健运失司,水湿内停,积聚生痰,痰阻中焦,清阳不升,头窍失养所表现出来的眩晕,头重昏蒙,舌苔白腻,脉濡滑的一类病证。.

**Supplied Gold evidence excerpt**

Source entity: retention of phlegm. Pinyin: Tan Zu. Source definition: 是指因嗜酒无度,过食肥甘厚味,损伤脾胃,以致健运失司,水湿内停,积聚生痰,痰阻中焦,清阳不升,头窍失养所表现出来的眩晕,头重昏蒙,舌苔白腻,脉濡滑的一类病证。. Source text: Syndrome: retention of phlegm. Pinyin: Tan Zu. Source definition: 是指因嗜酒无度,过食肥甘厚味,损伤脾胃,以致健运失司,水湿内停,积聚生痰,痰阻中焦,清阳不升,头窍失养所表现出来的眩晕,头重昏蒙,舌苔白腻,脉濡滑的一类病证。.

**Answer**

TCM educational synthesis: Syndrome Differentiation Agent: The TCM Research Corpus records that retention of phlegm refers to "坚结胶固之痰," also known as "老痰、结痰、郁痰." It describes phlegm retention as a condition where "痰浊停聚或流窜于脏腑、组织之间," with clinical manifestations including "痰多、胸闷、呕恶、眩晕、体胖、包块" as primary symptoms. The term "retention of phlegm in the interior" is also used, with similar characteristics and symptoms reported. [tcmv1-f885046af4e64e116fe259fa] [tcmv1-de7cea176037d44011e3a175] [tcmv1-0bfff608da9589346d9947ed]

**Return fields**: item_id, review_label, review_reason, confidence

---

### HV-042

- Anonymous system label: SYSTEM_A
- Domain: herbal_medicine + syndrome_differentiation
- Difficulty: hard
- Question: How are Hairy Willowweed and be affected by summer-head-dampness represented in the TCM corpus, and what evidence is recorded for each?
- Gold atomic fact: The source records this function for Hairy Willowweed: To clear heat and resolve toxin, disinhibit damp and check diarrhea, disperse food and rectify qi , quicken blood and joint bones..

**Supplied Gold evidence excerpt**

Source entity: Hairy Willowweed. Pinyin: SHUI JIE GU DAN. Latin name: Epilobium hirsutum. Used part: whole herb. Source-recorded function: To clear heat and resolve toxin, disinhibit damp and check diarrhea, disperse food and rectify qi , quicken blood and joint bones.. Source-recorded indication: Damp-heat dysentery, food accumulati on, distending pain in stomach duct, toothache, menstrual disorder, amenorrhea, vaginal discharge, fracture due to knocks and falls, swelling of sores, scalds, scab sore.. Source text: Herb: Hairy Willowweed. Pinyin: SHUI JIE GU DAN. Latin name: Epilobium hirsutum. Used part: whole herb. Source-recorded function: To clear heat and resolve toxin, disinhibit damp and check diarrhea, disperse food and rectify qi , quicken blood and joint bones.. Source-recorded indication: Damp-heat dysentery, food accumulati on, distending pain in stomach duct, toothache, menstrual disorder, amenorrhea, vaginal discharge, fracture due to knocks and falls, swelling of sores, scalds, scab sore..

**Answer**

TCM educational synthesis: Syndrome Differentiation Agent: be affected by summer-head-dampness is characterized by symptoms such as chest and upper abdomen fullness, irritability, body heat, and a yellow, greasy tongue coating, according to the source definition. The syndrome is described as a combination of summer heat and dampness, with these main features noted. No further details are provided in the evidence. [tcmv1-101954f8109186c09eda5f9a] Herbal Knowledge Agent: Hairy Willowweed, with the pinyin name SHUI JIE GU DAN and Latin name Epilobium hirsutum, is recorded as the whole herb used in traditional Chinese medicine. Its source-reported functions include clearing heat and resolving toxin, disinhibiting damp and checking diarrhea, dispersing food and rectifying qi, and quickening blood and joint bones. The indications associated with it are damp-heat dysentery, food accumulation, distending pain in stomach duct, toothache, menstrual disorder, amenorrhea, vaginal discharge, fractures from knocks and falls, swelling of sores, scalds, and scab sore. [tcmv1-02311edb10b086d360335335] The retrieved evidence describes these topics separately and does not establish an explicit relationship between them.

**Return fields**: item_id, review_label, review_reason, confidence

---

### HV-043

- Anonymous system label: SYSTEM_B
- Domain: herbal_medicine
- Difficulty: medium
- Question: What source-recorded functions and indications are listed for Spiked Loosestrife Equivalent plant: Lythrum anceps?
- Gold atomic fact: The source records these indications for Spiked Loosestrife Equivalent plant: Lythrum anceps: Dysentery, diarrhea, hematochezia, flooding, ulcerating sores, blood ejection, spontaneous external bleeding, bleeding due to external injury..

**Supplied Gold evidence excerpt**

Source entity: Spiked Loosestrife Equivalent plant: Lythrum anceps. Pinyin: QIAN QU CAI. Latin name: Lythrum salicaria. Used part: whole herb. Source-recorded function: To clear heat and resolve toxin, promote contraction and stanch bleeding.. Source-recorded indication: Dysentery, diarrhea, hematochezia, flooding, ulcerating sores, blood ejection, spontaneous external bleeding, bleeding due to external injury.. Source text: Herb: Spiked Loosestrife Equivalent plant: Lythrum anceps. Pinyin: QIAN QU CAI. Latin name: Lythrum salicaria. Used part: whole herb. Source-recorded function: To clear heat and resolve toxin, promote contraction and stanch bleeding.. Source-recorded indication: Dysentery, diarrhea, hematochezia, flooding, ulcerating sores, blood ejection, spontaneous external bleeding, bleeding due to external injury..

**Answer**

TCM educational synthesis: Herbal Knowledge Agent: Spiked Loosestrife Equivalent plant: Lythrum anceps is recorded in traditional sources as a herb used for clearing heat and resolving toxin, as well as promoting contraction and stanching bleeding. Its source-recorded indications include dysentery, diarrhea, hematochezia, flooding, ulcerating sores, blood ejection, and spontaneous external bleeding. The used part is the whole herb, and its pinyin name is QIAN QU CAI. The Latin name provided in the evidence is Lythrum salicaria. [tcmv1-00fd2b581663d6fe54e58dd1] The retrieved evidence describes these topics separately and does not establish an explicit relationship between them.

**Return fields**: item_id, review_label, review_reason, confidence

---

### HV-044

- Anonymous system label: SYSTEM_A
- Domain: syndrome_differentiation
- Difficulty: medium
- Question: How does the corpus define fluid retention, and what source wording is provided?
- Gold atomic fact: The source defines fluid retention as: 寒痰阻肺证是指寒痰交阻于肺,肺失宣降,以咳嗽气喘、痰多色白及寒证症状为主要表现的证。寒痰阻肺证又名寒饮停肺证、痰浊阻肺证。.

**Supplied Gold evidence excerpt**

Source entity: fluid retention. Pinyin: Han Yin. Source definition: 寒痰阻肺证是指寒痰交阻于肺,肺失宣降,以咳嗽气喘、痰多色白及寒证症状为主要表现的证。寒痰阻肺证又名寒饮停肺证、痰浊阻肺证。. Source text: Syndrome: fluid retention. Pinyin: Han Yin. Source definition: 寒痰阻肺证是指寒痰交阻于肺,肺失宣降,以咳嗽气喘、痰多色白及寒证症状为主要表现的证。寒痰阻肺证又名寒饮停肺证、痰浊阻肺证。.

**Answer**

TCM educational synthesis: The corpus defines fluid retention as a syndrome where cold and fluid are retained, described as "是阴寒之邪侵入人体,损伤阳气,寒邪留滞不去,外现寒证的证候。" It also mentions "fluid retention" as "寒痰阻肺证," characterized by "咳嗽气喘、痰多色白及寒证症状." Additionally, "retention of meat and food in the stomach" is defined as a condition caused by "饮食不节," leading to damage of the spleen and stomach. [tcmv1-c368fad0b4120970ade8e505] [tcmv1-081d7a82a9b8581366dadda7] [tcmv1-aaa5873f4fbe1f2669b9f6dd]

**Return fields**: item_id, review_label, review_reason, confidence

---

### HV-045

- Anonymous system label: SYSTEM_A
- Domain: herbal_medicine + syndrome_differentiation
- Difficulty: hard
- Question: How are Common Sinodielsia and yang exhaustion represented in the TCM corpus, and what evidence is recorded for each?
- Gold atomic fact: The source records these indications for Common Sinodielsia: Common cold, headache, cough, wind-damp impediment pain, wind water edema..

**Supplied Gold evidence excerpt**

Source entity: Common Sinodielsia. Pinyin: DIAN QIN. Latin name: Sinodielsia yunnanensis. Used part: root. Source-recorded function: To effuse exterior, dispel wind, relieve pain, disinhibit urine.. Source-recorded indication: Common cold, headache, cough, wind-damp impediment pain, wind water edema.. Source text: Herb: Common Sinodielsia. Pinyin: DIAN QIN. Latin name: Sinodielsia yunnanensis. Used part: root. Source-recorded function: To effuse exterior, dispel wind, relieve pain, disinhibit urine.. Source-recorded indication: Common cold, headache, cough, wind-damp impediment pain, wind water edema..

**Answer**

TCM educational synthesis: Common Sinodielsia: The herb is recorded in the TCM corpus as being used for effusing exterior, dispelling wind, relieving pain, and disinhibiting urine. It is indicated for conditions such as common cold, headache, cough, wind-damp impediment pain, and wind water edema.

yang exhaustion: The syndrome is defined in the TCM corpus as a pathological change where the body's yang energy is rapidly lost, leading to a severe decline in yang functions and life-threatening conditions. [tcmv1-0203996356a74cf84c60eccb] [tcmv1-0febd68eb306a23cea4a99a4] The retrieved evidence describes these topics separately and does not establish an explicit relationship between them.

**Return fields**: item_id, review_label, review_reason, confidence

---

### HV-046

- Anonymous system label: SYSTEM_B
- Domain: herbal_medicine + syndrome_differentiation
- Difficulty: hard
- Question: How are Creeping Skyflower Leaf and excessiveness of the stomach-fire represented in the TCM corpus, and what evidence is recorded for each?
- Gold atomic fact: The source records these indications for Creeping Skyflower Leaf: Stasis swelling from knocks and falls, swollen welling abscess..

**Supplied Gold evidence excerpt**

Source entity: Creeping Skyflower Leaf. Pinyin: JIA LIAN QIAO YE. Latin name: Duranta repens. Used part: leaf. Source-recorded function: To dissipate stasis and resolve toxin.. Source-recorded indication: Stasis swelling from knocks and falls, swollen welling abscess.. Source text: Herb: Creeping Skyflower Leaf. Pinyin: JIA LIAN QIAO YE. Latin name: Duranta repens. Used part: leaf. Source-recorded function: To dissipate stasis and resolve toxin.. Source-recorded indication: Stasis swelling from knocks and falls, swollen welling abscess..

**Answer**

TCM educational synthesis: excessiveness of the stomach-fire: Syndrome: excessiveness of the stomach-fire. Pinyin: Wei Huo Kang Sheng. Source definition: 指胃热炽盛化火的病变。  
Creeping Skyflower Leaf: Herb: Creeping Skyflower Leaf. Pinyin: JIA LIAN QIAO YE. Latin name: Duranta repens. Used part: leaf. Source-recorded function: To dissipate stasis and resolve toxin. Source-recorded indication: Stasis swelling from knocks and falls, swollen welling abscess. [tcmv1-1cd87a03ad55655b2e3d2ad2] [tcmv1-0417ced3f85a819d3be20a8f] The retrieved evidence describes these topics separately and does not establish an explicit relationship between them.

**Return fields**: item_id, review_label, review_reason, confidence

---

### HV-047

- Anonymous system label: SYSTEM_B
- Domain: syndrome_differentiation
- Difficulty: easy
- Question: What does the TCM Research Corpus record about floating of weak yang?
- Gold atomic fact: The source defines floating of weak yang as: 指体内阳气极虚,导致阴寒之气偏盛,格阳于外,阴阳寒热格拒,表现为内真寒外假热的证候。.

**Supplied Gold evidence excerpt**

Source entity: floating of weak yang. Pinyin: Xu Yang Shang Fu. Source definition: 指体内阳气极虚,导致阴寒之气偏盛,格阳于外,阴阳寒热格拒,表现为内真寒外假热的证候。. Source text: Syndrome: floating of weak yang. Pinyin: Xu Yang Shang Fu. Source definition: 指体内阳气极虚,导致阴寒之气偏盛,格阳于外,阴阳寒热格拒,表现为内真寒外假热的证候。.

**Answer**

TCM educational synthesis: Syndrome Differentiation Agent: The TCM Research Corpus records that the syndrome "floating of weak yang" (Xu Yang Shang Fu) refers to a condition where internal yang energy is extremely deficient, leading to an excess of yin cold, resulting in a situation where yang is blocked from reaching its proper place, causing a false exterior heat while the interior remains genuinely cold. This syndrome is characterized by the body's internal true cold and external apparent heat. [tcmv1-04b855d6b3623548c98c6648] [tcmv1-079919868955bcf05c3c24e8] [tcmv1-42803fcad95a4dcaab207d45]

**Return fields**: item_id, review_label, review_reason, confidence

---

### HV-048

- Anonymous system label: SYSTEM_A
- Domain: herbal_medicine + syndrome_differentiation
- Difficulty: hard
- Question: How are Bloodflower Milkweed and deficiency of body fluid with dryness in the intestines represented in the TCM corpus, and what evidence is recorded for each?
- Gold atomic fact: The source records this function for Bloodflower Milkweed: To clear heat and resolve toxin, quicken blood and stanch bleeding, disperse swelling and relieve pain..

**Supplied Gold evidence excerpt**

Source entity: Bloodflower Milkweed. Pinyin: LIAN SHENG GUI ZI HUA. Latin name: Asclepias curassavica. Used part: herb. Source-recorded function: To clear heat and resolve toxin, quicken blood and stanch bleeding, disperse swelling and relieve pain.. Source-recorded indication: Swelling pain in throat, lung heat cough, heat strangury, amenorrhea, flooding and spotting, vaginal discharge, swelling toxin of welling abscess and sore, eczema, intractable lichen, bleeding due to external injury.. Source text: Herb: Bloodflower Milkweed. Pinyin: LIAN SHENG GUI ZI HUA. Latin name: Asclepias curassavica. Used part: herb. Source-recorded function: To clear heat and resolve toxin, quicken blood and stanch bleeding, disperse swelling and relieve pain.. Source-recorded indication: Swelling pain in throat, lung heat cough, heat strangury, amenorrhea, flooding and spotting, vaginal discharge, swelling toxin of welling abscess and sore, eczema, intractable lichen, bleeding due to external injury..

**Answer**

TCM educational synthesis: deficiency of body fluid with dryness in the intestines: The TCM corpus records this syndrome as 肠燥津亏证, characterized by symptoms such as dryness in the intestines and signs of body fluid deficiency. It is described as a condition where the body fluids are insufficient, leading to impaired intestinal function and difficulty in bowel movements.

Bloodflower Milkweed: Bloodflower Milkweed is documented in the TCM corpus with the pinyin LIAN SHENG GUI ZI HUA and the Latin name Asclepias curassavica. It is used as an herb and has functions including clearing heat, resolving toxins, quickening blood, and stanching bleeding. [tcmv1-11bfd329971d541729b08392] [tcmv1-0280afee372cda5ead10df6d] The retrieved evidence describes these topics separately and does not establish an explicit relationship between them.

**Return fields**: item_id, review_label, review_reason, confidence

---

### HV-049

- Anonymous system label: SYSTEM_A
- Domain: herbal_medicine
- Difficulty: medium
- Question: What source-recorded functions and indications are listed for Capitate Rhododendron?
- Gold atomic fact: The source records this function for Capitate Rhododendron: To relieve cough and dispel phlegm, warm stomach and relieve pain..

**Supplied Gold evidence excerpt**

Source entity: Capitate Rhododendron. Pinyin: TOU HUA DU JUAN. Latin name: Rhododendron capitatum. Used part: leaf or flower. Source-recorded function: To relieve cough and dispel phlegm, warm stomach and relieve pain.. Source-recorded indication: Cough and asthma with abundant phlegm, stomach cold abdominal pain.. Source text: Herb: Capitate Rhododendron. Pinyin: TOU HUA DU JUAN. Latin name: Rhododendron capitatum. Used part: leaf or flower. Source-recorded function: To relieve cough and dispel phlegm, warm stomach and relieve pain.. Source-recorded indication: Cough and asthma with abundant phlegm, stomach cold abdominal pain..

**Answer**

TCM educational synthesis: Herbal Knowledge Agent: Capitate Rhododendron, with the pinyin name TOU HUA DU JUAN and Latin name Rhododendron capitatum, is recorded in traditional sources as being used for its function to relieve cough and dispel phlegm, as well as to warm the stomach and relieve pain. The evidence indicates it is applied for conditions such as cough and asthma accompanied by abundant phlegm, and stomach cold causing abdominal pain. The used part of the herb is either the leaf or the flower. [tcmv1-0067a262fc409b6b1afb4352] The retrieved evidence describes these topics separately and does not establish an explicit relationship between them.

**Return fields**: item_id, review_label, review_reason, confidence

---

### HV-050

- Anonymous system label: SYSTEM_A
- Domain: herbal_medicine
- Difficulty: medium
- Question: What source-recorded functions and indications are listed for Silktree Albizia Bark?
- Gold atomic fact: The source records these indications for Silktree Albizia Bark: Disquieted heart spirit, depression, insomnia, welling abscess and sores, knocks and falls..

**Supplied Gold evidence excerpt**

Source entity: Silktree Albizia Bark. Pinyin: HE HUAN PI. Latin name: Albizzia julibrissin. Traditional properties: Mild; Sweet. Meridians: Liver; Heart. Traditional class: Spirit calming. Used part: bark. Source-recorded function: To quiet spirit and resolve depression, quicken blood and disperse welling abscess.. Source-recorded indication: Disquieted heart spirit, depression, insomnia, welling abscess and sores, knocks and falls.. Source text: Herb: Silktree Albizia Bark. Pinyin: HE HUAN PI. Latin name: Albizzia julibrissin. Traditional properties: Mild; Sweet. Meridians: Liver; Heart. Used part: bark. Source-recorded function: To quiet spirit and resolve depression, quicken blood and disperse welling abscess.. Source-recorded indication: Disquieted heart spirit, depression, insomnia, welling abscess and sores, knocks and falls.. Clinical manifestations: 1. Tranquilizing. 2. Promoting blood circulation. 3. Analgesic..

**Answer**

TCM educational synthesis: Herbal Knowledge Agent: Silktree Albizia Bark, with the pinyin name He Huan Pi, is derived from the plant Albizzia julibrissin. It is traditionally characterized as mild and sweet in property, associated with the Liver and Heart meridians. The bark is used in TCM to quiet the spirit, resolve depression, quicken blood circulation, and disperse welling abscesses. Its source-recorded indications include disquieted heart spirit, depression, insomnia, welling abscesses and sores, as well as knocks and falls. Clinically, it is reported to have tranquilizing effects, promote blood circulation, and provide analgesic properties. [tcmv1-03ed105c1801871066130409] The retrieved evidence describes these topics separately and does not establish an explicit relationship between them.

**Return fields**: item_id, review_label, review_reason, confidence

---

### HV-051

- Anonymous system label: SYSTEM_B
- Domain: herbal_medicine
- Difficulty: easy
- Question: What traditional properties, meridians, and class are recorded for Coral?
- Gold atomic fact: The source associates Coral with these meridians: Liver; Heart.

**Supplied Gold evidence excerpt**

Source entity: Coral. Pinyin: SHAN HU. Latin name: Os Corallii. Traditional properties: Mild; Sweet. Meridians: Liver; Heart. Traditional class: Spirit calming. Source-recorded function: Supression and spirit calming. Source text: Herb: Coral. Pinyin: SHAN HU. Latin name: Os Corallii. Traditional properties: Mild; Sweet. Meridians: Liver; Heart. Source-recorded function: Supression and spirit calming.

**Answer**

TCM educational synthesis: Herbal Knowledge Agent: Coral is recorded in traditional Chinese medicine with properties of mild and sweet, acting on the Liver and Heart meridians. Its source-reported function is supression and spirit calming. There is no evidence provided about its traditional class. [tcmv1-013edaeca2bfba2cf027540d] [tcmv1-83a6360d452532b699743410] [tcmv1-008bc5af3eced1bdcca7a904]

**Return fields**: item_id, review_label, review_reason, confidence

---

### HV-052

- Anonymous system label: SYSTEM_B
- Domain: herbal_medicine
- Difficulty: easy
- Question: What traditional properties, meridians, and class are recorded for Siegesbeckiae Herba?
- Gold atomic fact: The source associates Siegesbeckiae Herba with these meridians: Liver,Kidney.

**Supplied Gold evidence excerpt**

Source entity: Siegesbeckiae Herba. Pinyin: Xixiancao. Latin name: Siegesbeckiae Herba. Traditional properties: Pungent,Bitter,Cold. Meridians: Liver,Kidney. Traditional class: Wind-Dampnessdispelling And Heatclearing Medicinal. Source text: Herb: Siegesbeckiae Herba. Pinyin: Xixiancao. Latin name: Siegesbeckiae Herba. Traditional properties: Pungent,Bitter,Cold. Meridians: Liver,Kidney. Traditional class: Wind-Dampnessdispelling And Heatclearing Medicinal.

**Answer**

TCM educational synthesis: Siegesbeckiae Herba is recorded with traditional properties of Pungent, Bitter, and Cold. It is associated with the Liver and Kidney meridians. Its traditional class is categorized as Wind-Dampnessdispelling And Heatclearing Medicinal. Another record lists its traditional properties as Bitter, Sour, and Calm, and it is linked to the Lung, Spleen, and Bladder meridians. The traditional class for this entry includes Medicinal For Detoxification、Parasiticide、Drying Dampness And Relieving Itching. [tcmv1-00d296322d93b630268bc622] [tcmv1-16b9eb5651da38ef38357ddb] [tcmv1-e25f36c540626399f3ec3663]

**Return fields**: item_id, review_label, review_reason, confidence

---

### HV-053

- Anonymous system label: SYSTEM_B
- Domain: herbal_medicine + syndrome_differentiation
- Difficulty: hard
- Question: How are Hairy Willowweed and be affected by summer-head-dampness represented in the TCM corpus, and what evidence is recorded for each?
- Gold atomic fact: The source records this function for Hairy Willowweed: To clear heat and resolve toxin, disinhibit damp and check diarrhea, disperse food and rectify qi , quicken blood and joint bones..

**Supplied Gold evidence excerpt**

Source entity: Hairy Willowweed. Pinyin: SHUI JIE GU DAN. Latin name: Epilobium hirsutum. Used part: whole herb. Source-recorded function: To clear heat and resolve toxin, disinhibit damp and check diarrhea, disperse food and rectify qi , quicken blood and joint bones.. Source-recorded indication: Damp-heat dysentery, food accumulati on, distending pain in stomach duct, toothache, menstrual disorder, amenorrhea, vaginal discharge, fracture due to knocks and falls, swelling of sores, scalds, scab sore.. Source text: Herb: Hairy Willowweed. Pinyin: SHUI JIE GU DAN. Latin name: Epilobium hirsutum. Used part: whole herb. Source-recorded function: To clear heat and resolve toxin, disinhibit damp and check diarrhea, disperse food and rectify qi , quicken blood and joint bones.. Source-recorded indication: Damp-heat dysentery, food accumulati on, distending pain in stomach duct, toothache, menstrual disorder, amenorrhea, vaginal discharge, fracture due to knocks and falls, swelling of sores, scalds, scab sore..

**Answer**

TCM educational synthesis: be affected by summer-head-dampness: evidence-supported facts for this target only: The syndrome is described as暑热挟湿, characterized by chest and epigastrium fullness, irritability, body heat, and a yellow, greasy tongue coating.  
Hairy Willowweed: evidence-supported facts for this target only: It is used as a whole herb in TCM, with functions including clearing heat and resolving toxins, disinhibiting damp and controlling diarrhea, and quickening blood to alleviate joint pain. [tcmv1-101954f8109186c09eda5f9a] [tcmv1-02311edb10b086d360335335] The retrieved evidence describes these topics separately and does not establish an explicit relationship between them.

**Return fields**: item_id, review_label, review_reason, confidence

---

### HV-054

- Anonymous system label: SYSTEM_A
- Domain: herbal_medicine
- Difficulty: medium
- Question: What source-recorded functions and indications are listed for Lily Magnolia Bark?
- Gold atomic fact: The source records these indications for Lily Magnolia Bark: Liquor jaundice, damp itchy in genitals, lai, double tongue, welling abscess and flat abscess, edema..

**Supplied Gold evidence excerpt**

Source entity: Lily Magnolia Bark. Pinyin: ZI YU LAN PI. Latin name: Magnolia liliflora. Used part: bark. Source-recorded function: To rectify qi and eliminate damp, calm asthma.. Source-recorded indication: Liquor jaundice, damp itchy in genitals, lai, double tongue, welling abscess and flat abscess, edema.. Source text: Herb: Lily Magnolia Bark. Pinyin: ZI YU LAN PI. Latin name: Magnolia liliflora. Used part: bark. Source-recorded function: To rectify qi and eliminate damp, calm asthma.. Source-recorded indication: Liquor jaundice, damp itchy in genitals, lai, double tongue, welling abscess and flat abscess, edema..

**Answer**

TCM educational synthesis: Lily Magnolia Bark, with the pinyin ZI YU LAN PI and Latin name Magnolia liliflora, is recorded in traditional Chinese medicine as the bark used part. Its source-recorded functions include rectifying qi and eliminating damp, as well as calming asthma. The indications associated with it are liquor jaundice, damp itchy in genitals, lai, double tongue, welling abscess and flat abscess, and edema. [tcmv1-0122eff9b074138cc8ab869a] The retrieved evidence describes these topics separately and does not establish an explicit relationship between them.

**Return fields**: item_id, review_label, review_reason, confidence

---

### HV-055

- Anonymous system label: SYSTEM_A
- Domain: herbal_medicine
- Difficulty: medium
- Question: What source-recorded functions and indications are listed for Largeleaf Spicebush?
- Gold atomic fact: The source records this function for Largeleaf Spicebush: To dispel wind and eliminate damp, warm center and move qi , disperse swelling and relieve pain..

**Supplied Gold evidence excerpt**

Source entity: Largeleaf Spicebush. Pinyin: HEI KE NAN. Latin name: Lindera megaphylla. Used part: root, bark or branch. Source-recorded function: To dispel wind and eliminate damp, warm center and move qi , disperse swelling and relieve pain.. Source-recorded indication: Wind-damp impediment pain, impediment pain numbness, cold pain in stomach duct and abdomen, mounting qi , swelling pain in throat, lichen sore.. Source text: Herb: Largeleaf Spicebush. Pinyin: HEI KE NAN. Latin name: Lindera megaphylla. Used part: root, bark or branch. Source-recorded function: To dispel wind and eliminate damp, warm center and move qi , disperse swelling and relieve pain.. Source-recorded indication: Wind-damp impediment pain, impediment pain numbness, cold pain in stomach duct and abdomen, mounting qi , swelling pain in throat, lichen sore..

**Answer**

TCM educational synthesis: Herbal Knowledge Agent: Largeleaf Spicebush is recorded in traditional Chinese medicine with two distinct used parts: branch-leaf and root-bark. The branch-leaf is noted to have the function of dispelling wind and killing worms, while also closing sores and stanching bleeding. It is traditionally indicated for scab and lichen with itching sores, bleeding from external injuries, and cracking of hands and feet. The root-bark is reported to warm the stomach and center, move qi and relieve pain, and also dispel wind and eliminate damp. It is traditionally used for conditions such as running piglet, beriberi, edema, scab and lichen, and bleeding due to external injury. [tcmv1-89ce17500435efe66ff41db0] [tcmv1-af9f0d463c366edec20bd906] The retrieved evidence describes these topics separately and does not establish an explicit relationship between them.

**Return fields**: item_id, review_label, review_reason, confidence

---

### HV-056

- Anonymous system label: SYSTEM_A
- Domain: herbal_medicine
- Difficulty: medium
- Question: What source-recorded functions and indications are listed for Woods Lcaquertree Leaf?
- Gold atomic fact: The source records these indications for Woods Lcaquertree Leaf: Knocks and falls, bleeding due to external injury, ancylostomiasis, scab and lichen, sore toxin, poisonous snake bite..

**Supplied Gold evidence excerpt**

Source entity: Woods Lcaquertree Leaf. Pinyin: YE QI SHU YE. Latin name: Rhus sylvestris. Used part: leaf. Source-recorded function: To dispel stasis and disperse swelling, kill worms, resolve toxin.. Source-recorded indication: Knocks and falls, bleeding due to external injury, ancylostomiasis, scab and lichen, sore toxin, poisonous snake bite.. Source text: Herb: Woods Lcaquertree Leaf. Pinyin: YE QI SHU YE. Latin name: Rhus sylvestris. Used part: leaf. Source-recorded function: To dispel stasis and disperse swelling, kill worms, resolve toxin.. Source-recorded indication: Knocks and falls, bleeding due to external injury, ancylostomiasis, scab and lichen, sore toxin, poisonous snake bite..

**Answer**

TCM educational synthesis: Herbal Knowledge Agent: Woods Lcaquertree Leaf, with the pinyin YE QI SHU YE and Latin name Rhus sylvestris, is used in traditional Chinese medicine for its source-recorded functions of dispelling stasis, dispersing swelling, killing worms, and resolving toxin. It is traditionally indicated for conditions such as knocks and falls, bleeding from external injuries, ancylostomiasis, scab and lichen, sore toxin, and poisonous snake bites. The evidence provided outlines these traditional uses without further details. [tcmv1-0039ac43934e87be99852a7e] The retrieved evidence describes these topics separately and does not establish an explicit relationship between them.

**Return fields**: item_id, review_label, review_reason, confidence

---

### HV-057

- Anonymous system label: SYSTEM_B
- Domain: herbal_medicine + syndrome_differentiation
- Difficulty: hard
- Question: How are Suberect Spatholobus and phlegm-damoness obstructing lung represented in the TCM corpus, and what evidence is recorded for each?
- Gold atomic fact: The source records these indications for Suberect Spatholobus: Septicemia, menstrual disorder, blood vacuity, anemia due to malnutrition, anemia due to bleeding, anemia with yellow complexion, numbness and paralysis, wind-damp impediment pain..

**Supplied Gold evidence excerpt**

Source entity: Suberect Spatholobus. Pinyin: MI HUA DOU. Latin name: Spatholobus suberectus. Used part: stem. Source-recorded function: To supplement blood, quicken blood, free network vessels.. Source-recorded indication: Septicemia, menstrual disorder, blood vacuity, anemia due to malnutrition, anemia due to bleeding, anemia with yellow complexion, numbness and paralysis, wind-damp impediment pain.. Source text: Herb: Suberect Spatholobus. Pinyin: MI HUA DOU. Latin name: Spatholobus suberectus. Used part: stem. Source-recorded function: To supplement blood, quicken blood, free network vessels.. Source-recorded indication: Septicemia, menstrual disorder, blood vacuity, anemia due to malnutrition, anemia due to bleeding, anemia with yellow complexion, numbness and paralysis, wind-damp impediment pain..

**Answer**

TCM educational synthesis: Syndrome Differentiation Agent: phlegm-damoness obstructing lung: evidence-supported facts for this target only  
The supplied evidence records that phlegm-damoness obstructing lung, or Tan Xian Yong Fei, is defined as a syndrome where phlegm-damoness accumulates or moves within the lungs, leading to clinical manifestations such as excessive phlegm, chest tightness, nausea, dizziness, obesity, and masses. The evidence describes the syndrome's characteristics based on traditional TCM content without further details. [tcmv1-0c442f3196333e00832100d2] Herbal Knowledge Agent: Suberect Spatholobus is recorded in the supplied evidence as an herb used for its source-recorded functions of supplementing blood, quickening blood, and freeing network vessels. Its traditional properties are described as Bitter, Sweet, and Warm, and it is associated with the Liver and Kidney meridians. The source-recorded indications include menstrual disorders, anemia due to malnutrition or bleeding, numbness and paralysis, and wind-damp impediment pain. The evidence also notes its use in treating septicemia and blood vacuity with a yellow complexion. [tcmv1-73e78057da399f7b656bf323] [tcmv1-01b5f99fa10f4ca948607b90] [tcmv1-a3ba8e00b6ad08fb851bca3c] The retrieved evidence describes these topics separately and does not establish an explicit relationship between them.

**Return fields**: item_id, review_label, review_reason, confidence

---

### HV-058

- Anonymous system label: SYSTEM_B
- Domain: syndrome_differentiation
- Difficulty: easy
- Question: What does the TCM Research Corpus record about sinking of the middle qi?
- Gold atomic fact: The source defines sinking of the middle qi as: 脾虚气陷证是指脾气虚弱,升举无力而反下陷,以眩晕、泄泻、脘腹重坠、内脏下垂及气虚症状为主要表现的证。脾虚气陷证又名中气下陷证。.

**Supplied Gold evidence excerpt**

Source entity: sinking of the middle qi. Pinyin: Zhong Qi Xia Xian. Source definition: 脾虚气陷证是指脾气虚弱,升举无力而反下陷,以眩晕、泄泻、脘腹重坠、内脏下垂及气虚症状为主要表现的证。脾虚气陷证又名中气下陷证。. Source text: Syndrome: sinking of the middle qi. Pinyin: Zhong Qi Xia Xian. Source definition: 脾虚气陷证是指脾气虚弱,升举无力而反下陷,以眩晕、泄泻、脘腹重坠、内脏下垂及气虚症状为主要表现的证。脾虚气陷证又名中气下陷证。.

**Answer**

TCM educational synthesis: The TCM Research Corpus records that the syndrome of sinking of the middle qi, known as 脾虚气陷证 or 中气下陷证, is characterized by脾气虚弱,升举无力而反下陷, with main manifestations including眩晕、泄泻、脘腹重坠、内脏下垂 and symptoms of qi deficiency. It does not mention any direct relationship with other syndromes listed in the provided evidence. [tcmv1-0706ebfe864b6c856d901961] [tcmv1-6768cbf7f9fc3b8ef9b67b63] [tcmv1-45cfd6aea2cb1bee0cc8c879]

**Return fields**: item_id, review_label, review_reason, confidence

---

### HV-059

- Anonymous system label: SYSTEM_A
- Domain: herbal_medicine + syndrome_differentiation
- Difficulty: hard
- Question: How are Suberect Spatholobus and phlegm-damoness obstructing lung represented in the TCM corpus, and what evidence is recorded for each?
- Gold atomic fact: The source records these indications for Suberect Spatholobus: Septicemia, menstrual disorder, blood vacuity, anemia due to malnutrition, anemia due to bleeding, anemia with yellow complexion, numbness and paralysis, wind-damp impediment pain..

**Supplied Gold evidence excerpt**

Source entity: Suberect Spatholobus. Pinyin: MI HUA DOU. Latin name: Spatholobus suberectus. Used part: stem. Source-recorded function: To supplement blood, quicken blood, free network vessels.. Source-recorded indication: Septicemia, menstrual disorder, blood vacuity, anemia due to malnutrition, anemia due to bleeding, anemia with yellow complexion, numbness and paralysis, wind-damp impediment pain.. Source text: Herb: Suberect Spatholobus. Pinyin: MI HUA DOU. Latin name: Spatholobus suberectus. Used part: stem. Source-recorded function: To supplement blood, quicken blood, free network vessels.. Source-recorded indication: Septicemia, menstrual disorder, blood vacuity, anemia due to malnutrition, anemia due to bleeding, anemia with yellow complexion, numbness and paralysis, wind-damp impediment pain..

**Answer**

TCM educational synthesis: phlegm-damoness obstructing lung: The syndrome is described as involving the accumulation of phlegm-damnos or stagnation in the lungs, with clinical features such as excessive phlegm, chest tightness, nausea, dizziness, obesity, and palpable masses. Evidence reports it as a condition characterized by the presence of phlegm-damnos obstructing lung function.

Suberect Spatholobus: It is traditionally used for its properties of warming, sweetness, and bitterness, and is associated with the liver meridian. The herb is reported to function by enriching blood, activating blood circulation, and removing obstructions from the channels and collaterals. [tcmv1-0c442f3196333e00832100d2] [tcmv1-73e78057da399f7b656bf323] [tcmv1-01b5f99fa10f4ca948607b90] The retrieved evidence describes these topics separately and does not establish an explicit relationship between them.

**Return fields**: item_id, review_label, review_reason, confidence

---

### HV-060

- Anonymous system label: SYSTEM_B
- Domain: herbal_medicine + syndrome_differentiation
- Difficulty: hard
- Question: How are Common Sinodielsia and yang exhaustion represented in the TCM corpus, and what evidence is recorded for each?
- Gold atomic fact: The source records this function for Common Sinodielsia: To effuse exterior, dispel wind, relieve pain, disinhibit urine..

**Supplied Gold evidence excerpt**

Source entity: Common Sinodielsia. Pinyin: DIAN QIN. Latin name: Sinodielsia yunnanensis. Used part: root. Source-recorded function: To effuse exterior, dispel wind, relieve pain, disinhibit urine.. Source-recorded indication: Common cold, headache, cough, wind-damp impediment pain, wind water edema.. Source text: Herb: Common Sinodielsia. Pinyin: DIAN QIN. Latin name: Sinodielsia yunnanensis. Used part: root. Source-recorded function: To effuse exterior, dispel wind, relieve pain, disinhibit urine.. Source-recorded indication: Common cold, headache, cough, wind-damp impediment pain, wind water edema..

**Answer**

TCM educational synthesis: Syndrome Differentiation Agent: yang exhaustion: The supplied evidence records that yang exhaustion, or Wang Yang, is defined as a pathological change where the body's yang气 is lost in a short period, leading to a severe decline in yang functions and potentially life-threatening conditions. This concept is described as a sudden and significant depletion of yang energy. [tcmv1-0febd68eb306a23cea4a99a4] Herbal Knowledge Agent: Common Sinodielsia is recorded in the supplied evidence as an herb used for its functions of effusing exterior, dispelling wind, relieving pain, and disinhibiting urine. It is indicated for conditions such as common cold, headache, cough, wind-damp impediment pain, and wind water edema. The used part is the root, and its pinyin name is Dian Qin. The Latin name provided is Sinodielsia yunnanensis. [tcmv1-0203996356a74cf84c60eccb] The retrieved evidence describes these topics separately and does not establish an explicit relationship between them.

**Return fields**: item_id, review_label, review_reason, confidence

---

