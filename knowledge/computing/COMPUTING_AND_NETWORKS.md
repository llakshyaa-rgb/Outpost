# Computing, Networks and Cybersecurity — Offline Reference

## Computer foundations
A computer system combines hardware, firmware, operating systems, applications, storage and networks. The CPU executes instructions; RAM holds working data; persistent storage retains data after power-off. Filesystems map names to stored data. Backups should be tested, versioned and kept separately from the original device.

## Programming concepts
Variables name values; types define operations; control flow selects execution paths; functions package reusable behaviour; data structures organise information; algorithms define steps. Complexity analysis estimates resource growth. Test normal cases, boundary cases, malformed input and failure recovery. Version control records changes and supports review and rollback.

## Operating systems
Processes are running programs; threads are execution paths; permissions control access; environment variables configure processes; package managers install and update software. Least privilege reduces damage from mistakes. Keep dependencies updated and verify project sources before installation.

## Networks
A network moves data between endpoints. Ethernet and Wi-Fi provide local connectivity; IP addresses identify interfaces; subnet masks/prefixes define network ranges; routers forward packets; DNS maps names to addresses; TCP provides ordered reliable streams; UDP provides datagrams. TLS protects data in transit when correctly configured. Firewalls enforce traffic rules.

## Web architecture
Browsers request resources from servers using HTTP. URLs identify resources. HTML describes structure, CSS presentation and JavaScript behaviour. APIs expose defined operations and data formats. Authentication establishes identity; authorization decides what an identity may do. Validate input, encode output for its context, protect sessions, apply rate limits and avoid exposing secrets.

## Cybersecurity principles
Confidentiality, integrity and availability are core security goals. Threat modelling identifies assets, actors, entry points, trust boundaries, attack paths and mitigations. Use unique passwords, a password manager, multi-factor authentication, software updates, encrypted backups and phishing awareness. Logs help investigations but may contain sensitive data.

## Safe analysis
Inspect unknown files in a controlled environment. Do not execute untrusted files on a personal device. Verify hashes and signatures where available, inspect file types rather than trusting extensions, and preserve originals before analysis. Only test systems you own or have explicit permission to assess.

## Data and privacy
Collect the minimum necessary data, restrict access, encrypt sensitive storage, set retention limits and understand consent and legal obligations. Backups, deletion and synchronisation must be designed deliberately; deletion from one device may not delete copies elsewhere.

## AI and machine learning
A model learns statistical patterns from training data. Training, inference, evaluation and deployment are distinct stages. Assess data provenance, bias, leakage, privacy, robustness, hallucination, latency, cost and monitoring. Benchmark on representative tasks; a high score on a narrow test does not prove general capability.
