# Case 2 exception report — CLS/CCRIS vs. supporting documents

- CLS extract: `samples/case-2-account-opening/xyz-sdn-bhd/XYZ Sdn Bhd - CLS Extract.pdf`
- Email request: `samples/case-2-account-opening/xyz-sdn-bhd/XYZ Sdn Bhd - Email Request.pdf`
- SSM search: `samples/case-2-account-opening/xyz-sdn-bhd/XYZ Sdn Bhd - SSM Search.pdf`
- CCRIS application form: `samples/case-2-account-opening/xyz-sdn-bhd/XYZ Sdn Bhd - CCRIS Application Form.pdf`
- Guarantor application form: `samples/case-2-account-opening/xyz-sdn-bhd/XYZ Sdn Bhd - Guarantor Application Form.pdf`
- Semantic checks: Groq not configured — text-diff heuristic only

| KCT | Check | Status | Confidence | Value A | Value B | Source (Value A) | Source (Value B) | Note |
|---|---|---|---|---|---|---|---|---|
| KCT-00001 | Customer name in CLS matches SSM | **REVIEW** | — |  | AIROCEANIC EXPRESS SDN. BHD. |  | XYZ Sdn Bhd - CLS Extract.pdf — CLS core-banking screen extract | Could not extract 'Customer Name' from one or both sources. |
| KCT-00002 | Registration number in CLS matches SSM | **REVIEW** | — |  | 199001016623 |  | XYZ Sdn Bhd - CLS Extract.pdf — CLS core-banking screen extract | Could not extract a registration number from one or both sources. |
| KCT-00003 | Registered address in CLS matches SSM | **REVIEW** | — |  | 910 (ST 1) BLOCK B PHILEO DAMANSARA 2, NO 15 JALAN 16/11, OFF JALAN DAMANSARA, 46350 PETALING JAYA SELANGOR |  | XYZ Sdn Bhd - CLS Extract.pdf — CLS core-banking screen extract | Could not extract 'Registered Address' from one or both sources. |
| KCT-00004 | Business nature in CLS matches SSM | **REVIEW** | — |  | 52290 52299 Other transportation support acti |  | XYZ Sdn Bhd - CLS Extract.pdf — CLS core-banking screen extract | Could not extract 'Business Nature / Industry' from one or both sources. |
| KCT-00005 | Director information matches Application Form / SSM | **REVIEW** | — |  | (no Authorized Signatory list in this sample) |  |  | Could not extract director/officer information from SSM. |
| KCT-00006 | Guarantor information in CLS matches Guarantor Form | **REVIEW** | — |  | DARMENDRAN A/L KUNA, SAFEGUARDS CORPORATI |  | XYZ Sdn Bhd - CLS Extract.pdf — CLS core-banking screen extract | Could not extract 'Guarantor Names' from one or both sources. |
| KCT-00007 | CCRIS information matches CCRIS Form | **REVIEW** | — |  | RM1000000.00 (ACF, purpose code 71) |  | XYZ Sdn Bhd - CLS Extract.pdf — CLS core-banking screen extract | Could not extract a comparable facility amount from one or both sources. |
| KCT-00008 | Mandatory CIF supporting documents are present | **FAIL** | 100% | Application Form (CCRIS), Guarantor Form, SSM Documents, CLS Extract, Email Request | Application Form (CCRIS), SSM Documents, CLS Extract, Email Request | Case 2 document set | Case 2 document set | Missing or unextractable: Guarantor Form. |
| KCT-00009 | Evidence of Maker-Checker review and approval | **REVIEW** | — | Participants:  | Rejection cycle: None, Final confirmation: None |  |  | Groq not configured -- could not analyze the email thread. |

**Summary**: 0 Pass, 1 Fail, 8 Review, 0 N/A.