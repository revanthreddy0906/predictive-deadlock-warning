# Early Warning of Unsafe States Before Banker's Algorithm Fires: Literature Review and Positioning

I found no prior work that combines a rule-based resource-pressure score, observer-mode simulation, event-based early-warning evaluation and an exact lookahead baseline for **resource-allocation** deadlock, so your combination appears novel. The novelty is in the framing and the evaluation, not the algorithm. Each component has strong precedents, and the closest work either predicts *lock* deadlocks in program traces or uses ML on cloud load without event-based evaluation.

## TL;DR
- **Novelty holds, with caveats.** I found no study that evaluates *early warning of Banker's unsafe states* using alarm precision, event recall and lead time. The nearest neighbours are deadlock *avoidance* speed-ups (Belik 1987; Finkel and Madduri 1987; DBDAA 2024), an ML "deadlock prediction" load balancer in CloudSim (Le Ngoc and Tran Cong 2023), and sound lock-deadlock prediction in program traces (Tunç et al., PLDI 2023). None of these targets your question.
- **Your evaluation design is well grounded.** Event-level recall with a look-back window, alarm-level precision and alarm silencing come straight from Hyland et al. (Nature Medicine 2020). Range-based precision and recall and window-based scoring come from Tatbul et al. (NeurIPS 2018) and Lavin and Ahmad (NAB, ICMLA 2015). Saito and Rehmsmeier (2015) and Davis and Goadrich (2006) justify using precision and recall rather than ROC for rare events.
- **Fix one citation now.** I could not find a "Kessels" BIT paper on the banker's algorithm. DOI 10.1007/BF01933724 is **Ferenc Belik, "Deadlock avoidance with a modified banker's algorithm," BIT 27:290–305 (1987)**, which states the Θ(mn²) cost and gives an amortised O(mn) variant. Cite Belik, and remove "Kessels" unless you can find a primary source for it.

## 1. Executive summary

Banker's algorithm comes from Dijkstra's EWD108 and EWD623 and was generalised by Habermann (CACM 1969).\[1\] It decides whether a state is safe, meaning some completion order exists in which every process can obtain its remaining maximum claim.\[2\] It is a binary, instantaneous test. Coffman, Elphick and Shoshani (1971) and Holt (1972) fixed the classical vocabulary: the four necessary conditions, reusable versus consumable resources, and graph reduction.\[3\] Later work on avoidance focused almost entirely on making the safety test **cheaper**. Belik (BIT 1987) gives amortised O(mn), Finkel and Madduri (IPL 1987) give an O(log n) test by maintaining safe sequences, Li and Cook (2007) give a near-linear algorithm, and DBDAA (PLOS ONE 2024) supports dynamic process arrival.\[4\]\[5\]\[6\]\[7\] None of this work makes the test **anticipatory**.

"Deadlock prediction" in the recent literature means two different things. The first is predictive analysis of *lock* deadlocks in program traces, such as Tunç et al. (PLDI 2023). The second is ML-flavoured load-balancing claims in cloud simulators, such as Le Ngoc and Tran Cong (INISCOM 2023) and an EasyChair preprint that is a narrative review without experiments.\[8\]\[9\]\[10\] Neither forecasts Banker's unsafe states with measured lead time.

Your evaluation borrows, legitimately, from clinical early warning (Hyland et al. 2020), earthquake early warning (Münchmeyer et al. 2021), time-series anomaly detection (Tatbul et al. 2018; NAB) and online failure prediction (Salfner et al. 2010). Expect reviewers to object most to four things: circularity between your indicators and the safety check, synthetic workloads, the assumption of known maximum claims, and the modest absolute F1. You can answer each with additional analyses: a learned-model baseline, cost-weighted metrics, robustness to misestimated claims, and a cheaper approximate lookahead. The most important framing fix is to present the result honestly. Contention alone (F1 0.34) beats your combined score (0.28), and exact lookahead (0.74) is an upper bound that costs about 39× more compute.

## 2. Annotated bibliography

### A. Classical foundations

**[Dijkstra-EWD623]** E. W. Dijkstra, "The mathematics behind the Banker's Algorithm," EWD 623, 1977; published in *Selected Writings on Computing: A Personal Perspective*, Springer-Verlag, 1982, pp. 308–312.\[2\] URL: https://www.cs.utexas.edu/~EWD/transcriptions/EWD06xx/EWD623.html
- In this note a "pattern" of loans and needs is safe if a granting strategy exists that guarantees all processes can complete their transactions. The banker grants a request only if the resulting pattern is safe and otherwise postpones it, and a safe pattern guarantees that a favourable moment will come in finite time. The algorithm searches for a permutation of processes that witnesses safety.\[2\]\[11\]
- Relevance: this is your primary source for the safe/unsafe definition. Quote it, and point out that "unsafe" means only that no such guarantee exists, not that the system is deadlocked.
- [FOUNDATIONAL]

**[Dijkstra-EWD108]** E. W. Dijkstra, EWD108 (in Dutch), c. 1964–1967, the original Banker's description written during the THE system design.\[1\] Stable URL: UNVERIFIED (the E.W. Dijkstra Archive at cs.utexas.edu hosts EWD scans, but I did not fetch the EWD108 page). The year is UNVERIFIED: you say 1965, and secondary sources vary.
- Relevance: cite it for historical priority only, since EWD623 is in English and easier to quote.
- [FOUNDATIONAL]

**[Dijkstra-EWD123]** E. W. Dijkstra, "Cooperating sequential processes," Technical Report EWD-123, Technological University, Eindhoven, 1965. This citation comes from Belik's reference list; I did not fetch a URL.\[7\]
- The 1965 report in which the banker's problem appears in English; it is often cited as the Banker's source.
- Relevance: the citation that best supports your "1965" date.
- [FOUNDATIONAL]

**[Habermann1969]** A. N. Habermann, "Prevention of system deadlocks," *Communications of the ACM*, 12(7):373–377, 385, July 1969. DOI: 10.1145/363156.363160\[12\]
- Presents algorithms that check a request against the current allocation and decide whether granting it introduces the possibility of deadlock. The algorithms were used in the THE system.\[13\] An annotated bibliography summarises it as defining a "safe" state via a completion sequence and showing that, in the worst case, "the processes will not get into a deadlock if and only if the allocation state is safe."\[14\]
- Relevance: the formal multi-resource generalisation that your safety check implements.
- [FOUNDATIONAL]

**[Holt1971]** R. C. Holt, "Comments on prevention of system deadlocks," *CACM*, 14(1):36–38, 1971. DOI: 10.1145/362452.362486.\[15\] Also **[ParnasHabermann1972]** D. L. Parnas and A. N. Habermann, "Comment on deadlock prevention method," *CACM*, 15(9):840–841, 1972. DOI: 10.1145/361573.361586\[16\]
- Holt shows that a scheduler that blocks safe requests can introduce "artificial" deadlocks, and that deadlock prevention does not eliminate permanent blocking (starvation).\[17\]
- Relevance: a precedent for treating safety as necessary but not sufficient for liveness, which supports including a waiting-ratio indicator.
- [FOUNDATIONAL]

**[Coffman1971]** E. G. Coffman Jr., M. J. Elphick and A. Shoshani, "System deadlocks," *ACM Computing Surveys*, 3(2):67–78, June 1971. DOI: 10.1145/356586.356588\[18\]
- Surveys deadlock treatment from both theoretical and practical angles. It is the source of the four necessary conditions: mutual exclusion, hold-and-wait, no preemption and circular wait.\[3\]\[19\]
- Relevance: your deadlock-prone workload deliberately induces circular wait. Cite this when you describe the workload design.
- [FOUNDATIONAL]

**[Holt1972]** R. C. Holt, "Some deadlock properties of computer systems," *ACM Computing Surveys*, 4(3):179–196, Sept. 1972. DOI: 10.1145/356603.356607. An earlier version appeared at SOSP '71 (DOI 10.1145/800212.806501).\[20\]\[21\]
- Develops a graph model of processes and resources (reusable and consumable) and graph-reduction deadlock detection. Holt's thesis (summarised in an annotated bibliography) shows that a reusable-resource graph with single-unit resources is deadlocked if and only if it contains a cycle. Andrews and Levin (1982) note that Holt's reduction evaluates safety in O(nm).\[14\]\[22\]\[23\]
- Relevance: cite it for resource-allocation graphs and for the deadlock-detection routine you run alongside Banker's.
- [FOUNDATIONAL]

**[Silberschatz2018]** A. Silberschatz, P. B. Galvin and G. Gagne, *Operating System Concepts*, 10th ed., Wiley, 2018. ISBN 978-1-119-32091-3.\[24\] URL: https://www.wiley.com/en-us/Operating+System+Concepts,+10th+Edition-p-9781119320913
- The standard textbook presentation of the safety and resource-request algorithms with Available/Max/Allocation/Need. It states that the safety algorithm may require on the order of m×n² operations (the exact chapter and page are UNVERIFIED).\[25\]
- Relevance: cite it for notation and the textbook loop that your NumPy version is compared against.
- [FOUNDATIONAL]

**[Tanenbaum2022]** A. S. Tanenbaum and H. Bos, *Modern Operating Systems*, 5th ed., Pearson, 2022 (© 2023). ISBN 978-0-13-761887-3 (print).\[26\] URL: https://www.pearson.com/en-us/subject-catalog/p/modern-operating-systems/P200000003295/9780137618880
- A second standard treatment of deadlock avoidance and resource trajectories.
- [FOUNDATIONAL]

**[Belik1987]** F. Belik, "Deadlock avoidance with a modified banker's algorithm," *BIT Numerical Mathematics*, 27(3):290–305, Sept. 1987. DOI: 10.1007/BF01933724\[7\]
- The abstract says avoidance "is preferable in many cases but seldom used on account of its high cost." It states that the banker's algorithm runs in Θ(mn²) for n processes and m resource types, and gives a modification with **amortised worst-case O(mn) under certain likely conditions**, at worst twice as fast as the original.\[7\]
- Relevance: **this is the BIT paper you were looking for, and it is not by Kessels.** Cite it for the Θ(mn²) bound. Also note that your empirical sub-quadratic growth fits its observation that typical cases are cheaper than the worst case.
- [FOUNDATIONAL]

**[Finkel1987]** R. Finkel and H. H. Madduri, "An efficient deadlock avoidance algorithm," *Information Processing Letters*, 24(1):25–30, 1987. DOI: 10.1016/0020-0190(87)90195-5\[5\]
- Generalises the safety test, computes the minimum resources a state needs to be safe, and keeps safe sequences between allocator calls, which gives an O(log n) safety test.\[5\] This was confirmed from the abstract only.
- Relevance: "minimum resources needed to stay safe" is a natural *continuous* safety margin, and therefore a strong additional baseline indicator.
- [CLOSEST RELATED]

**[LiCook2007]** Y. Li and R. Cook, "A new algorithm and asymptotical properties for the deadlock detection problem for computer systems with reusable resource types," in *Advances and Innovations in Systems, Computing Sciences and Software Engineering*, Springer, 2007, pp. 509–512. DOI: 10.1007/978-1-4020-6264-3_88\[27\]
- For d ≪ n resource types, the algorithm is n/log n times cheaper than Dijkstra's when d = O(log n). It is linear-time and asymptotically optimal when d and the requests are bounded by constants. The authors say it can improve Banker's.\[4\]
- Relevance: complexity context for your scaling measurements.
- [METHOD SUPPORT]

**[Lang1999]** S.-D. Lang, "An extended banker's algorithm for deadlock avoidance," *IEEE Transactions on Software Engineering*, 25(3), 1999. DOI: 10.1109/32.798330.\[28\] I verified only the metadata, not the content.
- [CLOSEST RELATED, UNVERIFIED content]

**[Zohora2024]** M. F. Zohora, F. Farhin and M. S. Kaiser, "DBDAA: A real-time approach to Dynamic Banker's Deadlock Avoidance Algorithm with optimized time complexity," *PLOS ONE*, 19(9):e0310807, 2024. DOI: 10.1371/journal.pone.0310807\[6\]
- Lets processes join in real time and take part in the safety check immediately. It introduces a "primary unsafe sequence" mechanism and reports reduced safe-state prediction time compared with earlier variants.\[6\]\[29\]\[30\]
- Relevance: the most recent peer-reviewed Banker's variant. Like the others it is about speed and dynamism, not forecasting, which is the gap you fill.
- [CLOSEST RELATED]

### B. Detection, avoidance, prediction

**[Agrawal1983]** R. Agrawal, M. J. Carey and D. J. DeWitt, "Deadlock detection is cheap," *ACM SIGMOD Record*, 13(2):19–34, Jan. 1983 (author list and pages per the ACM DL and dblp). DOI: 10.1145/984523.984524
- In database systems with exclusive locks, a deadlock exists if and only if the waits-for graph has a cycle. The abstract states that "under certain reasonable assumptions, deadlocks can be detected very cheaply," so detection-and-restart is preferred over avoidance.
- Relevance: explains why practical systems detect rather than avoid. It motivates a cheap warning layer on top of detection.
- [MOTIVATION]

**[AndrewsLevin1982]** G. R. Andrews and G. M. Levin, "On-the-fly deadlock prevention," *Proc. 1st ACM PODC*, 1982. DOI: 10.1145/800220.806694\[23\]
- Evaluates safety "between requests," classifying processes as good or bad and evaluating safe requests before they are made, using Holt's O(nm) reduction.\[14\]\[23\]
- Relevance: the earliest precedent I found for **precomputing the safety consequences of future requests**, which is a conceptual ancestor of your one-step lookahead baseline.
- [CLOSEST RELATED]

**[Tunc2023]** H. C. Tunç, U. Mathur, A. Pavlogiannis and M. Viswanathan, "Sound dynamic deadlock prediction in linear time," *Proc. ACM Program. Lang.* 7(PLDI), Article 177, 2023, pp. 1733–1758. DOI: 10.1145/3591291 (arXiv:2304.03692)\[31\]
- Defines sync-preserving deadlocks and gives SPDOffline and SPDOnline, a strictly online, linear-time algorithm suited to runtime monitoring, which predicts lock deadlocks by reasoning about reorderings of an observed trace.\[32\]
- Relevance: this is what "deadlock prediction" means in the programming-languages community. It is about *lock-order deadlocks in a program trace*, not *multi-unit resource allocation under declared claims*, and you should say so explicitly.
- [CLOSEST RELATED, different problem]

**[LeNgoc2023]** H. Le Ngoc and H. Tran Cong, "Enhancing load balancing in cloud computing through deadlock prediction," in *INISCOM 2023*, LNICST vol. 531, Springer, 2023, pp. 257–274. DOI: 10.1007/978-3-031-47359-3_19\[8\]
- Uses a linear-regression model (Weka) inside CloudSim to forecast the possibility of "deadlock" in VMs and allocates resources to avoid it. It reports better load balancing than standard algorithms.\[8\]\[33\]
- Relevance: the closest *resource-side* "prediction" paper. The differences are that it defines deadlock loosely as overloaded or hanging VMs rather than Banker's unsafety, reports no lead time or event-level precision, and evaluates against load balancers rather than a safety-check oracle.
- [CLOSEST RELATED]

**[Oluwaseyi2024]** J. Oluwaseyi, "AI-Enhanced Predictive Systems for Thread Deadlock Resolution: Early Detection and Prevention in Cloud Applications," EasyChair Preprint 14955, 2024.\[34\] URL: https://easychair.org/publications/preprint/fQbd/open. **Preprint, not peer-reviewed.**
- A narrative overview proposing ML classification of system states as "safe or at risk of deadlock," event-sequence prediction and anomaly detection.\[10\] I saw no experimental evaluation in the parts I read.
- Relevance: cite it at most as evidence that the idea is being *discussed*. It adds nothing empirical. A companion preprint by a different author (W. Kolawole, EasyChair Preprint 15019, 2024) is similar.\[35\]
- [CLOSEST RELATED, weak]

**[Lin2019-DRAGON]** C.-Y. Lin, T.-A. Yeh and J. Chou, "DRAGON: A dynamic scheduling and scaling controller for managing distributed deep learning jobs in Kubernetes cluster," *Proc. CLOSER 2019*, SciTePress, pp. 569–577. DOI: 10.5220/0007707605690577\[36\]
- Adds gang scheduling to Kubernetes to avoid idle, partially allocated resources. It reports 20–30% higher utilisation and more than 65% shorter job time than the default scheduler.\[36\]
- Relevance: a modern hold-and-wait scenario. Partial pod allocation is exactly the "spike"-like broad grab your workloads model.
- [MOTIVATION]

**[Jayaram2019-FfDL]** K. R. Jayaram, V. Muthusamy, P. Dube, V. Ishakian, C. Wang, B. Herta, S. Boag, D. Arroyo, A. Tantawi, A. Verma, F. Pollok and R. Khalaf, "FfDL: A flexible multi-tenant deep learning platform," *Proc. ACM/IFIP Middleware 2019*, pp. 82–95 (per dblp). DOI: 10.1145/3361525.3361538 (also arXiv:1909.06526).
- Section 3.5 describes "temporary deadlocks" when Kubernetes places pods one by one, for example 4 jobs each placing 1 of 2 learners. Gang scheduling "guaranteed zero temporary deadlocks."\[37\]
- Relevance: the most concrete modern resource-allocation-deadlock anecdote I found.
- [MOTIVATION]

**[K8sBlog2025]** Kubernetes Project, "Kubernetes v1.35: Introducing Workload Aware Scheduling," blog, 29 Dec 2025. URL: https://kubernetes.io/blog/2025/12/29/kubernetes-v1-35-introducing-workload-aware-scheduling/. Non-peer-reviewed.
- States that partial scheduling leads to "resource wastage and potential deadlocks" and introduces all-or-nothing gang placement.\[38\]
- [MOTIVATION]

### C. Early-warning evaluation methodology

**[Hyland2020]** S. L. Hyland, M. Faltys, M. Hüser, X. Lyu, T. Gumbsch, C. Esteban, C. Bock, M. Horn, M. Moor, B. Rieck, M. Zimmermann, D. Bodenham, K. Borgwardt, G. Rätsch and T. M. Merz, "Early prediction of circulatory failure in the intensive care unit using machine learning," *Nature Medicine*, 26:364–373, 2020. DOI: 10.1038/s41591-020-0789-4\[39\]\[40\]
- Defines an **alarm/event-based** evaluation. Recall is "the fraction of events with any alarm in the preceding 8 h", and precision is "the fraction of alarms which correctly predicted an event". These are described as "clinically more meaningful than time point-based measures."\[41\]
- Adds a **silencing policy** that suppresses alarms for 30 min after each alarm.\[42\] Reports 90% event recall with 82% of events caught more than 2 h ahead, a precision of 29.6% at 90% recall, and 0.05 alarms per patient-hour.\[41\]\[43\]
- Notes that events prevented by intervention would count as false positives.\[41\]
- Relevance: the template for your recall, precision, refractory period and lead-time metrics. Your observer mode removes their intervention-confound problem, because nothing is prevented, and that is worth stating as a methodological advantage.
- [METHOD SUPPORT]

**[Munchmeyer2021]** J. Münchmeyer, D. Bindi, U. Leser and F. Tilmann, "The transformer earthquake alerting model: A new versatile approach to earthquake early warning," *Geophysical Journal International*, 225(1), 2021. DOI: 10.1093/gji/ggaa609 (arXiv:2009.06316)
- Compares warning methods by alert performance and **warning time** at F1-optimal thresholds. It shows that lowering the alert threshold trades precision for longer warning times.\[44\]
- Relevance: supports reporting F1 together with lead-time distributions and threshold sweeps (precision–lead-time curves).
- [METHOD SUPPORT]

**[Tatbul2018]** N. Tatbul, T. J. Lee, S. Zdonik, M. Alam and J. Gottschlich, "Precision and recall for time series," *NeurIPS 31*, 2018, pp. 1924–1934. URL: https://proceedings.neurips.cc/paper/2018/hash/8f468c873a32bb0619eaeb2050ba45d1-Abstract.html (arXiv:1803.03639)
- Extends precision and recall to range-based anomalies with tunable existence reward, overlap size, positional bias ("front bias" for early detection) and cardinality (fragmentation) penalties.\[45\]
- Relevance: justifies your flicker-merging of episodes and could support a front-biased recall variant as a sensitivity analysis.
- [METHOD SUPPORT]

**[Lavin2015]** A. Lavin and S. Ahmad, "Evaluating real-time anomaly detection algorithms: the Numenta Anomaly Benchmark," *IEEE ICMLA 2015*, pp. 38–44. DOI: 10.1109/ICMLA.2015.141
- Scores detections within windows around each anomaly, rewarding earlier detection and penalising false positives, with application profiles that weight false positives and false negatives differently.\[46\]
- Relevance: a precedent for window-based scoring and for cost profiles, which you could add as a cost-weighted metric.
- [METHOD SUPPORT]

**[Saito2015]** T. Saito and M. Rehmsmeier, "The precision-recall plot is more informative than the ROC plot when evaluating binary classifiers on imbalanced datasets," *PLoS ONE*, 10(3):e0118432, 2015. DOI: 10.1371/journal.pone.0118432
- Simulations and re-analyses show that PR plots are more informative than ROC on imbalanced data, because precision measures the fraction of correct positive predictions.\[47\]
- [METHOD SUPPORT]

**[Davis2006]** J. Davis and M. Goadrich, "The relationship between precision-recall and ROC curves," *Proc. ICML 2006*, pp. 233–240. DOI: 10.1145/1143844.1143874
- A curve dominates in ROC space if and only if it dominates in PR space. Linear interpolation in PR space is incorrect, and optimising AUROC does not guarantee optimising AUPRC.\[48\]\[49\]
- Relevance: if you report PR curves, do not linearly interpolate between threshold points.
- [METHOD SUPPORT]

**[Efron1993]** B. Efron and R. J. Tibshirani, *An Introduction to the Bootstrap*, Chapman & Hall/CRC, 1993. DOI: 10.1201/9780429246593\[50\]
- The standard reference for bootstrap confidence intervals, including percentile and BCa intervals.\[51\]
- Relevance: cite it for your stratified bootstrap. Resample whole *sequences* (the independent unit) within scenario×size strata, not individual steps.
- [METHOD SUPPORT]

### D. Systems context and motivation

**[Gunawi2016]** H. S. Gunawi, M. Hao, R. O. Suminto, A. Laksono, A. D. Satria, J. Adityatama and K. J. Eliazar, "Why does the cloud stop computing? Lessons from hundreds of service outages," *Proc. ACM SoCC 2016*, pp. 1–16. DOI: 10.1145/2987550.2987583
- Analyses 1,247 news and post-mortem reports covering 597 unplanned outages of 32 services from 2009 to 2015. Section 5.5 of the final SoCC '16 paper states that "load-related problems, which cover 9% of outages, originate from four sources: (1) user requests, (2) code upgrades, (3) misconfiguration, and (4) flawed recovery," and Table 3 lists LOAD as the cause of 31 outages across 18 services. The percentages are computed among outages with known root causes; 355 of the 597 outages have UNKNOWN root causes.
- Relevance: motivates resource-pressure early warning in real services.
- [MOTIVATION]

**[Ewaschuk2016-SRE]** R. Ewaschuk (ed. B. Beyer), "Monitoring distributed systems," Chapter 6 in *Site Reliability Engineering: How Google Runs Production Systems*, O'Reilly, 2016. URL: https://sre.google/sre-book/monitoring-distributed-systems/
- "When pages occur too frequently, employees second-guess, skim, or even ignore incoming alerts... Effective alerting systems have good signal and very low noise." Rules that page humans "should be simple to understand and represent a clear failure," and saturation should page when "nearly problematic."\[52\]\[53\]
- Relevance: an industry case for **explainable, rule-based** indicators and for treating precision as a first-class metric. It also directly endorses alerting on near-saturation, which is what your score does.
- [MOTIVATION]

**[Salfner2010]** F. Salfner, M. Lenk and M. Malek, "A survey of online failure prediction methods," *ACM Computing Surveys*, 42(3), Article 10, 2010. DOI: 10.1145/1670679.1670680
- A taxonomy of online failure prediction from runtime monitoring of the current system state. It frames prediction quality in terms of **lead time**, prediction window and precision and recall.\[54\]\[55\]
- Relevance: places your work in the failure-prediction tradition, with "unsafe state" as the failure and "allocation state" as the monitored variable.
- [METHOD SUPPORT]

### E. Methodology support (gaps)

My search budget ran out before I found peer-reviewed sources on (i) simulation methodology and reproducibility for OS resource-management research, (ii) probabilistic Banker's variants and avoidance without known maximum claims, and (iii) empirical estimation of maximum claims. Classical sources do discuss the known-claims requirement: EWD623 assumes a pre-stated "need", and DBDAA lists static declared claims as a key limitation.\[6\]\[11\] These remain **open items** (see Section 8). Do not cite anything in these areas until you have found and checked it.

## 3. Related-work narrative (draft)

**Deadlock theory and avoidance.** Deadlock in resource-allocation systems was characterised early by Coffman et al. [Coffman1971], whose four necessary conditions remain the standard vocabulary, and by Holt [Holt1972], who introduced graph models with reusable and consumable resources and graph-reduction detection.\[3\]\[22\] Avoidance originates with Dijkstra's Banker's algorithm [Dijkstra-EWD123, Dijkstra-EWD623], in which a pattern of loans and needs is safe if a granting order exists that lets every process complete.\[2\] Habermann generalised the algorithm to multiple resource types [Habermann1969] and showed that, in the worst case, processes avoid deadlock if and only if the state is safe.\[14\] Holt [Holt1971] later pointed out that safety alone does not prevent permanent blocking.\[56\] Textbooks present the safety algorithm in the Available/Max/Allocation/Need form used here [Silberschatz2018, Tanenbaum2022].

**Cost of the safety test.** The textbook safety check costs Θ(mn²) for n processes and m resource types, and Belik [Belik1987] observed that avoidance is "seldom used on account of its high cost."\[7\] Most subsequent work has therefore targeted speed. Belik obtained an amortised O(mn) variant under likely conditions [Belik1987].\[7\] Finkel and Madduri maintained safe sequences between allocator calls to reach an O(log n) test [Finkel1987].\[5\] Li and Cook gave near-linear algorithms when the number of resource types is small [LiCook2007].\[4\] Zohora et al. recently proposed DBDAA, which admits processes dynamically and speeds up safe-state determination [Zohora2024].\[6\] Andrews and Levin evaluated the safety of prospective requests between requests [AndrewsLevin1982], an idea close in spirit to our one-step lookahead baseline.\[14\] All of these works answer the same binary question, namely whether the state is safe now, more cheaply. None of them asks how close the system is to becoming unsafe, or how early that could be signalled.

**Detection in practice.** Practical systems often prefer detection and recovery. In databases, deadlock corresponds to a cycle in the waits-for graph and can be detected cheaply [Agrawal1983].\[57\] Cluster schedulers reproduce the hold-and-wait pattern when gang-structured jobs are placed pod by pod. Platforms have reported "temporary deadlocks" from partial placement and adopted gang scheduling to avoid them [Jayaram2019-FfDL, Lin2019-DRAGON, K8sBlog2025].\[36\]\[37\]\[38\] In a study of 597 cloud outages, Gunawi et al. found that load-related problems caused 31 outages across 18 of 32 services, or 9% of outages with known root causes [Gunawi2016].

**Deadlock prediction.** The term "deadlock prediction" covers two distinct lines of work. In programming languages, predictive analysis infers lock-order deadlocks that could occur under some reordering of an observed trace. Tunç et al. give a sound online algorithm that runs in linear time [Tunc2023].\[9\]\[58\] That setting concerns mutex acquisition order in program executions, not multi-unit resource allocation against declared maximum claims. On the resource side, Le Ngoc and Tran Cong used linear regression in CloudSim to forecast VM "deadlock" for load balancing [LeNgoc2023].\[33\] Their notion of deadlock is overload rather than Banker's unsafety, and they report neither lead time nor event-level precision. Preprints proposing AI-based thread-deadlock prediction exist [Oluwaseyi2024] but provide no empirical evaluation.\[10\] To our knowledge, no prior work measures how early, and how reliably, an unsafe state can be anticipated before the safety check reports it.

**Early-warning evaluation.** We therefore borrow evaluation practice from domains where early warning is mature. Online failure prediction frames the task in terms of lead time and prediction windows [Salfner2010]. In intensive care, Hyland et al. evaluate alarms at the event level: recall is the fraction of events preceded by an alarm within a window, precision is the fraction of alarms followed by an event, and alarms are silenced for a fixed period after firing [Hyland2020].\[42\] We adopt the same structure, with a refractory period of R steps. Earthquake early warning reports alert quality together with warning time and shows that thresholds trade one against the other [Munchmeyer2021]. Range-based precision and recall [Tatbul2018] and window-based scoring in the Numenta Anomaly Benchmark [Lavin2015] motivate our treatment of unsafe episodes as ranges and our merging of flickering episodes. Because unsafe onsets are rare, we report precision and recall rather than ROC [Saito2015, Davis2006], and we quantify uncertainty with a stratified bootstrap over sequences [Efron1993]. Site reliability practice also favours simple, explainable alert rules with high signal and low noise, and paging on saturation that is nearly problematic [Ewaschuk2016-SRE]. This supports our choice of a transparent, rule-based score over an opaque model.

**Positioning.** Our contribution sits between these lines of work. We keep Banker's definition of safety as ground truth, run the system in observer mode so that unsafe states actually occur, and evaluate cheap allocation-state indicators as an early-warning system against random, threshold and exact-lookahead baselines.

## 4. Novelty and gap statement

Prior work on Banker's algorithm has made the safety test faster [Belik1987, Finkel1987, LiCook2007, Zohora2024] or more permissive [Habermann1969, Lang1999], but it has always answered a binary, present-tense question. "Deadlock prediction" research either targets lock-order deadlocks in program traces [Tunc2023] or uses loosely defined, overload-based notions of deadlock in cloud simulators without event-level timing metrics [LeNgoc2023]. We found no study that (i) lets a system drift into Banker-unsafe states under controlled workloads, (ii) scores explainable allocation-state indicators as an early-warning signal, and (iii) evaluates them with event-based precision, recall, lead time, refractory periods and confidence intervals against matched-rate random, threshold and exact one-step-lookahead baselines. The **framing and evaluation methodology** are therefore novel for resource-allocation deadlock. The individual techniques are not. The claim should be worded as "to our knowledge," because the searches did not cover simulation-methodology venues or probabilistic avoidance in depth.

**Closest prior works and how you differ:**
1. **Belik 1987 / Finkel and Madduri 1987.** Faster exact safety tests. You do not speed the test up; you anticipate its verdict. Finkel and Madduri's "minimum resources needed to be safe" is a candidate continuous indicator you should test.\[5\]
2. **Andrews and Levin 1982.** Precomputes the safety of prospective requests, conceptually your lookahead baseline.\[14\] You quantify its cost and accuracy and compare cheap proxies against it.
3. **Zohora et al. 2024 (DBDAA).** A dynamic Banker's algorithm with a "primary unsafe sequence" mechanism.\[29\] It is still binary and avoidance-oriented, with no lead-time evaluation.
4. **Le Ngoc and Tran Cong 2023.** ML "deadlock prediction" in CloudSim.\[8\] Its deadlock definition differs, it has no Banker's oracle, and it has no event-level metrics.
5. **Tunç et al. 2023.** Sound online prediction of lock deadlocks.\[32\] It is a different problem (lock-order cycles in traces) and needs no maximum claims.

## 5. Reviewer objections and responses

| Objection | Why it bites | Response, with literature support |
|---|---|---|
| **Circularity**: need pressure and contention are computed from the same Need/Available matrices that Banker's uses, so the score "approximates the oracle". | Reviewers may see the result as trivially expected. | Present it as intended: the question is whether O(m·n) aggregates anticipate an O(mn²) verdict *before* it flips. The exact lookahead baseline [AndrewsLevin1982] bounds what the same information can achieve. Report lead time conditional on detection, and show that the availability threshold (F1 0.16), which also uses the state, does much worse. Add Finkel and Madduri's minimum-resources-to-safety [Finkel1987] as a "smart circular" baseline. |
| **Synthetic workloads** | External validity. | Acknowledge it. Justify controlled scenarios as standard in early-warning method development (Hyland et al. also characterise performance by subgroup [Hyland2020]). Add a sensitivity analysis over claim tightness and random workload parameters. Cite gang-scheduling partial-allocation deadlocks [Jayaram2019-FfDL, Lin2019-DRAGON] to argue that the "spike" scenario is realistic. |
| **Known maximum claims** | Banker's needs declared maxima [Dijkstra-EWD623]; real systems rarely have them. | State it as an inherited limitation, also noted by DBDAA [Zohora2024]. Add an experiment in which the indicators receive noisy or inflated claims (e.g. ×1.2, ×0.8) while ground truth uses the true claims. Contention and waiting ratio partly survive without claims, which is a selling point. |
| **Moderate F1 (0.28)**, and contention alone (0.34) beats the combined score | Looks like weak engineering, and the weighting looks unjustified. | Report it honestly as a finding. Compare with Hyland et al., where a deployed-quality system ran at 29.6% precision at 90% recall [Hyland2020]. Show precision–recall and precision–lead-time curves across thresholds [Munchmeyer2021, Saito2015] rather than one operating point. Investigate why averaging dilutes contention, for example with max-aggregation or weights learned on the tuning seeds. |
| **Lookahead F1 0.74 "on the subset where computed"** | Possible selection bias in the comparison. | Report all methods on the *same* subset, and report the selection criterion. |
| **"Unsafe ≠ deadlock"** | Banker's unsafety is conservative, so why warn about it? | Your data show that 77–100% of unsafe episodes ended in deadlock in observer mode. Report this prominently. Also evaluate with *deadlock onset* as an alternative target. |
| **Metric choices** (onset alarm = miss, censoring, flicker merge) look ad hoc | Researcher degrees of freedom. | Cite the window and silencing definitions [Hyland2020], range-based scoring [Tatbul2018] and NAB windows [Lavin2015]. Run sensitivity analyses over the window (10/20/40 steps), merge gap and R. |
| **Bootstrap independence** | Steps are autocorrelated. | Resample whole sequences within strata [Efron1993]. State this explicitly. |
| **Complexity claim** ("far below Θ(mn²)") | May be confused with a worst-case claim. | Present it as average-case behaviour under your workloads, consistent with Belik's "under certain likely conditions" amortised O(mn) [Belik1987]. |

## 6. Suggested improvements (prioritised)

1. **Report all methods on the lookahead subset**, and add a **cheap approximate lookahead** (check only the k processes with the largest needs) to map the cost–accuracy frontier between your score (cheap) and exact lookahead (about 39× the cost). This is motivated by [AndrewsLevin1982] and [Belik1987].
2. **Add a "distance-to-unsafe" baseline** following Finkel and Madduri's minimum-resources-to-safety computation [Finkel1987]. It is the most principled continuous indicator, and if it beats your score, that is a publishable finding in itself.
3. **Add a learned baseline** (logistic regression or gradient-boosted trees on the same five indicators, trained on the tuning seeds). This mirrors the comparison of ML with a threshold baseline in [Hyland2020] and answers "why not ML?" ([LeNgoc2023] used linear regression). Keep the rule-based score as the explainable default [Ewaschuk2016-SRE].
4. **Threshold sweeps**: PR curves without linear interpolation [Davis2006] and precision versus median-lead-time curves [Munchmeyer2021].
5. **Cost-weighted metric**: an NAB-style application profile [Lavin2015] or a front-biased range recall [Tatbul2018] that rewards earlier alarms.
6. **Robustness to misdeclared claims** (see the table above).
7. **Alternative aggregation**: max or learned weights instead of the mean, since contention alone wins.
8. **Alarm burden**: report alarms per 1,000 steps, the analogue of Hyland's alarms per patient-hour [Hyland2020].

## 7. BibTeX

```bibtex
@misc{Dijkstra-EWD623,
  author = {Edsger W. Dijkstra},
  title = {The mathematics behind the Banker's Algorithm ({EWD} 623)},
  note = {Published in Selected Writings on Computing: A Personal Perspective, Springer-Verlag, 1982, pp. 308--312},
  howpublished = {\url{https://www.cs.utexas.edu/~EWD/transcriptions/EWD06xx/EWD623.html}}
}
@techreport{Dijkstra-EWD123,
  author = {Edsger W. Dijkstra},
  title = {Cooperating Sequential Processes},
  institution = {Technological University, Eindhoven},
  number = {EWD-123},
  year = {1965}
}
@article{Habermann1969,
  author = {A. N. Habermann},
  title = {Prevention of System Deadlocks},
  journal = {Communications of the ACM},
  volume = {12}, number = {7}, pages = {373--377, 385}, year = {1969},
  doi = {10.1145/363156.363160}
}
@article{Holt1971,
  author = {Richard C. Holt},
  title = {Comments on Prevention of System Deadlocks},
  journal = {Communications of the ACM},
  volume = {14}, number = {1}, pages = {36--38}, year = {1971},
  doi = {10.1145/362452.362486}
}
@article{ParnasHabermann1972,
  author = {D. L. Parnas and A. N. Habermann},
  title = {Comment on Deadlock Prevention Method},
  journal = {Communications of the ACM},
  volume = {15}, number = {9}, pages = {840--841}, year = {1972},
  doi = {10.1145/361573.361586}
}
@article{Coffman1971,
  author = {E. G. Coffman and M. Elphick and A. Shoshani},
  title = {System Deadlocks},
  journal = {ACM Computing Surveys},
  volume = {3}, number = {2}, pages = {67--78}, year = {1971},
  doi = {10.1145/356586.356588}
}
@article{Holt1972,
  author = {Richard C. Holt},
  title = {Some Deadlock Properties of Computer Systems},
  journal = {ACM Computing Surveys},
  volume = {4}, number = {3}, pages = {179--196}, year = {1972},
  doi = {10.1145/356603.356607}
}
@book{Silberschatz2018,
  author = {Abraham Silberschatz and Peter B. Galvin and Greg Gagne},
  title = {Operating System Concepts},
  edition = {10th}, publisher = {Wiley}, year = {2018},
  isbn = {978-1-119-32091-3}
}
@book{Tanenbaum2022,
  author = {Andrew S. Tanenbaum and Herbert Bos},
  title = {Modern Operating Systems},
  edition = {5th}, publisher = {Pearson}, year = {2022},
  isbn = {978-0-13-761887-3}
}
@article{Belik1987,
  author = {Ferenc Belik},
  title = {Deadlock Avoidance with a Modified Banker's Algorithm},
  journal = {BIT Numerical Mathematics},
  volume = {27}, number = {3}, pages = {290--305}, year = {1987},
  doi = {10.1007/BF01933724}
}
@article{Finkel1987,
  author = {Raphael Finkel and Hari H. Madduri},
  title = {An Efficient Deadlock Avoidance Algorithm},
  journal = {Information Processing Letters},
  volume = {24}, number = {1}, pages = {25--30}, year = {1987},
  doi = {10.1016/0020-0190(87)90195-5}
}
@incollection{LiCook2007,
  author = {Youming Li and Robert Cook},
  title = {A New Algorithm and Asymptotical Properties for the Deadlock Detection Problem for Computer Systems with Reusable Resource Types},
  booktitle = {Advances and Innovations in Systems, Computing Sciences and Software Engineering},
  publisher = {Springer}, pages = {509--512}, year = {2007},
  doi = {10.1007/978-1-4020-6264-3_88}
}
@article{Lang1999,
  author = {Sheau-Dong Lang},
  title = {An Extended Banker's Algorithm for Deadlock Avoidance},
  journal = {IEEE Transactions on Software Engineering},
  volume = {25}, number = {3}, year = {1999},
  doi = {10.1109/32.798330}
}
@article{Zohora2024,
  author = {Most Fatematuz Zohora and Fahiba Farhin and M. Shamim Kaiser},
  title = {{DBDAA}: A Real-Time Approach to Dynamic Banker's Deadlock Avoidance Algorithm with Optimized Time Complexity},
  journal = {PLOS ONE},
  volume = {19}, number = {9}, pages = {e0310807}, year = {2024},
  doi = {10.1371/journal.pone.0310807}
}
@inproceedings{AndrewsLevin1982,
  author = {Gregory R. Andrews and Gary M. Levin},
  title = {On-the-fly Deadlock Prevention},
  booktitle = {Proc. 1st ACM SIGACT-SIGOPS Symposium on Principles of Distributed Computing (PODC)},
  year = {1982},
  doi = {10.1145/800220.806694}
}
@article{Agrawal1983,
  author = {Rakesh Agrawal and Michael J. Carey and David J. DeWitt},
  title = {Deadlock Detection is Cheap},
  journal = {ACM SIGMOD Record},
  volume = {13}, number = {2}, pages = {19--34}, year = {1983},
  doi = {10.1145/984523.984524}
}
@article{Tunc2023,
  author = {H{\"u}nkar Can Tun{\c{c}} and Umang Mathur and Andreas Pavlogiannis and Mahesh Viswanathan},
  title = {Sound Dynamic Deadlock Prediction in Linear Time},
  journal = {Proceedings of the ACM on Programming Languages},
  volume = {7}, number = {PLDI}, pages = {1733--1758}, year = {2023},
  doi = {10.1145/3591291}
}
@inproceedings{LeNgoc2023,
  author = {Hieu Le Ngoc and Hung Tran Cong},
  title = {Enhancing Load Balancing in Cloud Computing Through Deadlock Prediction},
  booktitle = {Industrial Networks and Intelligent Systems (INISCOM 2023)},
  series = {LNICST}, volume = {531}, pages = {257--274},
  publisher = {Springer}, year = {2023},
  doi = {10.1007/978-3-031-47359-3_19}
}
@misc{Oluwaseyi2024,
  author = {Joseph Oluwaseyi},
  title = {{AI}-Enhanced Predictive Systems for Thread Deadlock Resolution: Early Detection and Prevention in Cloud Applications},
  howpublished = {EasyChair Preprint 14955},
  year = {2024},
  url = {https://easychair.org/publications/preprint/fQbd/open}
}
@inproceedings{Lin2019DRAGON,
  author = {Chan-Yi Lin and Ting-An Yeh and Jerry Chou},
  title = {{DRAGON}: A Dynamic Scheduling and Scaling Controller for Managing Distributed Deep Learning Jobs in {Kubernetes} Cluster},
  booktitle = {Proc. 9th Int. Conf. on Cloud Computing and Services Science (CLOSER)},
  pages = {569--577}, publisher = {SciTePress}, year = {2019},
  doi = {10.5220/0007707605690577}
}
@inproceedings{Jayaram2019FfDL,
  author = {K. R. Jayaram and Vinod Muthusamy and Parijat Dube and Vatche Ishakian and Chen Wang and Benjamin Herta and Scott Boag and Diana Arroyo and Asser Tantawi and Archit Verma and Falk Pollok and Rania Khalaf},
  title = {{FfDL}: A Flexible Multi-tenant Deep Learning Platform},
  booktitle = {Proc. 20th Int. Middleware Conference (Middleware '19)},
  pages = {82--95}, year = {2019},
  doi = {10.1145/3361525.3361538}
}
@misc{K8sBlog2025,
  author = {{Kubernetes Project}},
  title = {Kubernetes v1.35: Introducing Workload Aware Scheduling},
  year = {2025},
  howpublished = {\url{https://kubernetes.io/blog/2025/12/29/kubernetes-v1-35-introducing-workload-aware-scheduling/}}
}
@article{Hyland2020,
  author = {Stephanie L. Hyland and Martin Faltys and Matthias H{\"u}ser and Xinrui Lyu and Thomas Gumbsch and Crist{\'o}bal Esteban and Christian Bock and Max Horn and Michael Moor and Bastian Rieck and Marc Zimmermann and Dean Bodenham and Karsten Borgwardt and Gunnar R{\"a}tsch and Tobias M. Merz},
  title = {Early Prediction of Circulatory Failure in the Intensive Care Unit Using Machine Learning},
  journal = {Nature Medicine},
  volume = {26}, number = {3}, pages = {364--373}, year = {2020},
  doi = {10.1038/s41591-020-0789-4}
}
@article{Munchmeyer2021,
  author = {Jannes M{\"u}nchmeyer and Dino Bindi and Ulf Leser and Frederik Tilmann},
  title = {The Transformer Earthquake Alerting Model: A New Versatile Approach to Earthquake Early Warning},
  journal = {Geophysical Journal International},
  volume = {225}, number = {1}, year = {2021},
  doi = {10.1093/gji/ggaa609}
}
@inproceedings{Tatbul2018,
  author = {Nesime Tatbul and Tae Jun Lee and Stan Zdonik and Mejbah Alam and Justin Gottschlich},
  title = {Precision and Recall for Time Series},
  booktitle = {Advances in Neural Information Processing Systems 31 (NeurIPS)},
  pages = {1924--1934}, year = {2018},
  url = {https://proceedings.neurips.cc/paper/2018/hash/8f468c873a32bb0619eaeb2050ba45d1-Abstract.html}
}
@inproceedings{Lavin2015,
  author = {Alexander Lavin and Subutai Ahmad},
  title = {Evaluating Real-Time Anomaly Detection Algorithms -- The {Numenta} Anomaly Benchmark},
  booktitle = {Proc. IEEE 14th Int. Conf. on Machine Learning and Applications (ICMLA)},
  pages = {38--44}, year = {2015},
  doi = {10.1109/ICMLA.2015.141}
}
@article{Saito2015,
  author = {Takaya Saito and Marc Rehmsmeier},
  title = {The Precision-Recall Plot Is More Informative than the {ROC} Plot When Evaluating Binary Classifiers on Imbalanced Datasets},
  journal = {PLoS ONE},
  volume = {10}, number = {3}, pages = {e0118432}, year = {2015},
  doi = {10.1371/journal.pone.0118432}
}
@inproceedings{Davis2006,
  author = {Jesse Davis and Mark Goadrich},
  title = {The Relationship Between Precision-Recall and {ROC} Curves},
  booktitle = {Proc. 23rd Int. Conf. on Machine Learning (ICML)},
  pages = {233--240}, year = {2006},
  doi = {10.1145/1143844.1143874}
}
@book{Efron1993,
  author = {Bradley Efron and Robert J. Tibshirani},
  title = {An Introduction to the Bootstrap},
  publisher = {Chapman \& Hall/CRC}, year = {1993},
  doi = {10.1201/9780429246593}
}
@inproceedings{Gunawi2016,
  author = {Haryadi S. Gunawi and Mingzhe Hao and Riza O. Suminto and Agung Laksono and Anang D. Satria and Jeffry Adityatama and Kurnia J. Eliazar},
  title = {Why Does the Cloud Stop Computing? Lessons from Hundreds of Service Outages},
  booktitle = {Proc. 7th ACM Symposium on Cloud Computing (SoCC)},
  pages = {1--16}, year = {2016},
  doi = {10.1145/2987550.2987583}
}
@incollection{Ewaschuk2016SRE,
  author = {Rob Ewaschuk},
  editor = {Betsy Beyer and Chris Jones and Jennifer Petoff and Niall Richard Murphy},
  title = {Monitoring Distributed Systems},
  booktitle = {Site Reliability Engineering: How Google Runs Production Systems},
  publisher = {O'Reilly}, year = {2016},
  isbn = {978-1491929124},
  url = {https://sre.google/sre-book/monitoring-distributed-systems/}
}
@article{Salfner2010,
  author = {Felix Salfner and Maren Lenk and Miroslaw Malek},
  title = {A Survey of Online Failure Prediction Methods},
  journal = {ACM Computing Surveys},
  volume = {42}, number = {3}, articleno = {10}, pages = {1--42}, year = {2010},
  doi = {10.1145/1670679.1670680}
}
```

## 8. "To verify" list

- **"Kessels" BIT paper**: not found in dblp, the IPL tables of contents or web searches. DOI 10.1007/BF01933724 is Belik (1987).\[7\] Drop "Kessels" unless you find a primary source.
- **EWD108**: the exact year and stable archive URL are UNVERIFIED. Use EWD-123 (1965) or EWD623 for quotes.
- **Agrawal 1983**: per the ACM DL and dblp, the authors are R. Agrawal, M. J. Carey and D. J. DeWitt, SIGMOD Record 13(2):19–34, Jan. 1983. I took this from the enrichment pass and did not open the page myself, so check it once.
- **Finkel and Madduri 1987**: confirmed from the abstract snippet only. Read the paper before relying on the O(log n) claim.
- **Lang 1999**: content UNVERIFIED (metadata only).
- **FfDL**: per dblp, it was published at Middleware 2019, pp. 82–95, DOI 10.1145/3361525.3361538, with 12 authors led by K. R. Jayaram. I took this from the enrichment pass and did not open the page myself, so check it once.
- **Gunawi 2016**: the final SoCC '16 paper (§5.5) also gives "9% of outages" as load-related, and Table 3 lists 31 LOAD outages across 18 services. Percentages are among known root causes; 355 of the 597 outages have UNKNOWN root causes. Quote the percentage with that qualifier.
- **Hyland 2020**: the abstract says the system "predicts 90% of circulatory-failure events in the test set, with 82% identified more than 2 h in advance, resulting in an AUROC of 0.94 and an AUPRC of 0.63." The main text reports time-point-level AUPRCs of "0.467, 0.454, and 0.254 for the full, compact and baseline models." The 0.63 is therefore not a time-point AUPRC, so quote each number together with its evaluation level.
- **Silberschatz 10th ed.**: chapter and page for the "m × n²" statement are UNVERIFIED.
- **SRE book**: the editors are Betsy Beyer, Chris Jones, Jennifer Petoff and Niall Richard Murphy (O'Reilly, 2016, ISBN 978-1491929124, per publisher listings). The chapter author is Rob Ewaschuk.
- **Not found (open gaps)**: probabilistic Banker's variants, avoidance without known maximum claims, empirical claim estimation, simulation-methodology and reproducibility guidance for OS research, and any prior use of resource-pressure risk scores to anticipate deadlock or starvation. Search these specifically (e.g. ACM SIGMETRICS, IEEE TPDS, Petri-net deadlock avoidance in flexible manufacturing systems) before submission.

## Sources

1. [Banker's algorithm - AlgorithmWiki](http://algorithm-wiki.org/wiki2/index.php?title=Banker%27s_algorithm)
2. [The mathematics behind the Banker's Algorithm (EWD 623)](https://repositories.lib.utexas.edu/server/api/core/bitstreams/50d1a86e-639e-496b-8b1e-f88c7f3496db/content)
3. [Deadlock](https://www.cs.yale.edu/homes/aspnes/pinewiki/Deadlock.html)
4. [A New Algorithm and Asymptotical Properties for the Deadlock Detection Problem for Computer Systems with Reusable Resource Types](https://link.springer.com/chapter/10.1007/978-1-4020-6264-3_88)
5. [An efficient deadlock avoidance algorithm - ScienceDirect](https://www.sciencedirect.com/science/article/abs/pii/0020019087901955)
6. [DBDAA: A real-time approach to Dynamic Banker’s Deadlock Avoidance Algorithm with optimized time complexity](https://journals.plos.org/plosone/article?id=10.1371%2Fjournal.pone.0310807)
7. [Deadlock avoidance with a modified banker's algorithm - BIT Numerical Mathematics](https://link.springer.com/article/10.1007/BF01933724)
8. [Enhancing Load Balancing in Cloud Computing Through Deadlock Prediction](https://link.springer.com/chapter/10.1007/978-3-031-47359-3_19)
9. [177 Sound Dynamic Deadlock Prediction in Linear Time](https://arxiv.org/pdf/2304.03692)
10. [EasyChair Preprint №14955 AI-Enhanced Predictive Systems for Thread](https://easychair.org/publications/preprint/fQbd/open)
11. [E.W.Dijkstra Archive: The mathematics behind the Bankers Algorithm (EWD 623)](https://www.cs.utexas.edu/~EWD/transcriptions/EWD06xx/EWD623.html)
12. [Prevention of system deadlocks](https://cacm.acm.org/research/prevention-of-system-deadlocks/)
13. [Prevention of system deadlocks](https://www.semanticscholar.org/paper/Prevention-of-system-deadlocks-Habermann/6b4d5d26348bb100e3ee2bd4d63996b191a05581)
14. [DEADLOCK PREVENTION, DETECTION, and RESOLUTION AN ANNOTATED BIBLIOGRAPHY](https://dl.acm.org/doi/pdf/10.1145/850657.1127874)
15. [Comments on prevention of system deadlocks](https://cacm.acm.org/research/comments-on-prevention-of-system-deadlocks/)
16. [Comment on deadlock preventive method](https://dl.acm.org/doi/10.1145/361573.361586)
17. [Comments on prevention of system deadlocks](https://dl.acm.org/doi/pdf/10.1145/362452.362486)
18. [System Deadlocks](https://dl.acm.org/doi/10.1145/356586.356588)
19. [System Deadlocks, ACM Computing Surveys (CSUR)](https://www.deepdyve.com/lp/association-for-computing-machinery/system-deadlocks-lerTCYaK8g)
20. [Some deadlock properties of computer systems](https://dl.acm.org/doi/10.1145/800212.806501)
21. [Some Deadlock Properties of Computer Systems](https://dl.acm.org/doi/10.1145/356603.356607)
22. [Deadlock is a constant threat in terminal-oriented systems. This](https://webdocs.cs.ualberta.ca/~tony/OldPapers/dead.pdf)
23. [On-the-fly Deadlock Prevention Gregory R. Andrews Gary M. Levin](https://dl.acm.org/doi/pdf/10.1145/800220.806694)
24. [Operating System Concepts, 10th Edition](https://www.wiley.com/en-us/Operating+System+Concepts,+10th+Edition-p-9781119320913)
25. [What is Banker's Algorithm?](https://www.studytonight.com/operating-system/bankers-algorithm)
26. [Modern Operating Systems 5th edition](https://www.vitalsource.com/products/modern-operating-systems-subscription-andrew-s-tanenbaum-herbert-v9780137618941)
27. <https://api.crossref.org/works/10.1007/978-1-4020-6264-3_88>
28. [An Extended Banker's Algorithm for Deadlock Avoidance](https://dl.acm.org/doi/abs/10.1109/32.798330)
29. [\[PDF\] A Dynamic and Improved Implementation of Banker’s Algorithm](https://www.semanticscholar.org/paper/A-Dynamic-and-Improved-Implementation-of-Banker%E2%80%99s-Dixit-M.tech/c1726d8ca8bab9943260e2bd2852d3dbaa737e2f)
30. [DBDAA: A real-time approach to Dynamic Banker’s Deadlock Avoidance Algorithm with optimized time complexity](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC11414889/)
31. [Sound Dynamic Deadlock Prediction in Linear Time - Illinois Experts](https://experts.illinois.edu/en/publications/sound-dynamic-deadlock-prediction-in-linear-time/)
32. [Sound Dynamic Deadlock Prediction in Linear Time](https://dl.acm.org/doi/10.1145/3591291)
33. [CloudSim Architecture \[3\]](https://www.researchgate.net/figure/CloudSim-Architecture-3_fig1_349835588)
34. [Author: Joseph Oluwaseyi](https://easychair.org/publications/author/6fSlQ)
35. [Implementing AI for Thread Deadlock Management: Intelligent Solutions for Early Detection and Prevention in Cloud Environments](https://easychair.org/publications/preprint/d2c6v)
36. [SCITEPRESS - SCIENCE AND TECHNOLOGY PUBLICATIONS](https://www.scitepress.org/Papers/2019/77076/)
37. [FfDL : A Flexible Multi-tenant Deep Learning Platform](https://arxiv.org/pdf/1909.06526)
38. [Kubernetes v1.35: Introducing Workload Aware Scheduling](https://kubernetes.io/blog/2025/12/29/kubernetes-v1-35-introducing-workload-aware-scheduling/)
39. [Circulatory failure is predictable](https://www.sciencedaily.com/releases/2020/03/200309130050.htm)
40. [Early prediction of circulatory failure in the intensive care unit using machine learning - PubMed](https://pubmed.ncbi.nlm.nih.gov/32152583/)
41. <https://www.nature.com/articles/s41591-020-0789-4>
42. [EARLY PREDICTION OF RESPIRATORY FAILURE IN THE INTENSIVE CARE UNIT](https://arxiv.org/pdf/2105.05728)
43. [\[PDF\] Early prediction of circulatory failure in the intensive care unit using machine learning](https://www.semanticscholar.org/paper/Early-prediction-of-circulatory-failure-in-the-care-Hyland-Faltys/5e34d633a076f9df0227f8e2e05cfd76e33f2960)
44. [The transformer earthquake alerting model: A new versatile approach to earthquake early warning](https://arxiv.org/html/2009.06316v4)
45. [Precision and Recall for Time Series \[Quick Review\]](https://liner.com/review/precision-and-recall-for-time-series)
46. [Conformal k-NN Anomaly Detector for Univariate Data Streams](https://arxiv.org/pdf/1706.03412)
47. [The Precision-Recall Plot Is More Informative than the ROC Plot When Evaluating Binary Classifiers on Imbalanced Datasets](https://journals.plos.org/plosone/article?id=10.1371%2Fjournal.pone.0118432)
48. [(Open Access) The relationship between Precision-Recall and ROC curves (2006)](https://scispace.com/papers/the-relationship-between-precision-recall-and-roc-curves-4ojtpyg4ry)
49. [The Relationship Between Precision-Recall and ROC Curves](https://mlanthology.org/icml/2006/davis2006icml-relationship/)
50. [Adaptive Bag of Little Bootstraps for Nonsmooth Robust Inference: A Stability-Driven Framework with Reproducible Cholera Surveillance Illustration from the Democratic Republic of the Congo](https://arxiv.org/pdf/2608.16892)
51. [contentValidity: Content Validity Indices for Instrument ...](https://cran.rstudio.com/web//packages/contentValidity/contentValidity.pdf)
52. [Chapter 6 - Monitoring Distributed Systems](https://sre.google/sre-book/monitoring-distributed-systems/)
53. [SRE book notes: Monitoring Distributed Systems](https://bitmaybewise.substack.com/p/sre-book-notes-monitoring-distributed)
54. [A survey of online failure prediction methods](https://dl.acm.org/doi/10.1145/1670679.1670680)
55. [A Survey of AIOps Methods for Failure Management](https://dl.acm.org/doi/full/10.1145/3483424)
56. [Comments on prevention of system deadlocks](https://dl.acm.org/doi/10.1145/362452.362486)
57. [Deadlock Detection is Cheap Rakesh Agrawal \~ Michael J. Carey +](https://dl.acm.org/doi/pdf/10.1145/984523.984524)
58. [Sound Dynamic Deadlock Prediction in Linear Time](https://zenodo.org/records/7809600)
