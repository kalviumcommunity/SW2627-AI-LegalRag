# Sample Documents for Testing Property Intelligence Platform

This folder contains realistic legal and real estate documents designed to test and verify the end-to-end ingestion, vector search, and RAG answering pipeline.

---

## Available Test Documents

| File Name | Format | Subject Matter | Key Details |
| :--- | :--- | :--- | :--- |
| **`commercial_lease_agreement.md`** | Markdown (`.md`) | Commercial Office & Clinic Lease | $14,500/mo rent, 3.5% escalation, 5-year term, $29,000 security deposit, insurance clauses. |
| **`residential_purchase_agreement.txt`** | Text (`.txt`) | Residential Home Purchase Agreement | $875,000 purchase price, $25,000 earnest deposit, solar panel inclusion, 21-day financing contingency. |
| **`property_title_and_environmental_summary.md`** | Markdown (`.md`) | Title Report & Environmental Assessment | M-2 industrial zoning, 15ft utility easement, Phase 1 ESA findings (zero RECs), FEMA flood zone X. |

---

## How to Test via the Web Dashboard

1. **Open the Web Application**:
   Navigate to [http://localhost:5173](http://localhost:5173) in your browser.

2. **Upload a Document**:
   - Drag and drop any of the files in `sample_documents/` directly into the upload dropzone on the Home page or the Documents page.
   - Or click **"browse file"** and select `commercial_lease_agreement.md`, `residential_purchase_agreement.txt`, or `property_title_and_environmental_summary.md`.
   - The document will be uploaded, parsed, chunked, and embedded into your Neon PostgreSQL database.

3. **Verify Document Status**:
   - Go to the **Documents** page (`/documents`) to see the processed document, its chunk count, and file metadata.
   - Click on the document title to open the **Document Details** page (`/documents/:id`), inspect extracted text chunks, and see vector status.

4. **Ask Questions with AI**:
   Navigate to the **Ask Questions** page (`/ask`) or use the mini-card on the Home page. Here are suggested questions to try:

### Recommended Questions to Ask

#### For `commercial_lease_agreement.md`:
- *"What is the monthly base rent and how much does it increase each year?"*
- *"What are the tenant's maintenance responsibilities?"*
- *"What is the required insurance coverage amount?"*
- *"How long does the tenant have to cure a monetary default?"*

#### For `residential_purchase_agreement.txt`:
- *"What is the total purchase price and earnest money deposit?"*
- *"Are the rooftop solar panels and EV charger included in the sale?"*
- *"When is the closing date and how long is the inspection contingency period?"*
- *"What items are excluded from the purchase?"*

#### For `property_title_and_environmental_summary.md`:
- *"What is the zoning designation and what is the maximum building height?"*
- *"Were any Recognized Environmental Conditions (RECs) found in the Phase 1 assessment?"*
- *"What easements are recorded against the property?"*
- *"Is the property located in a flood zone?"*
