# Survey Design

## Purpose

This document defines the first survey system for the Django version of `thephage.org`.

The survey system should let admins create configurable member surveys without hardcoding questions in templates. It should preserve old responses well enough for review and export even when survey questions or choices are later edited.

This document supersedes older future-looking survey notes in the existing design docs where those notes assume surveys are always tied directly to a `CampYear`.

## Goals

- Support generic surveys at `/survey/<slug>/`.
- Support year-specific surveys by encoding the year in the survey slug, such as `2026-arrival-survey`.
- Let admins create, edit, order, activate, and deactivate surveys.
- Let members submit and edit their own survey response while a survey is active.
- Store answers in a simple format that supports text, single choice, multiple choice, other answers, and scale-like questions.
- Support simple conditional visibility based on selected choices from choice-based questions.
- Preserve enough snapshots on answers that old responses remain understandable after admin edits.
- Keep V1 small enough to build and maintain reliably.

## Non-Goals

- No public anonymous surveys.
- No survey open/close date windows in V1.
- No draft response state in V1.
- No freeform-text conditional logic in V1.
- No image/photo upload survey questions in V1.
- No matrix/grid questions in V1.
- No multi-page survey builder in V1.
- No directory, roster, aggregate-report, or payment-requirement integration in the first survey implementation unless separately prioritized.
- No numeric analytics over answer values in V1.

## Vocabulary

| Product Term | Code Model |
| --- | --- |
| Survey | `Survey` |
| Question | `SurveyQuestion` |
| Choice | `SurveyChoice` |
| Condition | `SurveyQuestionCondition` |
| Response | `SurveyResponse` |
| Answer | `SurveyAnswer` |

## Survey Activity

`Survey.is_active` controls whether members can submit or edit responses.

An active survey:

- Is accessible to members at `/survey/<slug>/`.
- Allows an authenticated active member to create or update their response.

An inactive survey:

- Does not allow member submission or editing.
- Remains visible to admins.
- Remains exportable by admins.
- Should return a friendly unavailable state or `404` for normal member access.

V1 does not include `opens_at` or `closes_at`.

## Member Routes

| Route | Behavior |
| --- | --- |
| `/survey/<slug>/` | Display and submit the survey |
| `/survey/<slug>/complete/` | Optional completion or confirmation page |

The survey route requires a logged-in active member.

Each user should have at most one response per survey. Returning to an active survey edits the existing response.

### Member Survey Page

`/survey/<slug>/` is the member-facing survey page.

The page should show:

- A first card with the survey name and rendered `description_markdown`.
- One card per question.
- A submit button after all question cards.

If the logged-in member already has a response, the survey should prepopulate their previous answers and allow them to revise and resubmit while the survey is active.

Submitting the survey:

- Creates a response if the member has not answered before.
- Updates the existing response if one already exists.
- Redirects to `/survey/<slug>/complete/` after a successful POST.

`/survey/<slug>/complete/` is the completion page for now. It can be simple and should link back to the survey while the survey remains active.

## Admin Routes

The admin UI should follow existing admin patterns.

| Route | Behavior |
| --- | --- |
| `/admin/surveys/` | Survey overview and create-survey card |
| `/admin/surveys/<slug>/` | Edit survey metadata, view and update questions, create questions, delete survey |
| `/admin/surveys/<slug>/<question_id>/` | Edit one question, configure conditions, delete question |
| `/admin/surveys/<slug>/responses/` | View response table |
| `/admin/surveys/<slug>/responses.csv` | Download response table as CSV |

Admin UI rules:

- Use overview tables with clear edit links.
- Use separate create cards.
- Use object-specific edit pages for substantial edits.
- Use up/down controls for ordering.
- Do not expose raw `display_order` fields.
- Put destructive actions in danger areas.
- Protect or warn on destructive edits that can change existing survey structure.

The Surveys admin section should appear between Pages and Menus in the admin navigation and admin home section list.

### Admin Survey Overview Page

`/admin/surveys/` is the top-level survey admin page.

The first card is `Surveys`.

Above the surveys table, show a checkbox labeled `Show active only`.

- The checkbox is checked by default.
- When checked, the table shows only active surveys.
- When unchecked, the table shows all surveys.
- Filtering should happen client-side from embedded JSON rather than through an Apply button and page reload.
- The no-JavaScript fallback should render the active-surveys table.

The surveys table is sorted by survey name and has one row per survey.

Columns:

- Name, rendered as a secondary edit button linking to `/admin/surveys/<slug>/`.
- Slug.
- Active state.
- Response count.
- View Responses action, linking to `/admin/surveys/<slug>/responses/`.

The embedded survey JSON should include:

- `name`.
- `slug`.
- `is_active`.
- `response_count`.
- `edit_url`.
- `responses_url`.

The second card is `Create Survey`.

Fields:

- `name`.
- `slug`.
- `description_markdown`, as a larger text area.

Create behavior:

- Admins type the slug manually; do not auto-generate it from the name in V1.
- New surveys are active by default.
- `name` and `slug` must be unique.
- `slug` must be valid for use in a URL path segment without escaping.
- Successful creation redirects to `/admin/surveys/<slug>/`.
- Failed creation stays on `/admin/surveys/#create-survey`.

### Admin Survey Edit Page

`/admin/surveys/<slug>/` is the main survey edit page.

The page contains these cards, in order:

- `Survey Details`.
- One card per question.
- `Add Question`.
- `Delete Survey` danger card.

The `Survey Details` card allows editing:

- `name`.
- `slug`.
- `description_markdown`.
- `is_active`.

It ends with an `Update Survey` button.

Each question card allows editing:

- `name`.
- `description_markdown`.
- `render_hint`.
- `is_required`.

The question type is not editable after creation. If the type is wrong, the admin should delete the question and create a new one.

Question card actions:

- `Update` saves the current question card and redirects to that question fragment.
- `Edit` saves the current question card and redirects to `/admin/surveys/<slug>/<question_id>/`.
- Move up saves the current question card, moves the question up, and redirects to that question fragment.
- Move down saves the current question card, moves the question down, and redirects to that question fragment.

Choice-based question cards show choice management below the question fields.

Choice-based question types:

- `single_choice`.
- `multi_choice`.

Choice management includes:

- A create-choice form above the choices table with `label` and `value` fields.
- The Create Choice button should sit to the right of the value field on non-mobile widths and stack below on mobile.
- Creating a choice saves dirty question fields first. If the question update is invalid, the choice is not created.
- A choices table with `label`, `value`, order controls, an inline Update Choice action, and a delete action for each choice.
- The Update Choice button should sit to the right of the value field on non-mobile widths and stack below on mobile.
- An `allows_other` checkbox below the choices table.
- An `other_label` input associated with `allows_other`.

Other is always rendered last on the member-facing survey. Other is not a normal `SurveyChoice` row.

The `Add Question` card contains:

- `name`.
- `question_type`.
- `Create Question` button.

The question creation form should set `render_hint` from the default render hint for the selected question type.

The `Delete Survey` danger card is protected:

- If the survey has no responses or answers, normal protected delete is enough.
- If the survey has responses or answers, require the admin to type `delete` before deleting.
- Deleting a survey deletes its questions, choices, conditions, responses, and answers.

### Admin Question Edit Page

`/admin/surveys/<slug>/<question_id>/` is the detail page for one question.

The first card is the same question edit card used on the survey edit page, but without the `Edit` button. It still has `Update Question`.

The second card is `Conditional`.

Conditional card fields:

- Checkbox: `Display only under specified conditions`.
- Controlling question selector, enabled when conditional display is checked.
- Choice checkboxes for the selected controlling question.

The controlling question selector should show choice-based questions earlier in current display order. If the question already has conditions that point to a controlling question now later in display order, keep that controlling question available and show a warning rather than silently deleting the condition.

Saving conditions:

- If conditional display is unchecked, delete all condition rows for the question.
- If conditional display is checked, require one controlling question and at least one selected choice.
- Saving creates one `SurveyQuestionCondition` row per selected choice.
- Multiple selected choices are OR conditions.
- Full cycle detection must run before saving conditions.

The bottom card is a `Delete Question` danger card.

Deleting a question is allowed even when answers exist. Existing answers must remain understandable through answer snapshots.

### Admin Fragments And Redirects

Use stable fragment IDs so each update returns the admin to the relevant card.

Recommended fragments:

- `#survey-details`.
- `#question-<question_id>`.
- `#create-question`.
- `#delete-survey`.

Redirect behavior:

- Updating survey details redirects to `/admin/surveys/<new-slug>/#survey-details`.
- Updating a question redirects to `/admin/surveys/<slug>/#question-<question_id>`.
- Moving a question redirects to `/admin/surveys/<slug>/#question-<question_id>`.
- Creating a question redirects to `/admin/surveys/<slug>/#question-<new_question_id>`.
- Creating, updating, deleting, or moving choices redirects to the parent question fragment.
- Updating conditions redirects to `/admin/surveys/<slug>/<question_id>/#conditional`.
- Deleting a question redirects to `/admin/surveys/<slug>/#create-question`.

### Admin Response Review Page

`/admin/surveys/<slug>/responses/` shows responses for one survey.

The page should show a response table where each row is one `SurveyResponse`.

Columns:

- Name, combining the user's first and last name into one column.
- Email.
- One column per current survey question, ordered by `display_order`, then `id`.

Answer rendering:

- Decode `SurveyAnswer.value` JSON arrays for display.
- Join multi-value answers with a readable delimiter such as `; `.
- Leave the cell blank if no answer exists for that response/question.
- Leave the cell blank for empty JSON arrays.
- Do not include deleted questions in V1. Deleted-question answers remain snapshotted for historical data, but this response table only reports current questions.

The page should include an `Export CSV` button at the bottom. The button downloads `/admin/surveys/<slug>/responses.csv`.

The export should use the same rows and columns as the HTML table. If there are no responses, it should still export the header row.

## Data Model

### Survey

| Field | Type | Notes |
| --- | --- | --- |
| `id` | primary key | Django default |
| `slug` | slug, unique | Used in `/survey/<slug>/` |
| `name` | string, unique | Human-readable title |
| `description_markdown` | text | Rendered with existing sanitized Markdown renderer |
| `is_active` | boolean, default true | Members can submit/edit when true |
| `created_at` | datetime | Auto-created |
| `updated_at` | datetime | Auto-updated |

Suggested ordering:

- `name`
- `slug`

### SurveyQuestion

| Field | Type | Notes |
| --- | --- | --- |
| `id` | primary key | Django default |
| `survey` | FK to `Survey` | Cascade delete is acceptable before production data; be conservative after responses exist |
| `name` | string | Question prompt |
| `description_markdown` | text | Optional explanatory text below prompt |
| `question_type` | string choices | Defines answer shape |
| `render_hint` | string choices | Defines preferred UI rendering |
| `is_required` | boolean | Required only when visible |
| `allows_other` | boolean | Enables typed other value for choice questions |
| `other_label` | string | Defaults to `Other` |
| `display_order` | integer | Admin-controlled through move buttons |
| `created_at` | datetime | Auto-created |
| `updated_at` | datetime | Auto-updated |

Suggested ordering:

- `survey`
- `display_order`
- `id`

### SurveyChoice

| Field | Type | Notes |
| --- | --- | --- |
| `id` | primary key | Django default |
| `question` | FK to `SurveyQuestion` | Choices belong to one question |
| `label` | string | Display text |
| `value` | string | Optional stored value |
| `display_order` | integer | Admin-controlled through move buttons |
| `created_at` | datetime | Auto-created |
| `updated_at` | datetime | Auto-updated |

If `value` is blank, use `label` as the answer value.

Choices are valid for choice-based question types.

### SurveyQuestionCondition

Conditions determine when a question is visible.

| Field | Type | Notes |
| --- | --- | --- |
| `id` | primary key | Django default |
| `question` | FK to `SurveyQuestion` | The question being shown or hidden |
| `depends_on_question` | FK to `SurveyQuestion` | Choice-based controlling question |
| `visible_if_choice` | FK to `SurveyChoice` | Choice that makes `question` visible |
| `created_at` | datetime | Auto-created |
| `updated_at` | datetime | Auto-updated |

Semantics:

- No condition rows means the question is always visible.
- One condition row means the question is visible if that choice is selected.
- Multiple rows for the same question are OR conditions.
- A conditional question should depend on only one controlling question in V1.
- Conditions depend on questions in the same survey.
- The admin UI should prefer controlling questions earlier in current display order because that matches how members read the form.
- Conditions only depend on `single_choice` or `multi_choice` questions.
- Freeform text conditions are not supported in V1.
- Full cycle detection must prevent circular condition graphs.

Example:

| Question | Depends On | Visible If Choice |
| --- | --- | --- |
| `Who is your sponsor?` | `How many years have you been camping?` | `0` |

Meaning:

Show `Who is your sponsor?` when the user selected `0` for `How many years have you been camping?`

Suggested constraints:

- `question != depends_on_question`
- `question.survey == depends_on_question.survey`
- `visible_if_choice.question == depends_on_question`
- Unique row for `question`, `depends_on_question`, and `visible_if_choice`

Cycle detection should treat each condition as a directed edge from the dependent question to the controlling question. Saving conditions must reject any graph where following those edges can return to the starting question.

### SurveyResponse

| Field | Type | Notes |
| --- | --- | --- |
| `id` | primary key | Django default |
| `survey` | FK to `Survey` | The survey being answered |
| `user` | FK to user model | The member who answered |
| `created_at` | datetime | Auto-created |
| `updated_at` | datetime | Auto-updated |

Constraints:

- Unique `survey`, `user`

A response is created the first time a member saves a valid survey. Later saves update the same response.

### SurveyAnswer

| Field | Type | Notes |
| --- | --- | --- |
| `id` | primary key | Django default |
| `response` | FK to `SurveyResponse` | Parent response |
| `question` | nullable FK to `SurveyQuestion` | Current question reference; use `SET_NULL` when a question is deleted |
| `question_id_snapshot` | integer | Question ID at save time, for deleted-question history |
| `question_name_snapshot` | string | Prompt at save time |
| `question_type_snapshot` | string | Type at save time |
| `render_hint_snapshot` | string | Render hint at save time |
| `value` | text | JSON array of strings |
| `choice_snapshot` | text | JSON array of selected choice metadata |
| `created_at` | datetime | Auto-created |
| `updated_at` | datetime | Auto-updated |

Do not snapshot `description_markdown` in V1.

Constraints:

- Current answers should be unique for `response`, `question` while `question` is not null.

Deleting an individual question must not delete existing answers. The nullable `question` reference and snapshots preserve answer history after the question row is gone.

## Question Types

Recommended V1 `question_type` values:

| Value | Meaning |
| --- | --- |
| `text` | Freeform text answer |
| `single_choice` | One selected predefined choice, optionally with other |
| `multi_choice` | Zero or more selected predefined choices, optionally with other |

Yes/no questions should be `single_choice` questions with Yes and No choices.

Scale questions should be `single_choice` questions with numeric-looking choices and `render_hint = scale`.

Question type is chosen when the question is created and is not editable after creation.

## Render Hints

Render hints are stored on `SurveyQuestion.render_hint`.

The selected render hint controls presentation and some validation, but `question_type` controls the answer shape.

The allowed hint matrix should live in code, not in the database, because adding a render hint also requires rendering, validation, and tests.

Recommended V1 matrix:

| `question_type` | Allowed `render_hint` values | Default |
| --- | --- | --- |
| `text` | `short_text`, `long_text`, `email`, `phone`, `number`, `date` | `short_text` |
| `single_choice` | `radio`, `select`, `scale` | `radio` |
| `multi_choice` | `checkboxes` | `checkboxes` |

Recommended code location:

```text
surveys/question_types.py
```

That module should define the executable source of truth for allowed and default hints, such as:

```text
ALLOWED_RENDER_HINTS
DEFAULT_RENDER_HINTS
```

Use those constants in:

- Model or service validation.
- Admin forms.
- Question creation defaults.
- Member form rendering.
- Tests.

V1 render hint meanings:

| Value | Intended UI |
| --- | --- |
| `short_text` | Single-line text input |
| `long_text` | Textarea |
| `email` | Email-style text input plus server validation |
| `phone` | Phone-style text input |
| `number` | Numeric-looking text input |
| `date` | Date input |
| `radio` | Radio buttons |
| `select` | Select dropdown |
| `checkboxes` | Checkbox list |
| `scale` | Radio-style scale |

Validation notes:

- `short_text`, `long_text`, `phone`, and `number` are stored as strings.
- `email` should receive email-format validation.
- `date` should receive ISO date validation from the submitted date input.
- `radio`, `select`, and `scale` save one valid choice value.
- `checkboxes` saves zero or more valid choice values.

## Answer Values

`SurveyAnswer.value` stores text containing a JSON array of strings.

Always use JSON serialization, such as `json.dumps(...)`. Do not hand-build JSON strings.

Examples:

| Answer Kind | Stored `value` |
| --- | --- |
| Short text | `["Alice"]` |
| Long text | `["I have camped before."]` |
| Single choice | `["green"]` |
| Multiple choice | `["green", "pink"]` |
| Scale | `["3"]` |
| Optional unanswered | `[]` |

This format keeps all answer values consistent while avoiding premature reporting-specific schema.

## Choice Snapshots

`SurveyAnswer.choice_snapshot` stores text containing a JSON array of selected choice metadata.

For a predefined choice:

```json
[{"source":"choice","choice_id":12,"label":"Option 1","value":"Option 1"}]
```

For an other answer:

```json
[{"source":"other","label":"Other","value":"Custom answer"}]
```

For a text answer with no predefined choice:

```json
[]
```

The snapshot lets admins understand old answers if a choice label or value changes later.

## Other Answers

`allows_other` enables an extra typed answer for choice questions.

Behavior:

- For `single_choice`, selecting Other stores one typed value.
- For `multi_choice`, selecting Other adds one typed value alongside selected predefined choices.
- Empty Other text should not be saved.
- If Other is selected and the question is required, the typed Other value should be required.
- If Other is not selected, any posted Other text should be ignored.

The saved `choice_snapshot` should distinguish predefined choices from Other values.

## Conditional Visibility

Conditionals are based only on selected choices.

A question is visible when:

- It has no `SurveyQuestionCondition` rows.
- It has at least one condition row where `visible_if_choice` is selected in the controlling answer.

A question is hidden when:

- It has condition rows and none of the referenced choices are selected.

Required validation only applies to visible questions.

Hidden questions should save as empty answers or have their answer deleted. The preferred V1 behavior is to keep one answer row per previously answered question and set hidden answers to `[]`, but deleting hidden answers is acceptable if the implementation is simpler and exports treat missing as empty.

Conditions may be created in any question creation order. The admin UI should guide users toward depending on earlier displayed questions, but correctness must come from a full condition graph cycle check.

The cycle validator must reject:

- A question depending on itself.
- A two-question cycle.
- Any longer cycle.

The cycle validator should allow:

- Simple chains.
- Multiple questions depending on the same controlling question.
- One question visible for multiple selected choices from the same controlling question.

## Member UI Conditional Behavior

Django renders the complete survey form server-side.

The member survey page should use one card per question. Existing answers should be prepopulated from the member's current `SurveyResponse`.

Prepopulation rules:

- Text answers prepopulate from the decoded `SurveyAnswer.value` array.
- Choice answers preselect current choices when the saved snapshot still references existing choices.
- Other answers refill the other text input from the saved snapshot.
- If a saved answer references a deleted choice, keep the historical answer in snapshots but do not force that deleted choice back into the current form.

Each question wrapper should include condition metadata for JavaScript, such as:

```html
<fieldset
  data-survey-question-id="42"
  data-visible-if-question-id="17"
  data-visible-if-choice-ids="[10,11]"
>
</fieldset>
```

Vanilla JavaScript should:

- Watch controlling choice inputs.
- Show dependent questions when their condition matches.
- Hide dependent questions when their condition does not match.
- Disable inputs inside hidden questions so stale hidden values are not submitted.
- Re-enable inputs when questions become visible again.

JavaScript is a progressive enhancement. The server must recompute visibility and validation on POST.

Without JavaScript, the page can show all questions. Conditional descriptions should make dependent questions understandable, and the server should ignore hidden-by-rule answers when the form is submitted.

## Server Validation

The server is authoritative.

On POST, the server should:

- Load survey questions and choices.
- Parse submitted answers.
- Determine visible questions from submitted choice IDs.
- Validate required visible questions.
- Validate answer shape for each visible question.
- Ignore or clear hidden question answers.
- Save the response and answers in a transaction.

Validation rules:

- Inactive surveys cannot be submitted by members.
- Required visible questions cannot have empty `value`.
- Text questions save zero or one string.
- Single-choice questions save zero or one string.
- Multi-choice questions save zero or more strings.
- Choice answers must reference choices belonging to the question.
- Other answers are only accepted when `allows_other = true`.
- Conditional parent questions must be from the same survey.

## Admin Editing Rules

V1 should allow editing survey definitions after responses exist. Answer snapshots are intentionally present so historical answers stay understandable when questions or choices later change.

Safe edits:

- Rename survey.
- Update survey description.
- Toggle `is_active`.
- Edit question description.
- Reorder questions.
- Reorder choices.
- Edit choice label if admins understand old answers use snapshots.

Risky edits:

- Changing `question_type` after question creation.
- Deleting questions after responses exist.
- Deleting choices after responses exist.
- Deleting choices used by conditions.

Recommended V1 behavior:

- Prevent changing `question_type` after question creation.
- Allow deleting a question with answers, preserving answers through nullable `SurveyAnswer.question` and snapshots.
- Allow deleting a choice with answers, preserving answer context through `choice_snapshot`.
- Block deleting a choice that is used by a condition until the condition is edited. This avoids silently changing visibility rules.
- Allow deactivating a survey instead of deleting it.
- Show response counts on survey and question admin pages.
- Require typed `delete` confirmation before deleting a survey with responses or answers.

## Exports

V1 export is CSV from the response review page.

Route:

```text
/admin/surveys/<slug>/responses.csv
```

Export shape:

- One row per `SurveyResponse`.
- Include one combined user name column.
- Include user email.
- Include one column per current survey question.
- Decode answer `value` JSON arrays for display.
- Join multi-value answers with a readable delimiter such as `; `.
- Leave empty or missing answers blank.
- Exclude deleted questions for V1.
- Export headers even when there are no responses.

Snapshots are primarily for historical answer interpretation. The response table and CSV use current question order and current question names in V1.

## Dashboard And Payment Integration

Surveys are generic in V1.

The survey app should not require a `CampYear` FK. A year-specific survey can use a slug like `2026-arrival-survey`.

Future dashboard integration can add a separate requirement/configuration model that points a camp year to a survey. That future model can decide whether survey completion gates taxes.

Do not store survey completion state on the user account or member profile.

## Security And Permissions

Member survey pages require an authenticated active user.

Admin survey pages require an authenticated active admin user.

A member may only view or edit their own response.

Admins may view and export responses.

Survey Markdown should use the existing sanitized Markdown rendering path.

## Testing Notes

The survey system should be tested by feature. Server-side behavior is the critical path; JavaScript is progressive enhancement and should not be the only thing enforcing visibility, requiredness, or data cleanup.

### Test Principles

- Test every important behavior through the server, even when the browser also has JavaScript support.
- Test form validation failures leave existing database state unchanged.
- Test redirects include the expected fragment when the UI depends on returning to a specific card.
- Test historical snapshots whenever deleting or editing current survey structure could otherwise make old answers confusing.
- Keep JavaScript small enough that syntax checks and server-side invariants provide most confidence.

### Model And Service Tests

Survey tests should cover:

- `Survey.is_active` defaults to true.
- `Survey.name` is unique.
- `Survey.slug` is unique.
- Invalid slugs with spaces or unsafe URL characters are rejected.
- Surveys sort by `name` then `slug`.

Question tests should cover:

- Creating a question appends it after existing questions by `display_order`.
- Reordering questions swaps display order without exposing raw order fields.
- `question_type` values are limited to the V1 enum.
- `question_type` is treated as immutable after creation by admin forms.
- New questions get the default render hint for their type.
- The render-hint matrix rejects incompatible values, such as `text` plus `checkboxes` or `multi_choice` plus `short_text`.
- `allows_other` and `other_label` are meaningful only for choice-based questions.
- `is_required` is enforced only when the question is visible.

Choice tests should cover:

- Creating a choice appends it after existing choices by `display_order`.
- Reordering choices swaps display order without exposing raw order fields.
- Blank `SurveyChoice.value` falls back to `SurveyChoice.label` for saved answers.
- Choices are only valid for choice-based questions.
- Deleting a choice used by a condition is blocked until the condition is changed.
- Deleting a choice with existing answers preserves historical answer meaning through `choice_snapshot`.

Condition tests should cover:

- Conditions can only reference questions in the same survey.
- `visible_if_choice` must belong to `depends_on_question`.
- `depends_on_question` must be choice-based.
- A question cannot depend on itself.
- A dependent question can only have one controlling question in V1.
- Multiple condition rows for the same dependent question and controlling question are allowed when they reference different choices.
- Duplicate rows for the same `question`, `depends_on_question`, and `visible_if_choice` are rejected.
- Self-cycles are rejected.
- Two-question cycles are rejected.
- Three-or-more-question cycles are rejected.
- Valid condition chains are allowed.
- Valid branch graphs, where multiple questions depend on the same controlling question, are allowed.
- Invalid condition saves do not partially replace existing valid conditions.

Response and answer tests should cover:

- A user can have only one `SurveyResponse` per survey.
- Different users can each have responses for the same survey.
- The same user can have responses for different surveys.
- `SurveyAnswer.value` is always JSON serialized as an array of strings.
- Text answers snapshot question ID, name, type, and render hint.
- Choice answers snapshot selected choice IDs, labels, values, and source.
- Other answers snapshot `source = "other"` separately from predefined choices.
- Current answers are unique per response and non-null question.
- Deleting a question sets existing answer `question` references to null and preserves snapshots.
- Deleting a whole survey cascades through its questions, choices, conditions, responses, and answers.

### Admin Overview Tests

`/admin/surveys/` tests should cover:

- Anonymous users are redirected to login.
- Non-admin members receive `403`.
- Admin users can load the page.
- The page appears in the admin navigation between Pages and Menus.
- The admin home section list includes Surveys between Pages and Menus.
- The `Show active only` checkbox is checked by default.
- Active-only mode hides inactive surveys in the no-JavaScript fallback.
- Embedded survey JSON includes active and inactive surveys for client-side filtering.
- Unchecking active-only shows both active and inactive surveys without a page reload.
- Survey rows are sorted by name.
- Each row shows an edit button, slug, active state, response count, and View Responses action.
- Response counts match the number of `SurveyResponse` rows for each survey.
- View Responses links to `/admin/surveys/<slug>/responses/`.
- Empty state renders when there are no matching surveys.
- Create Survey form includes name, slug, and a larger description field.
- Create Survey form does not expose `is_active` because new surveys default active.
- Creating a valid survey saves name, slug, description, and active default.
- Creating a survey redirects to `/admin/surveys/<slug>/`.
- Duplicate name is rejected.
- Duplicate slug is rejected.
- Invalid slug is rejected.
- Failed creation returns to `/admin/surveys/#create-survey` with errors.

### Admin Survey Edit Tests

`/admin/surveys/<slug>/` tests should cover:

- Anonymous users are redirected to login.
- Non-admin members receive `403`.
- Unknown survey slug returns `404`.
- Survey Details card renders name, slug, description, and active fields.
- Updating survey details saves all fields.
- Updating survey details after changing slug redirects to `/admin/surveys/<new-slug>/#survey-details`.
- Duplicate survey name is rejected without changing the survey.
- Duplicate survey slug is rejected without changing the survey.
- Invalid survey slug is rejected without changing the survey.
- Questions render one card per question in display order.
- Question cards render name, description, render hint, and required fields.
- Question cards do not render editable question type controls.
- Render-hint choices are limited to hints valid for that question's type.
- Updating a question saves dirty fields and redirects to `#question-<question_id>`.
- Clicking Edit on a dirty question saves dirty fields and redirects to `/admin/surveys/<slug>/<question_id>/`.
- Moving a dirty question up saves dirty fields, updates order, and redirects to that question fragment.
- Moving a dirty question down saves dirty fields, updates order, and redirects to that question fragment.
- Moving the first question up is a no-op that does not corrupt ordering.
- Moving the last question down is a no-op that does not corrupt ordering.
- Adding a text question sets the default text render hint.
- Adding a single-choice question sets the default single-choice render hint.
- Adding a multi-choice question sets the default multi-choice render hint.
- Adding a question appends it to the end and redirects to `#question-<new_question_id>`.

Choice management tests on the survey edit page should cover:

- Text questions do not show choice management controls.
- Single-choice questions show choice management controls.
- Multi-choice questions show choice management controls.
- Creating a choice saves dirty question fields first, saves label and value, and redirects to the parent question fragment.
- Invalid dirty question fields block choice creation and leave existing question data unchanged.
- Creating a choice with blank value is accepted.
- Choice rows render in display order.
- Moving a choice up updates order and redirects to the parent question fragment.
- Moving a choice down updates order and redirects to the parent question fragment.
- Updating choice label or value saves changes and redirects to the parent question fragment.
- Deleting an unused choice removes it and redirects to the parent question fragment.
- Deleting a choice used by a condition is rejected with a friendly error.
- Updating `allows_other` and `other_label` saves both fields.

Survey delete tests should cover:

- Delete Survey card appears at the bottom of the page.
- Deleting a survey with no responses succeeds through protected delete.
- Deleting a survey with responses or answers fails without typed `delete` confirmation.
- Deleting a survey with responses or answers fails with the wrong confirmation text.
- Deleting a survey with responses or answers succeeds with typed `delete` confirmation.
- Successful survey delete redirects to `/admin/surveys/`.
- Successful survey delete removes questions, choices, conditions, responses, and answers.

### Admin Question Detail Tests

`/admin/surveys/<slug>/<question_id>/` tests should cover:

- Anonymous users are redirected to login.
- Non-admin members receive `403`.
- Unknown survey slug returns `404`.
- Unknown question ID returns `404`.
- A question ID from a different survey returns `404`.
- The question edit card renders without an Edit button.
- Updating the question saves fields and redirects back to the question detail page.
- The Conditional card is unchecked when the question has no conditions.
- Unchecking conditional display deletes existing condition rows.
- Checking conditional display requires a controlling question.
- Checking conditional display requires at least one selected choice.
- The controlling question selector includes choice-based questions earlier in current display order.
- The controlling question selector excludes text questions.
- The controlling question selector excludes the current question.
- If an existing controlling question is now later in display order, it remains selectable and the page shows a warning.
- Selecting one controlling choice creates one condition row.
- Selecting multiple controlling choices creates multiple OR condition rows.
- Updating conditions replaces old rows for that question rather than appending stale rows.
- Condition updates reject wrong-survey questions.
- Condition updates reject choices that do not belong to the controlling question.
- Condition updates reject text controlling questions.
- Condition updates reject cycles and preserve prior valid conditions.

Question delete tests should cover:

- Delete Question card appears at the bottom of the page.
- Deleting a question removes that question and its choices.
- Deleting a question removes conditions where that question is the dependent question.
- Deleting a question removes conditions where that question is the controlling question.
- Deleting a question with answers preserves those answers with null question references and snapshots.
- Successful question delete redirects to `/admin/surveys/<slug>/#create-question`.

### Member Survey Page Tests

`/survey/<slug>/` tests should cover:

- Anonymous users are redirected to login.
- Inactive users cannot access the survey.
- Unknown survey slug returns `404`.
- Inactive survey access is blocked with the chosen unavailable behavior.
- Active survey page renders the survey name and sanitized description in the first card.
- Active survey page renders one card per current question in display order.
- Conditional question cards include the data attributes needed by JavaScript.
- Text render hints render the expected text, textarea, email, phone, number, and date controls.
- Single-choice render hints render radio, select, and scale controls.
- Multi-choice render hint renders checkbox controls.
- Other controls render last when `allows_other` is enabled.
- Other controls do not render when `allows_other` is disabled.
- Existing text answers prepopulate from decoded JSON values.
- Existing single-choice answers preselect the saved current choice when it still exists.
- Existing multi-choice answers preselect all saved current choices that still exist.
- Existing other answers prepopulate the other field.
- Deleted historical choices remain in snapshots but are not forced back into the current form.

### Member Submission Tests

Submission tests should cover:

- Posting a valid first response creates one response and answer rows.
- Posting again updates the existing response rather than creating a second response.
- Successful POST redirects to `/survey/<slug>/complete/`.
- The completion page loads for the logged-in user.
- The completion page links back to the survey while the survey is active.
- Inactive surveys reject POST without changing existing answers.
- Required visible text questions reject empty answers.
- Required hidden questions do not reject empty answers.
- Optional unanswered questions save as empty JSON arrays or are treated as empty consistently.
- Text questions save zero or one string.
- Single-choice questions reject multiple selected choices.
- Single-choice questions reject choices from other questions.
- Multi-choice questions reject choices from other questions.
- Multi-choice questions save multiple selected values in display or submitted order consistently.
- Email render hint validates email format.
- Date render hint validates ISO date input.
- Number render hint validates number-looking input while still saving a string.
- Other text is required when Other is selected on a required question.
- Posted Other text is ignored when Other is not selected.
- Other answers are rejected when `allows_other` is false.
- Choice snapshots distinguish predefined choices from Other values.
- Conditional visibility is recomputed on the server from submitted choice IDs.
- A hidden conditional answer does not remain as an active saved value after submission.
- A conditional question becomes required when its condition is met and `is_required` is true.
- A conditional question is not required when its condition is not met.
- Multiple selected condition choices behave as OR conditions.
- Multi-choice controlling questions trigger dependents when any selected choice matches.
- Malicious POSTs cannot answer another user's response.

### Export And Response Review Tests

Response review page tests should cover:

- Anonymous users are redirected to login.
- Non-admin members receive `403`.
- Admin users can view `/admin/surveys/<slug>/responses/`.
- Unknown survey slug returns `404`.
- The table includes Name and Email columns.
- The Name column combines first and last name.
- The table includes one column per current survey question in current display order.
- The table includes one row per survey response.
- Text answers render as readable strings.
- Multi-value answers render with the chosen delimiter.
- Missing answers render as blank cells.
- Empty JSON array answers render as blank cells.
- Deleted questions do not appear as columns.
- The Export CSV button appears at the bottom of the page.

CSV export tests should cover:

- Anonymous users are redirected to login.
- Non-admin members receive `403`.
- Admin users can export `/admin/surveys/<slug>/responses.csv`.
- Export headers include Name and Email.
- Export headers include current survey questions in current display order.
- Text answers export as readable strings.
- Multi-value answers export with the chosen delimiter.
- Empty or hidden answers export as empty cells.
- Deleted questions do not appear as current-question columns.
- Export with no responses still returns the header row.
- CSV values are escaped correctly for commas, quotes, and newlines.

### JavaScript Tests And Checks

JavaScript should remain small and non-authoritative.

Checks should cover:

- `node --check` passes for the survey JavaScript file.
- Rendered question cards include enough `data-*` metadata for conditional behavior.
- Server tests still pass with JavaScript behavior assumed absent.
- If a browser-level test tool is later added, add one smoke test that changing a controlling choice hides and shows a dependent question and disables hidden inputs.
