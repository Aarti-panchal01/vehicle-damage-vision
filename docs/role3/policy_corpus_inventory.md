# Role 3 Policy Corpus Inventory

Retrieved on **2026-11-15** for the six added documents. The existing four source records retain their original retrieval dates.

## Inventory

There are **10 PDFs** totaling **284 PDF pages**: eight insurer policy wordings and two regulatory instruments. The policy and regulatory counts are based on the local PDF files and the source manifest. All ten files opened as PDFs; there are no duplicate file hashes or manifest rows without a matching PDF.

| # | Document title | Publisher | Category | Insurer / UIN | Source URL |
|---:|---|---|---|---|---|
| 1 | Auto Secure Private Car Package | TATA AIG | Insurer policy wording | TATA AIG / `IRDAN108RPMT0002V02200001` | [Official policy PDF](https://www.tataaig.com/s3/Policy_Wordings_auto_secure_private_car_package_policy.pdf_703fae35ff.pdf) |
| 2 | Car Package Policy | ACKO | Insurer policy wording | ACKO / `IRDAN157RPMT0013V01202526` | [Official policy PDF](https://acko-cms.ackoassets.com/Policy_Wordings_Acko_Car_Package_Policy_e47e757374.pdf) |
| 3 | Private Car Policy Bundled | HDFC ERGO | Insurer policy wording | HDFC ERGO / `IRDAN146RPMT0041V01202425` | [Official policy PDF](https://customer-portal-assets.hdfcergo.com/documents/PivateCar-Bundled-PolicyWording_TPchange..-221520120878.pdf) |
| 4 | Private Car Long Term Package Policy | SBI General | Insurer policy wording | SBI General / `IRDAN144RPMT0022V01202425` | [Official policy PDF](https://content.sbigeneral.in/uploads/SBIG_Private_Car_Long_Term_Policy_Policy_Wording_26082501_19afcbe403.pdf) |
| 5 | Motor Private Car – Package Policy Wording | Universal Sompo General Insurance Company Limited | Insurer policy wording | Universal Sompo / `IRDAN134RP0004V03200708` | [Official policy PDF](https://www.universalsompo.com/assets/file/motor-private-car/motor-private-car-policy-wordings.pdf) |
| 6 | Policy Wordings Private Car Package Policy (V-07-16-2024) | Liberty General Insurance Limited | Insurer policy wording | Liberty General / `IRDAN150RP0035V02201213` | [Official policy PDF](https://www.libertyinsurance.in/Docx/Policy%20Wordings%20for%20Private%20car%20Package%20policy%20V_16072024.pdf) |
| 7 | Standard Form for Private Car Package Policy | The New India Assurance Company Limited | Insurer policy wording | New India Assurance / **not stated in the PDF** | [Official policy PDF](https://www.newindia.co.in/assets/docs/know-more/motor/STANDARD%20FORM%20FOR%20PRIVATE%20CAR%20PACKAGE%20POLICY.pdf) |
| 8 | Digit Private Car Package Policy – Multi Year – Policy Wording | Go Digit General Insurance Limited | Insurer policy wording | Go Digit / `IRDAN158RPMT0035V01202425` | [Official policy PDF](https://www.godigit.com/content/dam/godigit/directportal/en/downloads/car/digit-private-car-package-policy.pdf) |
| 9 | Motor Vehicles (Third Party Insurance Base Premium and Liability) Rules, 2022, G.S.R. 394(E) | Ministry of Road Transport and Highways, Government of India | Regulation | Not applicable; insurer and UIN intentionally blank | [Official Gazette PDF](https://egazette.gov.in/WriteReadData/2022/236018.pdf) |
| 10 | Motor Vehicles (Third Party Insurance Base Premium and Liability) Amendment Rules, 2024, G.S.R. 32(E) | Ministry of Road Transport and Highways, Government of India | Regulation | Not applicable; insurer and UIN intentionally blank | [Official Gazette PDF](https://egazette.gov.in/WriteReadData/2024/251207.pdf) |

The 2024 instrument amends the 2022 base-premium rules. Both are retained so the amendment can be interpreted against the underlying rules. The New India wording does not state a UIN; none was inferred. Regulatory sources have empty `insurer` and `uin` cells in `sources.csv`, so exact insurer/UIN filtering cannot associate them with a policy. Their `document_category` is `regulation`.

## Categories and publishers

- **Insurer policy wordings: 8.** Publishers: TATA AIG, ACKO, HDFC ERGO, SBI General, Universal Sompo General Insurance Company Limited, Liberty General Insurance Limited, The New India Assurance Company Limited, and Go Digit General Insurance Limited.
- **Regulations: 2.** Publisher: Ministry of Road Transport and Highways, Government of India.
- **Page count: 284.** Existing PDFs: 153 pages; added PDFs: 131 pages.

`data/policy_docs/sources.csv` records each document title, publisher, URL, retrieval date, category, and insurer/UIN where stated. The two regulatory records have no insurer/UIN values.

## Missing and inaccessible sources

- The IRDAI-hosted Motor Insurance Handbook / e-Vahan Bima handbook was not collected. The legacy IRDAI handbook listing returned a gateway error during this run.
- The Indian Motor Tariff 2002 download linked from New India Assurance's official motor page resolved to a 404 page, so it was not added.
- A United India Insurance private-car policy PDF link returned 404, and an ICICI Lombard policy-wording PDF link returned 403. Neither was added.
- The MoRTH-hosted paths for the 2022 and 2024 Gazette PDFs returned HTML rather than PDF files. The same official instruments were obtained from the Government of India's eGazette URLs listed above.
- No separate, current IRDAI motor-insurance circular or guideline, nor a standalone vehicle-parts depreciation schedule, was verified and added in this collection. The corpus includes insurer-specific depreciation wording where present, but those terms must not be treated as universally applicable.

No ChromaDB rebuild was performed. Retrieval/index metadata will be incorporated only during a later, separately authorized rebuild.
