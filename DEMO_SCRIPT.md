# 5-Minute Demonstration Script (HACK-P438)

**Target Audience**: Hackathon Judges and Evaluators  
**Estimated Time**: 5 minutes  
**Goal**: Demonstrate AI retrieval with confidence gating, multilingual localization, citizen grievance filing, tracking, and staff management workflows.

---

### Step 1: Start the Prototype (0:00 - 0:30)
1. In your terminal, run:
   ```bash
   uvicorn app.main:app --reload
   ```
2. Open your web browser to `http://127.0.0.1:8000`.
3. Point out the top demonstration banner:
   *"PROTOTYPE (SAMPLE DATA) - Prototype with sample data. Not an official government service."*

---

### Step 2: Test Supported Chat Question (0:30 - 1:15)
1. Click on **AI Assistant** in the top navigation bar (`/chat`).
2. In the query box, type:
   > `What documents do I need for a birth certificate?`
3. Click **Send** (or use the microphone icon if voice input is enabled in Chrome/Edge).
4. **Expected Result**:
   - The assistant returns `HIGH CONFIDENCE`.
   - Answer lists the required documents: Hospital Discharge Summary / Form 1, Parents' ID Proof, Marriage Certificate, Address Proof, and notes that registration within 21 days is free.
   - Verified source card is displayed: `FAQ: What documents do I need for a birth certificate?` with link `https://india.gov.in` and review date `15 Aug 2026`.
   - Disclaimer is shown: *"This is general guidance, not an official legal or administrative decision."*

---

### Step 3: Test Unsupported Question & Refusal (1:15 - 1:50)
1. In the same chat window, enter an out-of-scope question:
   > `Will I win my court case?`
2. Click **Send**.
3. **Expected Result**:
   - The assistant marks the response as `LOW CONFIDENCE`.
   - **No fabricated sources** are shown.
   - Refusal message is displayed:
     *"I cannot answer this question from the curated civic knowledge base. I can only provide guidance on supported public services and procedures. Please explore the Services Directory or submit a formal civic grievance."*
   - A direct button **"File a Grievance"** is offered.

---

### Step 4: Switch Language to Telugu or Hindi (1:50 - 2:30)
1. Look at the language selector in the top-right header (currently showing *English*).
2. Select **తెలుగు** (Telugu).
3. Notice:
   - Header, navigation links, and hero copy instantly translate to Telugu:
     *"ప్రజా సేవలు & పౌర సమస్యల పోర్టల్"*
4. Switch back or select **हिन्दी** (Hindi) to observe Devanagari localization:
   *"सार्वजनिक शिकायत एआई सहायक"*
5. Return language to English for the remainder of the walkthrough.

---

### Step 5: Submit a Grievance (2:30 - 3:30)
1. Click **File Grievance** in the navigation header (`/grievance/new`).
2. Point out the privacy warning banner:
   *"Privacy Notice: We collect only minimal details necessary for addressing your issue. Do NOT enter Aadhaar numbers, PAN, bank account details..."*
3. Fill out the multi-step form:
   - **Step 1 (Details)**:
     - Category: `Water Supply`
     - Subject: `Drinking water pipeline rupture causing street flooding`
     - Description: `Clean drinking water is gushing out of an underground pipeline joint near the community hall. Road is submerged.`
     - Click **Next Step**.
   - **Step 2 (Location)**:
     - Municipal Ward: `Ward 12 - Gandhinagar`
     - Nearest Landmark: `Opposite Gandhi Statue, 4th Cross`
     - Click **Next Step**.
   - **Step 3 (Contact & Proof)**:
     - Name: `Ramesh Kumar`
     - Contact: `citizen@demo.test`
     - Attachment: *(Optional - select a sample JPG or PDF)*
     - Click **Next Step**.
   - **Step 4 (Review)**:
     - Verify details in the review box.
     - Click **Submit Grievance**.
4. **Expected Result**:
   - Redirects to confirmation page `/grievance/confirm/GRV-2026-XXXXXX`.
   - Mandatory banner is prominently displayed:
     *"Demo system: this request is stored in this prototype only and has NOT been sent to any real government department."*
   - Copy or note down the generated reference number (e.g. `GRV-2026-000017`).

---

### Step 6: Track the Grievance (3:30 - 4:00)
1. Click **Track this Request** (or go to `/track` and paste the reference number).
2. Observe the current status:
   - Status badge: `Submitted`
   - Priority badge: `High` (automatically detected from terms like "rupture/flooding")
   - Status Timeline shows entry #1: *"Grievance submitted via citizen web portal"* by *System*.

---

### Step 7: Staff Management Queue & Status Update (4:00 - 4:40)
1. Click **Login** in the top navigation bar (`/login`).
2. Enter staff credentials:
   - Email: `staff@demo.test`
   - Password: `Staff@123`
3. Click **Sign In**.
4. You are redirected to `/admin` (Staff Queue).
   - Point out the pure-CSS analytics bars showing grievances grouped by status and category.
   - Filter by status `Submitted` or category `Water Supply`.
   - Locate the grievance filed in Step 5 and click **Review**.
5. In the **Staff Processing Action** box:
   - Change Status to `In Progress`
   - Staff Review Note: `Emergency maintenance crew dispatched with repair clamp #4.`
   - Click **Save & Append History**.
6. The page reloads showing the new history record appended with timestamp and staff signature.

---

### Step 8: Citizen Sees Updated History (4:40 - 5:00)
1. Click **Logout** (`/logout`).
2. Go to **Track Status** (`/track`) and re-enter the reference number from Step 5.
3. Observe:
   - Current status badge is now **In Progress**.
   - Status Timeline displays both the original submission entry AND the newly appended staff review note:
     *"Emergency maintenance crew dispatched with repair clamp #4."*
4. End of demonstration.
