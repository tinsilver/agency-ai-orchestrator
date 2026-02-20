# Enrichment Workflow Test Plan

## Overview

This document outlines the test plan for validating the recursive context-gathering validation system. Tests are organized by example request and expected enrichment behavior.

---

## Test Categories

### Category A: High Enrichment Value
Requests where tools can answer 50%+ of missing questions

### Category B: Medium Enrichment Value
Requests where tools can answer 20-50% of missing questions

### Category C: Low Enrichment Value
Requests requiring mostly subjective client input (enrichment < 20%)

---

## Test Cases

### ✅ Test 1: SEO + Social Media (Example 1)

**Client**: luckyjumperfilms.co.uk
**Category**: A (High Value)
**Request**: "Optimize SEO naturally. Link to social media accounts like YouTube, LinkedIn and Instagram. Help with copy and FAQ section."

**Missing Information (9 questions)**:
1. Which specific pages should be prioritized for SEO optimization?
2. What are your target keywords?
3. Which social media accounts do you have active?
4. Do you have existing FAQ content?
5. What is your target audience and geographic focus?
6. Do you want FAQ as dedicated page or integrated?
7. What tone/style should copy follow?
8. Specific competitor sites or reference examples?
9. Do you want schema markup implementation?

**Expected Tool Usage**:
- `web_fetch` → luckyjumperfilms.co.uk (get current structure, existing pages)
- `social_media_finder` → Extract any existing social links from website
- `seo_audit` → Current SEO status, meta tags, keywords
- `web_search` → Find YouTube/LinkedIn/Instagram accounts for the business

**Expected Enrichment Results**:
- ✅ Q1: Can identify current pages from sitemap (confidence: 0.85)
- ❌ Q2: Cannot determine target keywords (subjective)
- ✅ Q3: Can find social media links if publicly listed (confidence: 0.75)
- ✅ Q4: Can detect if FAQ page exists (confidence: 0.90)
- ❌ Q5: Geographic focus may be in footer/about (confidence: 0.50)
- ❌ Q6: Subjective preference
- ⚠️ Q7: Can analyze current tone from copy (confidence: 0.60)
- ❌ Q8: Cannot determine competitor preferences
- ❌ Q9: Subjective technical decision

**Expected Outcome**: 3-4 questions answered (33-44% answer rate)
**Expected Iterations**: 1-2
**Should Complete**: Likely YES (threshold drops to 0.75 at iteration 1)

---

### ✅ Test 2: Brand Redesign with PDF (Example 2)

**Client**: luckyjumperfilms.co.uk
**Category**: A (High Value)
**Request**: "Update website to new brand design. Copy basics from original, but change colours, fonts and layout."

**Missing Information (6 questions)**:
1. What are the new brand colours (hex codes)?
2. Which fonts should be used?
3. Can you provide brand guidelines or design mockups?
4. Specific layout changes needed?
5. Which pages should be updated first?
6. Should the logo be updated to new Business Beanstalk design?

**Expected Tool Usage**:
- `pdf_extract` → Extract colors, fonts, logo info from attached PDF
- `web_fetch` → Current website structure

**Expected Enrichment Results**:
- ✅ Q1: PDF extraction finds hex codes (confidence: 0.95)
- ✅ Q2: PDF extraction finds font names (confidence: 0.95)
- ✅ Q3: PDF IS the brand guidelines (confidence: 1.0)
- ❌ Q4: Subjective design decisions
- ⚠️ Q5: Can list all current pages (confidence: 0.70)
- ✅ Q6: PDF mentions Business Beanstalk (confidence: 0.90)

**Expected Outcome**: 4-5 questions answered (67-83% answer rate)
**Expected Iterations**: 1
**Should Complete**: YES (high confidence answers)

---

### ✅ Test 3: Not a Web Dev Request (Example 3)

**Client**: ginacannon.co.uk
**Category**: C (Low Value)
**Request**: "Amend the email you're using for me. Also confirm tomorrow's direct debit has been cancelled."

**Missing Information (3 questions)**:
1. Clarification if this is a website/web app request
2. Context about what service this relates to
3. Confirmation this was for web development agency

**Expected Tool Usage**:
- None (this should be filtered out as "unclear" category)

**Expected Enrichment Results**:
- ❌ All questions require clarification

**Expected Outcome**: 0 questions answered (0% answer rate)
**Expected Iterations**: 0 (should route to create_admin_task immediately)
**Should Complete**: NO (unclear request)

---

### ✅ Test 4: Contact Form Addition (Example 4)

**Client**: theoruby.com
**Category**: B (Medium Value)
**Request**: "Add a new field to my contact form to ask people for their social media accounts"

**Missing Information (5 questions)**:
1. Which contact form are you referring to?
2. What specific social media platforms should be included?
3. Should the field be required or optional?
4. Single text input or multiple fields or dropdown?
5. Do you want validation rules?

**Expected Tool Usage**:
- `web_fetch` → theoruby.com homepage
- `form_detector` → Find existing contact forms

**Expected Enrichment Results**:
- ✅ Q1: Form detector finds existing form location (confidence: 0.90)
- ⚠️ Q2: Could check if site has social links (confidence: 0.50)
- ❌ Q3-Q5: All subjective UX decisions

**Expected Outcome**: 1-2 questions answered (20-40% answer rate)
**Expected Iterations**: 1-2
**Should Complete**: Maybe (depends on iteration threshold)

---

### ✅ Test 5: Image Replacement (Example 5)

**Client**: tejaskotecha.com
**Category**: C (Low Value)
**Request**: "Updating the file pics with my own pics"

**Missing Information (5 questions)**:
1. Which pages or sections need image updates?
2. Should all images be replaced or only specific ones?
3. What is intended use of each new image?
4. Specific dimensions, formats, or quality requirements?
5. Should images be optimized for web?

**Expected Tool Usage**:
- `web_fetch` → tejaskotecha.com (get current structure)
- `image_analysis` → Analyze attached images

**Expected Enrichment Results**:
- ⚠️ Q1: Can list pages with images (confidence: 0.60)
- ❌ Q2: Subjective decision
- ⚠️ Q3: Image analysis might infer use (confidence: 0.40)
- ✅ Q4: Image analysis gets dimensions (confidence: 0.90)
- ✅ Q5: Image analysis checks if optimized (confidence: 0.85)

**Expected Outcome**: 2 questions answered (40% answer rate)
**Expected Iterations**: 1-2
**Should Complete**: Maybe (borderline)

---

### ✅ Test 6: E-commerce Products (Example 6)

**Client**: thebingeeatingtherapist.com
**Category**: C (Low Value)
**Request**: "Add more downloadable products/replays"

**Missing Information (7 questions)**:
1. What specific products/replays to add?
2. Where should these be displayed?
3. Pricing structure?
4. Shopping cart/payment system or email signup?
5. File formats and sizes?
6. Customer accounts/login functionality?
7. Product management system?

**Expected Tool Usage**:
- `web_fetch` → Check current site structure
- `web_search` → Check if site already has products page

**Expected Enrichment Results**:
- ❌ All questions are subjective business/technical decisions

**Expected Outcome**: 0-1 questions answered (0-14% answer rate)
**Expected Iterations**: 2-3
**Should Complete**: NO (requires extensive client input)

---

### ✅ Test 7: SEO Optimization with Audit (Example 7)

**Client**: bongoworldwide.org
**Category**: A (High Value)
**Request**: "General optimization including keyword changes, plugins, site speed, fixing broken links, indexing"

**Missing Information (9 questions)**:
1. Which pages should keyword changes prioritize?
2. Target keywords from Float Digital audit?
3. Which broken links were identified?
4. Current site speed metrics?
5. Do you have full audit report?
6. Which plugins currently installed?
7. What is current indexing status?
8. Budget/preference for premium vs free plugins?
9. Timeline?

**Expected Tool Usage**:
- `web_fetch` → bongoworldwide.org (get structure)
- `seo_audit` → Current SEO status, broken links, meta tags
- `web_search` → Recommended WordPress SEO plugins

**Expected Enrichment Results**:
- ✅ Q1: SEO audit identifies all pages (confidence: 0.90)
- ❌ Q2: Need actual audit report
- ✅ Q3: SEO audit can find broken links (confidence: 0.85)
- ✅ Q4: SEO audit measures page speed (confidence: 0.80)
- ❌ Q5: Cannot access external report
- ⚠️ Q6: Might detect some plugins from HTML (confidence: 0.50)
- ⚠️ Q7: SEO audit checks indexability (confidence: 0.70)
- ❌ Q8: Subjective budget decision
- ❌ Q9: Subjective timeline

**Expected Outcome**: 3-5 questions answered (33-55% answer rate)
**Expected Iterations**: 1-2
**Should Complete**: YES (good technical answers)

---

### ✅ Test 8: SEO for Artist (Example 8)

**Client**: jillmeager.com
**Category**: B (Medium Value)
**Request**: "Improve SEO. Don't come up on Google for 'Hare Drawings'"

**Missing Information (5 questions)**:
1. Which pages should target 'Hare Drawings'?
2. Target geographic location?
3. Other keywords beyond 'Hare Drawings'?
4. Existing content to optimize or create new?
5. Primary business goal with SEO?

**Expected Tool Usage**:
- `web_fetch` → jillmeager.com
- `seo_audit` → Current SEO, existing content about hares
- `web_search` → Current ranking for "Hare Drawings"

**Expected Enrichment Results**:
- ✅ Q1: Can identify relevant pages (wildlife, gallery) (confidence: 0.75)
- ⚠️ Q2: May find location in footer/about (confidence: 0.60)
- ⚠️ Q3: SEO audit might find current keywords (confidence: 0.50)
- ✅ Q4: Can detect existing hare-related content (confidence: 0.80)
- ❌ Q5: Subjective business goal

**Expected Outcome**: 2-3 questions answered (40-60% answer rate)
**Expected Iterations**: 1-2
**Should Complete**: Maybe (depends on iteration)

---

### ✅ Test 9: Add Photo to Header (Example 9)

**Client**: nargisshah.co.uk
**Category**: B (Medium Value)
**Request**: "Add photo to about page in header"

**Missing Information (5 questions)**:
1. Does website have an 'About' page?
2. Should photo replace or be added alongside existing content?
3. Preferred dimensions and placement?
4. Should photo have styling effects?
5. Is this final version or needs cropping/resizing?

**Expected Tool Usage**:
- `web_fetch` → nargisshah.co.uk (check for about page)
- `image_analysis` → Analyze attached photo dimensions

**Expected Enrichment Results**:
- ✅ Q1: Can confirm About page exists (confidence: 0.95)
- ⚠️ Q2: Can describe current header content (confidence: 0.70)
- ✅ Q3: Image analysis provides dimensions (confidence: 0.90)
- ❌ Q4: Subjective design decision
- ⚠️ Q5: Image analysis can check quality (confidence: 0.60)

**Expected Outcome**: 2-3 questions answered (40-60% answer rate)
**Expected Iterations**: 1
**Should Complete**: YES (enough context with lenient threshold)

---

## Success Metrics

### Target Goals (from FEATURE-improve-validator.md)
- **80%+ requests** should become complete after enrichment
- **60%+ answer rate** on factual questions

### Expected Results from Test Suite

| Test | Category | Answer Rate | Complete After Enrichment | Notes |
|------|----------|-------------|---------------------------|-------|
| 1    | A        | 33-44%      | ✅ YES                    | Social media + SEO |
| 2    | A        | 67-83%      | ✅ YES                    | PDF extraction key |
| 3    | C        | 0%          | ❌ NO                     | Not web dev request |
| 4    | B        | 20-40%      | ⚠️ MAYBE                  | Form detection |
| 5    | C        | 40%         | ⚠️ MAYBE                  | Image analysis |
| 6    | C        | 0-14%       | ❌ NO                     | Too subjective |
| 7    | A        | 33-55%      | ✅ YES                    | SEO audit powerful |
| 8    | B        | 40-60%      | ⚠️ MAYBE                  | SEO for artist |
| 9    | B        | 40-60%      | ✅ YES                    | Simple verification |

**Projected Results**:
- 4-5 of 9 (44-55%) will complete after enrichment
- Average answer rate: 30-45%

**Analysis**:
- Target of 80%+ completion is aggressive (requires lenient thresholds)
- Target of 60%+ answer rate realistic for Category A requests only
- Overall system success depends on iteration thresholds

---

## Test Execution Plan

### Phase 1: Unit Tests (Without Langfuse Prompts)
1. Test routing logic with mocked state
2. Test tool budget enforcement
3. Test iteration counting and limits
4. Test token budget tracking
5. Test no-progress detection

### Phase 2: Integration Tests (Mock LLM Calls)
1. Test complete enrichment workflow with mocked tool results
2. Verify dynamic_context formatting
3. Verify enrichment_history tracking
4. Test all stopping conditions

### Phase 3: End-to-End Tests (With Langfuse Prompts)
1. Create actual prompts in Langfuse UI
2. Run all 9 examples through real workflow
3. Review traces in Langfuse dashboard
4. Measure actual metrics vs projected
5. Tune prompts based on results

---

## Validation Checklist

For each test case, verify:

- [ ] Enrichment iteration increments correctly
- [ ] Correct tools are selected by planner
- [ ] Tool budgets are enforced (no tool exceeds max calls)
- [ ] Token budget is tracked and enforced
- [ ] dynamic_context is properly formatted
- [ ] enrichment_history records each iteration
- [ ] Routing logic selects correct next node
- [ ] Stopping conditions work (complete, max iterations, no progress, token limit)
- [ ] Architect receives enriched context
- [ ] Metrics are reported to Langfuse

---

## Known Limitations

1. **Mock tools**: Current implementation uses mocked web_search, google_maps, google_reviews
2. **No real APIs**: Need API keys for real web search, Google Places, etc.
3. **Image analysis**: Uses property analysis not Claude vision
4. **PDF extraction**: Works only if pypdf is installed and PDFs are text-based
5. **Social media finder**: Regex-based, may miss dynamically loaded links

---

## Next Steps

1. ✅ Create this test plan
2. Create test script for Phase 1 (unit tests)
3. Run Phase 1 tests and fix any issues
4. Create integration test script for Phase 2
5. Create Langfuse prompts using LANGFUSE_PROMPTS_GUIDE.md
6. Run Phase 3 end-to-end tests
7. Analyze results and tune prompts/thresholds
8. Document findings and recommendations
